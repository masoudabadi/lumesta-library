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

# --- 2. HYBRID SEARCH LOGIC ---
def search_books_hybrid(query):
    found_books = []
    clean_query = str(query).strip()
    
    # STRATEGY A: Google Books (Best for Title/Author lists)
    try:
        url = f"https://www.googleapis.com/books/v1/volumes?q={clean_query}&maxResults=20"
        response = requests.get(url)
        data = response.json()
        
        if "items" in data:
            for item in data["items"]:
                info = item.get("volumeInfo", {})
                
                # Get ISBN safely
                isbn = "Unknown"
                for ident in info.get("industryIdentifiers", []):
                    if ident["type"] == "ISBN_13":
                        isbn = ident["identifier"]
                        break
                
                book = {
                    "source": "Google",
                    "title": info.get("title", "Unknown Title"),
                    "author": ", ".join(info.get("authors", ["Unknown Author"])),
                    "cover": info.get("imageLinks", {}).get("thumbnail", ""),
                    "isbn": isbn,
                    "published": info.get("publishedDate", "")[:4]
                }
                found_books.append(book)
    except:
        pass

    # STRATEGY B: Open Library (Backup for ISBNs)
    # Only runs if Google failed OR if the query looks like an ISBN
    if not found_books or clean_query.replace("-", "").isdigit():
        clean_isbn = clean_query.replace("-", "")
        try:
            url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{clean_isbn}&format=json&jscmd=data"
            response = requests.get(url)
            data = response.json()
            key = f"ISBN:{clean_isbn}"
            
            if key in data:
                info = data[key]
                book = {
                    "source": "OpenLibrary",
                    "title": info.get("title", "Unknown"),
                    "author": ", ".join([a["name"] for a in info.get("authors", [])]),
                    "cover": info.get("cover", {}).get("medium", ""),
                    "isbn": clean_isbn,
                    "published": info.get("publish_date", "")
                }
                # Add to the TOP of the list
                found_books.insert(0, book)
        except:
            pass
            
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

    # Search Button
    if st.button("Search", type="primary"):
        if user_query:
            with st.spinner(f"Searching for '{user_query
