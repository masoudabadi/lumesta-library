import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import pandas as pd

# 1. SETUP PAGE
st.set_page_config(page_title="Lumesta Library", page_icon="📚")
st.title("📚 Lumesta Library")

# 2. CONNECT TO GOOGLE SHEET
# We use a "try/except" block to handle errors nicely
try:
    # We get the secrets from Streamlit's hidden vault
    creds_dict = dict(st.secrets["gcp_service_account"])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Lumesta_Library").sheet1
    st.success("Connected to Database ✅")
except Exception as e:
    st.error("Could not connect to Google Sheets. Check your Secrets!")
    st.stop()

# 3. HELPER FUNCTION (Get Book Info)
def fetch_book_metadata(isbn):
    url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
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

# 4. THE APP INTERFACE
tab1, tab2 = st.tabs(["➕ Add New Book", "📖 View Library"])

with tab1:
    st.header("Add a Book")
    isbn_input = st.text_input("Enter ISBN (Scan or Type)")

    if st.button("Search"):
        if isbn_input:
            book = fetch_book_metadata(isbn_input)
            if book:
                st.image(book['cover'], width=150)
                st.write(f"**Title:** {book['title']}")
                st.write(f"**Author:** {book['author']}")
                
                if st.button("Confirm Add"):
                    # Add to Google Sheet
                    sheet.append_row([isbn_input, book['title'], book['author'], "Available", "", "", book['cover']])
                    st.success(f"Added '{book['title']}' to library!")
            else:
                st.error("Book not found.")

with tab2:
    st.header("Your Collection")
    # Get all data from sheet
    data = sheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df)
    else:
        st.info("Library is empty.")
