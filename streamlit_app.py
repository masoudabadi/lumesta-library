import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import pandas as pd
from datetime import date

# 1. SETUP
st.set_page_config(page_title="Lumesta Library", page_icon="📚")
st.title("📚 Lumesta Library")

# 2. CONNECT TO DATABASE
try:
    creds_dict = dict(st.secrets["gcp_service_account"])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Lumesta_Library").sheet1
except Exception as e:
    st.error("Database Connection Error. Check Secrets.")
    st.stop()

# 3. SMARTER SEARCH FUNCTION
def fetch_book_metadata(query):
    # Step A: Clean the input
    clean_query = str(query).replace("-", "").strip()
    
    # Step B: Try Strict ISBN Search
    url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{clean_query}"
    response = requests.get(url)
    data = response.json()
    
    # Step C: If strict fails, try General Search (The Fallback)
    if "items" not in data:
        st.caption(f"Strict search failed for '{clean_query}'. Trying general search...")
        url = f"https://www.googleapis.com/books/v1/volumes?q={clean_query}"
        response = requests.get(url)
        data = response.json()
    
    # Step D: Process Result
    if "items" in data:
        volume_info = data["items"][0]["volumeInfo"]
        return {
            "title": volume_info.get("title", "Unknown Title"),
            "author": ", ".join(volume_info.get("authors", ["Unknown Author"])),
            "cover": volume_info.get("imageLinks", {}).get("thumbnail", "")
        }
    return None

# 4. APP INTERFACE
tab1, tab2 = st.tabs(["➕ Add New Book", "📖 View Library"])

with tab1:
    st.write("### Add a Book")
    
    # Simple Input Box
    user_input = st.text_input("Enter ISBN or Book Title")

    if st.button("Search"):
        if user_input:
            with st.spinner(f"Searching for '{user_input}'..."):
                book = fetch_book_metadata(user_input)
                
            if book:
                col1, col2 = st.columns([1, 3])
                with col1:
                    if book['cover']:
                        st.image(book['cover'], width=100)
                with col2:
                    st.subheader(book['title'])
                    st.write(f"**Author:** {book['author']}")
                
                if st.button("Confirm Add"):
                    sheet.append_row([user_input, book['title'], book['author'], "Available", "", "", book['cover']])
                    st.balloons()
                    st.success(f"Added '{book['title']}'!")
            else:
                st.error(f"Could not find any book matching '{user_input}'. Try typing the title manually.")
                
                # Manual Fallback
                with st.expander("Enter Details Manually"):
                    with st.form("manual_fail"):
                        m_title = st.text_input("Title")
                        m_author = st.text_input("Author")
                        if st.form_submit_button("Save Manual Entry"):
                            sheet.append_row([user_input, m_title, m_author, "Available", "", "", ""])
                            st.success("Saved manually!")
