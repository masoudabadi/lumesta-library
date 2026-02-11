import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import pandas as pd
from PIL import Image
from pyzbar.pyzbar import decode

st.set_page_config(page_title="Lumesta Library", page_icon="📚", layout="centered")

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
    
    # Open both tabs
    workbook = client.open("Lumesta_Library")
    sheet = workbook.sheet1 # The Library tab
    user_sheet = workbook.worksheet("Users") # The new Users tab
except Exception as e:
    st.error(f"Database Error: {e}")
    st.stop()

# --- 2. LOGIN LOGIC ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

def login_user(username, password):
    user_data = user_sheet.get_all_records()
    for row in user_data:
        if str(row['Username']).lower() == username.lower() and str(row['Password']) == str(password):
            st.session_state['logged_in'] = True
            st.session_state['username'] = username.lower()
            st.session_state['user_display_name'] = row['Name']
            return True
    return False

if not st.session_state['logged_in']:
    st.title("🔐 Lumesta Login")
    user = st.text_input("Username")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        if login_user(user, pwd):
            st.rerun()
        else:
            st.error("Invalid Username or Password")
    st.stop() # Stop everything else until they log in

# --- 3. APP HEADER (AFTER LOGIN) ---
st.title(f"📚 {st.session_state['user_display_name']}'s Library")
if st.sidebar.button("Logout"):
    st.session_state['logged_in'] = False
    st.rerun()

# --- 4. SEARCH LOGIC ---
def search_books_hybrid(query):
    results = []
    # (Existing search logic remains the same, but we return only unique results)
    search_url = f"https://openlibrary.org/search.json?q={query}&limit=10"
    try:
        resp = requests.get(search_url).json()
        for doc in resp.get("docs", []):
            cover_id = doc.get("cover_i")
            results.append({
                "title": doc.get("title", "Unknown"),
                "author": ", ".join(doc.get("author_name", ["Unknown"])),
                "cover": f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else "",
                "isbn": doc.get("isbn", ["Unknown"])[0] if "isbn" in doc else "Unknown"
            })
    except: pass
    return results

# --- 5. TABS ---
tab1, tab2 = st.tabs(["➕ Add Books", "📋 My Loan Desk"])

with tab1:
    query = st.text_input("Find a new book to add:")
    if st.button("Search"):
        results = search_books_hybrid(query)
        for i, book in enumerate(results):
            col1, col2, col3 = st.columns([1,3,1])
            with col1: st.image(book['cover'], width=50) if book['cover'] else st.write("📘")
            with col2: st.write(f"**{book['title']}**")
            with col3:
                if st.button("Add", key=f"add_{i}"):
                    # Column A is now 'Owner'
                    sheet.append_row([st.session_state['username'], book['isbn'], book['title'], book['author'], "Available", "", "", book['cover']])
                    st.toast("Saved!")

with tab2:
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    
    # FILTER: Only show books where 'Owner' matches the logged-in user
    if not df.empty and 'Owner' in df.columns:
        my_books = df[df['Owner'].astype(str).str.lower() == st.session_state['username']]
        
        if my_books.empty:
            st.info("Your library is currently empty.")
        else:
            search_own = st.text_input("Search your collection:")
            if search_own:
                my_books = my_books[my_books['Title'].str.contains(search_own, case=False)]
            
            selected = st.selectbox("Manage Book:", my_books['Title'].tolist())
            if selected:
                # Find row index in the ORIGINAL spreadsheet
                idx = df[df['Title'] == selected].index[0]
                row_num = idx + 2
                
                with st.form("edit"):
                    status = st.radio("Status", ["Available", "Borrowed"], index=0 if df.loc[idx, 'Status'] == "Available" else 1)
                    borrower = st.text_input("Borrower", value=df.loc[idx, 'Borrower'])
                    if st.form_submit_button("Update"):
                        sheet.update_cell(row_num, 5, status) # Col E is Status
                        sheet.update_cell(row_num, 6, borrower if status == "Borrowed" else "") # Col F is Borrower
                        st.success("Updated!")
                        st.rerun()
            st.dataframe(my_books[['Title', 'Author', 'Status', 'Borrower']])
