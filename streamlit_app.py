import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import pandas as pd
from datetime import date

# 1. SETUP PAGE
st.set_page_config(page_title="Lumesta Library", page_icon="📚")
st.title("📚 Lumesta Library")

# 2. CONNECT TO GOOGLE SHEET
try:
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
def fetch_book_metadata(query):
    # If query is all digits (ISBN), use ISBN search
    clean_query = query.replace("-", "").strip()
    
    if clean_query.isdigit():
        url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{clean_query}"
    else:
        # Otherwise search by title
        url = f"https://www.googleapis.com/books/v1/volumes?q=intitle:{query}"
        
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
    # Toggle between Automatic Search and Manual Entry
    add_mode = st.radio("How do you want to add the book?", ["Search (ISBN or Title)", "Manual Entry"], horizontal=True)
    
    if add_mode == "Search (ISBN or Title)":
        st.info("Tip: You can scan a barcode, type an ISBN (numbers only), or just type the Book Title!")
        # Camera Scanner
        scanned_code = st.camera_input("Scan Barcode (Optional)")
        
        # Text Input
        user_input = st.text_input("Enter ISBN or Title", value=scanned_code if scanned_code else "")

        if st.button("Search Book"):
            if user_input:
                book = fetch_book_metadata(user_input)
                if book:
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        if book['cover']:
                            st.image(book['cover'], width=100)
                    with col2:
                        st.subheader(book['title'])
                        st.write(f"**Author:** {book['author']}")
                    
                    if st.button("Confirm & Add to Library"):
                        today = date.today().strftime("%Y-%m-%d")
                        # Columns: ISBN, Title, Author, Status, Borrower, Due_Date, Cover_URL
                        sheet.append_row([user_input, book['title'], book['author'], "Available", "", "", book['cover']])
                        st.balloons()
                        st.success(f"Added '{book['title']}' to library!")
                else:
                    st.error("Book not found. Try 'Manual Entry' mode.")
            else:
                st.warning("Please enter an ISBN or Title.")

    else: # Manual Entry Mode
        with st.form("manual_add"):
            st.write("### Enter Book Details Manually")
            m_title = st.text_input("Book Title")
            m_author = st.text_input("Author")
            m_isbn = st.text_input("ISBN (Optional)")
            submitted = st.form_submit_button("Add Book")
            
            if submitted:
                if m_title and m_author:
                    sheet.append_row([m_isbn, m_title, m_author, "Available", "", "", ""])
                    st.success(f"Added '{m_title}' manually!")
                else:
                    st.error("Title and Author are required.")

with tab2:
    st.header("Your Collection")
    # Refresh button
    if st.button("Refresh Library"):
        st.rerun()
        
    data = sheet.get_all_records()
    if data:
        df = pd.DataFrame(data)
        # Show specific columns to keep it clean
        st.dataframe(df[['Title', 'Author', 'Status', 'Borrower']])
    else:
        st.info("Library is empty.")
