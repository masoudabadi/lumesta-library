import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import pandas as pd
from PIL import Image
from pyzbar.pyzbar import decode
import numpy as np

st.set_page_config(page_title="Lumesta Library", page_icon="📚")
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

# --- 2. FUNCTIONS ---
def search_google_books(query):
    url = f"https://www.googleapis.com/books/v1/volumes?q={query}"
    try:
        response = requests.get(url)
        data = response.json()
        if "items" in data:
            info = data["items"][0]["volumeInfo"]
            return {
                "title": info.get("title", "Unknown"),
                "author": ", ".join(info.get("authors", ["Unknown"])),
                "cover": info.get("imageLinks", {}).get("thumbnail", "")
            }
    except:
        pass
    return None

def search_open_library(isbn):
    url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
    try:
        response = requests.get(url)
        data = response.json()
        key = f"ISBN:{isbn}"
        if key in data:
            info = data[key]
            return {
                "title": info.get("title", "Unknown"),
                "author": ", ".join([a["name"] for a in info.get("authors", [])]),
                "cover": info.get("cover", {}).get("medium", "")
            }
    except:
        pass
    return None

def decode_barcode(image_file):
    try:
        image = Image.open(image_file)
        decoded_objects = decode(image)
        for obj in decoded_objects:
            # Look for ISBNs (EAN13)
            if obj.type == 'EAN13' or obj.type == 'ISBN13':
                return obj.data.decode('utf-8')
    except Exception as e:
        st.error(f"Camera Error: {e}")
    return None

# --- 3. APP INTERFACE ---
tab1, tab2 = st.tabs(["➕ Add New Book", "📖 View Library"])

with tab1:
    st.write("### Step 1: Get the ISBN")
    
    # A. CAMERA INPUT
    img_file = st.camera_input("Scan Barcode (Optional)")
    scanned_code = ""
    
    if img_file:
        scanned_code = decode_barcode(img_file)
        if scanned_code:
            st.success(f"Scanned: {scanned_code}")
        else:
            st.warning("Could not read barcode. Try getting closer or clearer lighting.")

    # B. MANUAL INPUT (Auto-filled if scanned)
    # We use 'value=' to fill it if the camera worked
    user_input = st.text_input("ISBN or Title", value=scanned_code if scanned_code else "")
    
    st.write("### Step 2: Search & Save")
    if st.button("Search"):
        if user_input:
            clean_isbn = user_input.replace("-", "").strip()
            
            with st.spinner("Searching..."):
                book = search_google_books(clean_isbn)
                if not book and clean_isbn.isdigit():
                    book = search_open_library(clean_isbn)

            if book:
                # Save to session state
                st.session_state['current_book'] = book
                st.session_state['current_isbn'] = user_input
            else:
                st.error("❌ Not found.")

    # Result Display
    if 'current_book' in st.session_state:
        book = st.session_state['current_book']
        st.info("Found it!")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            if book['cover']:
                st.image(book['cover'], width=100)
        with col2:
            st.subheader(book['title'])
            st.write(f"**Author:** {book['author']}")
        
        if st.button("Confirm Add to Library"):
            try:
                sheet.append_row([
                    st.session_state['current_isbn'], 
                    book['title'], 
                    book['author'], 
                    "Available", 
                    "", 
                    "", 
                    book['cover']
                ])
                st.success("✅ Saved!")
                del st.session_state['current_book']
            except Exception as e:
                st.error(f"Save Error: {e}")

with tab2:
    if st.button("Refresh List"):
        st.rerun()
    
    data = sheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df)
    else:
        st.info("Library is empty.")
