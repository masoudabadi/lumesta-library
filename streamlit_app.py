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

# --- 2. SEARCH LOGIC (Expanded to 40) ---
def search_google_books(query):
    # maxResults=40 is the API limit for a single page
    url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=40"
    found_books = []
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if "items" in data:
            for item in data["items"]:
                info = item.get("volumeInfo", {})
                
                # Find the best ISBN
                isbn = "Unknown"
                for ident in info.get("industryIdentifiers", []):
                    if ident["type"] == "ISBN_13":
                        isbn = ident["identifier"]
                        break
                
                # Build the book object
                book = {
                    "title": info.get("title", "Unknown Title"),
                    "author": ", ".join(info.get("authors", ["Unknown Author"])),
                    "cover": info.get("imageLinks", {}).get("thumbnail", ""),
                    "isbn": isbn,
                    "published": info.get("publishedDate", "")[:4] # Year only
                }
                found_books.append(book)
    except Exception as e:
        st.error(f"Search Error: {e}")
        
    return found_books

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
    st.markdown("### 1. Find a Book")
    
    # Camera Section
    img_file = st.camera_input("Scan Barcode (Optional)")
    scanned_code = ""
    if img_file:
        scanned_code = decode_barcode(img_file)
        if scanned_code:
            st.success(f"Scanned: {scanned_code}")
    
    # Search Input
    default_search = scanned_code if scanned_code else ""
    user_query = st.text_input("Enter Title, Author, or ISBN", value=default_search)

    # Search Button
    if st.button("Search Library", type="primary"):
        if user_query:
            clean_query = user_query.replace("-", "").strip()
            with st.spinner(f"Searching for '{user_query}'..."):
                results = search_google_books(clean_query)
                st.session_state['search_results'] = results
                
                if not results:
                    st.warning("No books found.")
        else:
            st.warning("Please enter a title or ISBN.")

    # --- RESULTS LIST ---
    if 'search_results' in st.session_state and st.session_state['search_results']:
        results = st.session_state['search_results']
        st.markdown(f"### Found {len(results)} Results")
        
        for i, book in enumerate(results):
            # We use a container to group the book info nicely
            with st.container():
                col1, col2, col3 = st.columns([1, 4, 2])
                
                # Col 1: Cover Image
                with col1:
                    if book['cover']:
                        st.image(book['cover'], width=70)
                    else:
                        st.write("📘") # Placeholder icon
                
                # Col 2: Info
                with col2:
                    st.markdown(f"**{book['title']}**")
                    st.caption(f"{book['author']} ({book['published']})")
                    st.caption(f"ISBN: {book['isbn']}")
                
                # Col 3: Add Button
                with col3:
                    # Unique key is essential here!
                    if st.button("Add to Library", key=f"btn_{i}"):
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
                            st.toast(f"✅ Added '{book['title']}'!")
                        except Exception as e:
                            st.error("Save failed. Check permissions.")
                
                st.divider()

with tab2:
    if st.button("Refresh List"):
        st.rerun()
    
    data = sheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df[['Title', 'Author', 'Status']])
    else:
        st.info("Library is empty.")
