import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import pandas as pd

st.set_page_config(page_title="Lumesta Library", page_icon="📚")
st.title("📚 Lumesta Library")

# --- 1. CONNECT TO DATABASE ---
try:
    # Using the "Nuclear Option" secrets access
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
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Lumesta_Library").sheet1
    st.caption("✅ Database Connected")
except Exception as e:
    st.error(f"Database Error: {e}")
    st.stop()

# --- 2. THE SEARCH LOGIC (Google + OpenLibrary) ---
def search_google_books(query):
    # Try Google Books
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
    # Try Open Library (Backup)
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

# --- 3. THE APP INTERFACE ---
user_input = st.text_input("Enter ISBN or Title", "")

if st.button("Search"):
    if user_input:
        st.write(f"Searching for: **{user_input}**...")
        
        # clean the input
        clean_isbn = user_input.replace("-", "").strip()

        # Attempt 1: Google
        book = search_google_books(clean_isbn)
        
        # Attempt 2: Open Library (if Google failed)
        if not book and clean_isbn.isdigit():
            st.warning("Google didn't answer. Trying Open Library...")
            book = search_open_library(clean_isbn)

        # Result
        if book:
            st.success("Found it!")
            col1, col2 = st.columns([1, 3])
            with col1:
                if book['cover']:
                    st.image(book['cover'], width=100)
            with col2:
                st.subheader(book['title'])
                st.write(f"**Author:** {book['author']}")
            
            if st.button("Add to Library"):
                sheet.append_row([user_input, book['title'], book['author'], "Available", "", "", book['cover']])
                st.success("Saved!")
        else:
            st.error("❌ Not found in Google OR Open Library.")
            st.write("Debug Info: Please verify the number is correct.")
