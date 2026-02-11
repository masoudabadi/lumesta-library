import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import pandas as pd
from PIL import Image
from pyzbar.pyzbar import decode

st.set_page_config(page_title="Lumesta Library", page_icon="📚", layout="centered")
st.title("📚 Lumesta Library")

# --- 1. CONNECT TO DATABASE ---
try:
    creds_dict = {
        "type": st.secrets["gcp_service_account"]["type"],
        "project_id": st.secrets["gcp_service_account"]["project_id"],
        "private_key_id": st.secrets["gcp_service_account"]["private_key_id"],
        "private_key": st.secrets["gcp_service_account"]["private_key"],
        "client_email": st.secrets["gcp_service_account"]["client_email"],
        "client_id": st.secrets["gcp_service_account"]["client_id"],
        "auth_uri": st.secrets["gcp_service_account"]["auth_uri"],
        "token_uri": st.secrets["gcp_service_account"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["gcp_service_account"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["gcp_service_account"]["client_x509_cert_url"]
    }
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Lumesta_Library").sheet1
    st.caption("✅ Database Connected")
except Exception as e:
    st.error(f"Database Error: {e}")
    st.stop()

# --- 2. AGGREGATOR SEARCH ENGINE ---
def search_books_hybrid(query):
    results = []
    clean_query = str(query).strip()
    
    # Check if it looks like an ISBN (Digits only)
    is_isbn = clean_query.replace("-", "").isdigit()

    # --- SOURCE 1: GOOGLE BOOKS ---
    try:
        # We ask for 15 results from Google
        url = f"https://www.googleapis.com/books/v1/volumes?q={clean_query}&maxResults=15"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if "items" in data:
                for item in data["items"]:
                    info = item.get("volumeInfo", {})
                    
                    # Find ISBN
                    isbn = "Unknown"
                    for ident in info.get("industryIdentifiers", []):
                        if ident["type"] == "ISBN_13":
                            isbn = ident["identifier"]
                            break
                    
                    results.append({
                        "source": "Google Books",
                        "title": info.get("title", "Unknown"),
                        "author": ", ".join(info.get("authors", ["Unknown"])),
                        "cover": info.get("imageLinks", {}).get("thumbnail", ""),
                        "isbn": isbn,
                        "year": info.get("publishedDate", "")[:4]
                    })
    except:
        pass

    # --- SOURCE 2: OPEN LIBRARY ---
    # We ALWAYS run this for text searches now (not just as backup)
    # This doubles our chances of finding relevant books
    try:
        if is_isbn:
            # ISBN Mode (Strict)
            isbn_clean = clean_query.replace("-", "")
            url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn_clean}&format=json&jscmd=data"
            resp = requests.get(url).json()
            key = f"ISBN:{isbn_clean}"
            if key in resp:
                info = resp[key]
                results.insert(0, { # Put exact ISBN match at top
                    "source": "OpenLibrary",
                    "title": info.get("title", "Unknown"),
                    "author": ", ".join([a["name"] for a in info.get("authors", [])]),
                    "cover": info.get("cover", {}).get("medium", ""),
                    "isbn": isbn_clean,
                    "year": info.get("publish_date", "")
                })
        else:
            # Text Mode (Broad)
            # We ask for top 15 from Open Library too
            search_url = f"https://openlibrary.org/search.json?q={clean_query}&limit=15"
            resp = requests.get(search_url).json()
            for doc in resp.get("docs", []):
                cover_id = doc.get("cover_i")
                cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else ""
                
                # Only add if it has a title
                if doc.get("title"):
                    results.append({
                        "source": "OpenLibrary",
                        "title": doc.get("title"),
                        "author": ", ".join(doc.get("author_name", ["Unknown"])),
                        "cover": cover_url,
                        "isbn": doc.get("isbn", ["Unknown"])[0] if "isbn" in doc else "Unknown",
                        "year": str(doc.get("first_publish_year", ""))
                    })
    except:
        pass

    # --- CLEANUP & SORTING ---
    # 1. Remove duplicates (based on Title + Author) to keep list clean
    seen = set()
    unique_results = []
    for book in results:
        # Create a unique "fingerprint" for the book
        fingerprint = (book['title'].lower(), book['author'].lower())
        if fingerprint not in seen:
            seen.add(fingerprint)
            unique_results.append(book)
    
    # 2. Sort: Put books WITH covers at the top (they look better)
    unique_results.sort(key=lambda x: x['cover'] == "", reverse=False)

    return unique_results

def decode_barcode(image_file):
    try:
        image = Image.open(image_file)
        decoded_objects = decode(image)
        for obj in decoded_objects:
            if obj.type in ['EAN13', 'ISBN13']:
                return obj.data.decode('utf-8')
    except:
        pass
    return None

# --- 3. APP INTERFACE ---
tab1, tab2 = st.tabs(["➕ Add New Book", "📖 View Library"])

with tab1:
    st.write("### Find a Book")
    
    # Camera
    img_file = st.camera_input("Scan Barcode (Optional)")
    scanned_code = ""
    if img_file:
        scanned_code = decode_barcode(img_file)
        if scanned_code:
            st.success(f"Scanned: {scanned_code}")

    # Search Box
    default = scanned_code if scanned_code else ""
    user_query = st.text_input("Enter Title, Author, or ISBN", value=default)

    if st.button("Search", type="primary"):
        if user_query:
            with st.spinner(f"Searching for '{user_query}'..."):
                results = search_books_hybrid(user_query)
                st.session_state['results'] = results
                
                if not results:
                    st.error("No books found.")
        else:
            st.warning("Please enter text to search.")

    # Display Results
    if 'results' in st.session_state and st.session_state['results']:
        results = st.session_state['results']
        st.write(f"Found {len(results)} results:")
        
        for i, book in enumerate(results):
            with st.container():
                col1, col2, col3 = st.columns([1, 3, 2])
                
                with col1:
                    if book['cover']:
                        st.image(book['cover'], width=60)
                    else:
                        st.write("📘")
                
                with col2:
                    st.markdown(f"**{book['title']}**")
                    st.caption(f"{book['author']}")
                    st.caption(f"Source: {book['source']}")
                
                with col3:
                    if st.button("Add", key=f"add_{i}"):
                        try:
                            sheet.append_row([
                                book['isbn'], 
                                book['title'], 
                                book['author'], 
                                "Available", 
                                "", 
                                "", 
                                book['cover']
                            ])
                            st.toast(f"✅ Added {book['title']}!")
                        except:
                            st.error("Save failed. Check Permissions.")
                st.divider()

with tab2:
    if st.button("Refresh List"):
        st.rerun()
    data = sheet.get_all_records()
    if data:
        st.dataframe(pd.DataFrame(data))
    else:
        st.info("Empty Library")
