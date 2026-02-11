import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import pandas as pd
from datetime import date

st.set_page_config(page_title="Lumesta Library", page_icon="📚")
st.title("📚 Lumesta Library")

# --- DEBUG MODE CONNECT ---
try:
    # We access the secrets DIRECTLY this time to avoid dictionary errors
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
    st.caption("✅ Connected to Google Sheets")
except Exception as e:
    st.error(f"❌ DATABASE ERROR: {e}")
    st.stop()

# --- SEARCH FUNCTION ---
def fetch_book_metadata(query):
    clean_query = str(query).replace("-", "").strip()
    
    # 1. Try Strict ISBN
    url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{clean_query}"
    try:
        response = requests.get(url)
        data = response.json()
        
        # 2. Try General Search if Strict fails
        if "items" not in data:
            url = f"https://www.googleapis.com/books/v1/volumes?q={clean_query}"
            response = requests.get(url)
            data = response.json()
            
        if "items" in data:
            volume_info = data["items"][0]["volumeInfo"]
            return {
                "title": volume_info.get("title", "Unknown Title"),
                "author": ", ".join(volume_info.get("authors", ["Unknown Author"])),
                "cover": volume_info.get("imageLinks", {}).get("thumbnail", "")
            }
        return None
    except Exception as e:
        st.error(f"Search API Error: {e}")
        return None

# --- UI ---
user_input = st.text_input("Enter ISBN or Title (e.g. 9780143038092)", "")

if st.button("Search"):
    if user_input:
        book = fetch_book_metadata(user_input)
        
        if book:
            st.image(book['cover'], width=120)
            st.subheader(book['title'])
            st.write(f"**Author:** {book['author']}")
            
            if st.button("Add to Library"):
                sheet.append_row([user_input, book['title'], book['author'], "Available", "", "", book['cover']])
                st.success("Added!")
        else:
            st.error(f"Not found: '{user_input}'. Try typing the title manually.")
