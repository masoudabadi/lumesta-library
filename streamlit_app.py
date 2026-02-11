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

# --- 2. SEARCH LOGIC (Hybrid) ---
def search_books_hybrid(query):
    results = []
    clean_query = str(query).strip()
    is_isbn = clean_query.replace("-", "").isdigit()

    # Google Books
    try:
        url = f"https://www.googleapis.com/books/v1/volumes?q={clean_query}&maxResults=15"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if "items" in data:
                for item in data["items"]:
                    info = item.get("volumeInfo", {})
                    isbn = "Unknown"
                    for ident in info.get("industryIdentifiers", []):
                        if ident["type"] == "ISBN_13":
                            isbn = ident["identifier"]
                            break
                    results.append({
                        "source": "Google",
                        "title": info.get("title", "Unknown"),
                        "author": ", ".join(info.get("authors", ["Unknown"])),
                        "cover": info.get("imageLinks", {}).get("thumbnail", ""),
                        "isbn": isbn
                    })
    except:
        pass

    # Open Library
    try:
        if is_isbn:
            isbn_clean = clean_query.replace("-", "")
            url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn_clean}&format=json&jscmd=data"
            resp = requests.get(url).json()
            key = f"ISBN:{isbn_clean}"
            if key in resp:
                info = resp[key]
                results.insert(0, {
                    "source": "OpenLibrary",
                    "title": info.get("title", "Unknown"),
                    "author": ", ".join([a["name"] for a in info.get("authors", [])]),
                    "cover": info.get("cover", {}).get("medium", ""),
                    "isbn": isbn_clean
                })
        else:
            search_url = f"https://openlibrary.org/search.json?q={clean_query}&limit=10"
            resp = requests.get(search_url).json()
            for doc in resp.get("docs", []):
                if doc.get("title"):
                    cover_id = doc.get("cover_i")
                    cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else ""
                    results.append({
                        "source": "OpenLibrary",
                        "title": doc.get("title"),
                        "author": ", ".join(doc.get("author_name", ["Unknown"])),
                        "cover": cover_url,
                        "isbn": doc.get("isbn", ["Unknown"])[0] if "isbn" in doc else "Unknown"
                    })
    except:
        pass

    # Deduplicate
    seen = set()
    unique = []
    for book in results:
        fp = (book['title'].lower(), book['author'].lower())
        if fp not in seen:
            seen.add(fp)
            unique.append(book)
    return unique

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
tab1, tab2 = st.tabs(["➕ Add Books", "📋 Loan Desk"])

# --- TAB 1: ADD BOOKS ---
with tab1:
    st.write("### Find a Book")
    img_file = st.camera_input("Scan Barcode")
    scanned = decode_barcode(img_file) if img_file else ""
    if scanned: st.success(f"Scanned: {scanned}")
    
    query = st.text_input("Title, Author, or ISBN", value=scanned)
    
    if st.button("Search", type="primary"):
        if query:
            with st.spinner("Searching..."):
                results = search_books_hybrid(query)
                st.session_state['results'] = results
                if not results: st.error("No books found.")
    
    if 'results' in st.session_state and st.session_state['results']:
        st.write(f"Found {len(st.session_state['results'])} results:")
        for i, book in enumerate(st.session_state['results']):
            with st.container():
                c1, c2, c3 = st.columns([1, 3, 2])
                with c1:
                    if book['cover']: st.image(book['cover'], width=50)
                with c2:
                    st.write(f"**{book['title']}**")
                    st.caption(book['author'])
                with c3:
                    if st.button("Add", key=f"add_{i}"):
                        sheet.append_row([book['isbn'], book['title'], book['author'], "Available", "", "", book['cover']])
                        st.toast("✅ Added!")
                st.divider()

# --- TAB 2: LOAN MANAGER (Optimized for Large Libraries) ---
with tab2:
    st.header("Loan Desk")
    
    # 1. Fetch Current Data
    data = sheet.get_all_records()
    
    if not data:
        st.info("Library is empty.")
    else:
        df = pd.DataFrame(data)
        
        # 2. Search Filter
        st.write("##### Search Collection")
        search_term = st.text_input("Filter by Title or Author...", placeholder="e.g. Gatsby")
        
        # Filter the DataFrame based on search
        if search_term:
            filtered_df = df[
                df['Title'].astype(str).str.contains(search_term, case=False) | 
                df['Author'].astype(str).str.contains(search_term, case=False)
            ]
        else:
            filtered_df = df # Show all if search is empty
        
        # 3. Dynamic Dropdown (Shows only filtered results)
        book_list = filtered_df['Title'].tolist()
        
        if not book_list:
            st.warning("No matching books found.")
        else:
            selected_book = st.selectbox("Select Book to Edit:", book_list)
            
            # 4. Editing Interface
            if selected_book:
                # Get the exact row data
                # We search the ORIGINAL dataframe to find the index (essential for writing back to sheet)
                original_index = df[df['Title'] == selected_book].index[0]
                sheet_row_number = original_index + 2 
                
                # Get current values
                current_status = df.loc[original_index, 'Status']
                current_borrower = df.loc[original_index, 'Borrower']
                current_cover = df.loc[original_index, 'Cover_URL'] # Assuming 'Cover_URL' column exists
                
                st.divider()
                
                # Layout: Image on Left, Form on Right
                col_img, col_form = st.columns([1, 2])
                
                with col_img:
                    if current_cover and str(current_cover).startswith("http"):
                         st.image(current_cover, width=120)
                    else:
                         st.write("📘 No Cover")
                
                with col_form:
                    st.subheader(selected_book)
                    with st.form("edit_loan"):
                        new_status = st.radio(
                            "Status", 
                            ["Available", "Borrowed", "Not Available"],
                            index=["Available", "Borrowed", "Not Available"].index(current_status) if current_status in ["Available", "Borrowed", "Not Available"] else 0
                        )
                        
                        new_borrower = st.text_input("Borrower Name", value=current_borrower)
                        
                        if st.form_submit_button("💾 Save Changes"):
                            try:
                                final_borrower = new_borrower if new_status == "Borrowed" else ""
                                sheet.update_cell(sheet_row_number, 4, new_status)
                                sheet.update_cell(sheet_row_number, 5, final_borrower)
                                st.success("Updated!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
