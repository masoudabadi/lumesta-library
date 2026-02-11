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
    
    workbook = client.open("Lumesta_Library")
    sheet = workbook.sheet1
    user_sheet = workbook.worksheet("Users")
except Exception as e:
    st.error(f"Database Error: {e}")
    st.stop()

# --- 2. AUTHENTICATION SYSTEM ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

def login_user(username, password):
    users = user_sheet.get_all_records()
    for user in users:
        if str(user['Username']).strip().lower() == username.strip().lower() and str(user['Password']) == str(password):
            return user['Name']
    return None

def signup_user(username, password, name):
    users = user_sheet.get_all_records()
    # Check if username exists
    for user in users:
        if str(user['Username']).strip().lower() == username.strip().lower():
            return False # User exists
    
    # Add new user
    user_sheet.append_row([username, password, name])
    return True

# --- LOGIN / SIGNUP SCREEN ---
if not st.session_state['logged_in']:
    st.title("📚 Lumesta Library")
    
    tab_login, tab_signup = st.tabs(["Login", "Create Account"])
    
    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                user_name = login_user(username, password)
                if user_name:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = username.lower()
                    st.session_state['display_name'] = user_name
                    st.success(f"Welcome back, {user_name}!")
                    st.rerun()
                else:
                    st.error("Incorrect username or password.")

    with tab_signup:
        with st.form("signup_form"):
            new_user = st.text_input("Choose a Username")
            new_pass = st.text_input("Choose a Password", type="password")
            new_name = st.text_input("Your Full Name (e.g. Jackie)")
            submit_signup = st.form_submit_button("Sign Up")
            
            if submit_signup:
                if new_user and new_pass and new_name:
                    if signup_user(new_user, new_pass, new_name):
                        st.success("Account created! Logging you in...")
                        st.session_state['logged_in'] = True
                        st.session_state['username'] = new_user.lower()
                        st.session_state['display_name'] = new_name
                        st.rerun()
                    else:
                        st.error("That username is already taken.")
                else:
                    st.warning("Please fill in all fields.")
    
    st.stop() # Stop here if not logged in

# --- 3. MAIN APP (LOGGED IN) ---
st.sidebar.title(f"Hi, {st.session_state['display_name']}!")
if st.sidebar.button("Logout"):
    st.session_state['logged_in'] = False
    st.rerun()

st.title(f"{st.session_state['display_name']}'s Library")

# --- SEARCH FUNCTION ---
def search_books_hybrid(query):
    results = []
    try:
        url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=10"
        data = requests.get(url).json()
        if "items" in data:
            for item in data["items"]:
                info = item.get("volumeInfo", {})
                isbn = "Unknown"
                for ident in info.get("industryIdentifiers", []):
                    if ident["type"] == "ISBN_13":
                        isbn = ident["identifier"]
                        break
                results.append({
                    "title": info.get("title", "Unknown"),
                    "author": ", ".join(info.get("authors", ["Unknown"])),
                    "cover": info.get("imageLinks", {}).get("thumbnail", ""),
                    "isbn": isbn
                })
    except: pass
    return results

# --- APP TABS ---
tab1, tab2 = st.tabs(["➕ Add Books", "📋 My Collection"])

with tab1:
    st.subheader("Add to Your Collection")
    query = st.text_input("Search by Title, Author, or ISBN")
    if st.button("Search Books"):
        if query:
            results = search_books_hybrid(query)
            st.session_state['search_results'] = results
    
    if 'search_results' in st.session_state:
        for i, book in enumerate(st.session_state['search_results']):
            with st.container():
                c1, c2, c3 = st.columns([1, 3, 1])
                with c1: st.image(book['cover'], width=60) if book['cover'] else st.write("📘")
                with c2: 
                    st.write(f"**{book['title']}**")
                    st.caption(book['author'])
                with c3:
                    if st.button("Add", key=f"add_{i}"):
                        # Adds the book with the CURRENT USER'S username
                        sheet.append_row([st.session_state['username'], book['isbn'], book['title'], book['author'], "Available", "", "", book['cover']])
                        st.toast(f"Added to {st.session_state['display_name']}'s list!")
                st.divider()

with tab2:
    st.subheader("Manage Your Books")
    
    # 1. Get All Data
    all_data = sheet.get_all_records()
    df = pd.DataFrame(all_data)
    
    # 2. Filter for CURRENT USER only
    # We check if 'Owner' column exists first to avoid errors
    if not df.empty and 'Owner' in df.columns:
        my_books = df[df['Owner'].astype(str).str.lower() == st.session_state['username']]
        
        if my_books.empty:
            st.info("You haven't added any books yet.")
        else:
            # Search Filter
            filter_text = st.text_input("Filter your books:", placeholder="Type a title...")
            if filter_text:
                my_books = my_books[my_books['Title'].astype(str).str.contains(filter_text, case=False)]
            
            # Book Selection
            book_titles = my_books['Title'].tolist()
            if book_titles:
                selected_title = st.selectbox("Select a book to edit:", book_titles)
                
                # Find the row in the ORIGINAL dataframe (to get the right Index)
                # We filter the original DF to find the row where Title matches AND Owner matches
                # This prevents editing someone else's book if they have the same title
                row_match = df[(df['Title'] == selected_title) & (df['Owner'].astype(str).str.lower() == st.session_state['username'])]
                
                if not row_match.empty:
                    idx = row_match.index[0]
                    sheet_row = idx + 2
                    
                    current_status = df.loc[idx, 'Status']
                    current_borrower = df.loc[idx, 'Borrower']
                    current_cover = df.loc[idx, 'Cover_URL'] if 'Cover_URL' in df.columns else ""

                    st.divider()
                    col_a, col_b = st.columns([1, 2])
                    
                    with col_a:
                        if str(current_cover).startswith("http"):
                            st.image(current_cover, width=100)
                        else:
                            st.write("📘")
                    
                    with col_b:
                        with st.form("update_status"):
                            st.write(f"**{selected_title}**")
                            new_status = st.radio("Status", ["Available", "Borrowed"], index=0 if current_status == "Available" else 1)
                            new_borrower = st.text_input("Borrower Name", value=current_borrower)
                            
                            if st.form_submit_button("Save Changes"):
                                sheet.update_cell(sheet_row, 5, new_status) # Col E
                                sheet.update_cell(sheet_row, 6, new_borrower if new_status == "Borrowed" else "") # Col F
                                st.success("Updated!")
                                st.rerun()
