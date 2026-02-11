import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import pandas as pd
from PIL import Image
from pyzbar.pyzbar import decode

st.set_page_config(page_title="Lumesta Library", page_icon="📚", layout="centered")

# --- 1. SAFETY BLOCK (Fixes the Error) ---
# We make sure these exist before doing ANYTHING else
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = ""
if 'display_name' not in st.session_state:
    st.session_state['display_name'] = ""

# --- 2. CONNECT TO DATABASE ---
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

# --- 3. AUTHENTICATION LOGIC ---
def login_user(username, password):
    users = user_sheet.get_all_records()
    for user in users:
        # Check matching username/password
        if str(user['Username']).strip().lower() == username.strip().lower() and str(user['Password']) == str(password):
            return user['Name']
    return None

def signup_user(username, password, name):
    users = user_sheet.get_all_records()
    for user in users:
        if str(user['Username']).strip().lower() == username.strip().lower():
            return False # User already exists
    user_sheet.append_row([username, password, name])
    return True

# --- 4. LOGIN SCREEN (Gatekeeper) ---
if not st.session_state['logged_in']:
    st.title("📚 Lumesta Library")
    
    tab_login, tab_signup = st.tabs(["Login", "Create Account"])
    
    with tab_login:
        with st.form("login_form"):
            user_in = st.text_input("Username")
            pass_in = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                name_found = login_user(user_in, pass_in)
                if name_found:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = user_in.lower()
                    st.session_state['display_name'] = name_found
                    st.rerun()
                else:
                    st.error("Incorrect username or password.")

    with tab_signup:
        with st.form("signup_form"):
            new_user = st.text_input("Choose Username")
            new_pass = st.text_input("Choose Password", type="password")
            new_name = st.text_input("Full Name (e.g. Masoud)")
            if st.form_submit_button("Sign Up"):
                if new_user and new_pass and new_name:
                    if signup_user(new_user, new_pass, new_name):
                        st.success("Account created! logging in...")
                        st.session_state['logged_in'] = True
                        st.session_state['username'] = new_user.lower()
                        st.session_state['display_name'] = new_name
                        st.rerun()
                    else:
                        st.error("Username taken.")
                else:
                    st.warning("Fill all fields.")
    
    st.stop() # CRITICAL: Stop here if not logged in

# --- 5. MAIN APP (Only runs if Logged In) ---

# Sidebar Logout
st.sidebar.title(f"Hi, {st.session_state['display_name']}!")
if st.sidebar.button("Logout"):
    st.session_state['logged_in'] = False
    st.session_state['username'] = ""
    st.session_state['display_name'] = ""
    st.rerun()

st.title(f"{st.session_state['display_name']}'s Library")

# --- HELPER: SEARCH FUNCTION ---
def search_books_hybrid(query):
    results = []
    # Google Books
    try:
        url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=15"
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
    
    # Deduplicate
    unique = []
    seen = set()
    for r in results:
        fp = r['title'].lower()
        if fp not in seen:
            seen.add(fp)
            unique.append(r)
    return unique

# --- TABS ---
tab1, tab2 = st.tabs(["➕ Add Books", "📋 My Collection"])

# Tab 1: Add
with tab1:
    st.subheader("Add to Your Collection")
    query = st.text_input("Search Title, Author, or ISBN")
    if st.button("Search Books"):
        if query:
            st.session_state['search_results'] = search_books_hybrid(query)

    if 'search_results' in st.session_state:
        for i, book in enumerate(st.session_state['search_results']):
            with st.container():
                c1, c2, c3 = st.columns([1, 3, 1])
                with c1:
                    st.image(book['cover'], width=60) if book['cover'] else st.write("📘")
                with c2:
                    st.markdown(f"**{book['title']}**")
                    st.caption(book['author'])
                with c3:
                    if st.button("Add", key=f"add_{i}"):
                        sheet.append_row([
                            st.session_state['username'], 
                            book['isbn'], 
                            book['title'], 
                            book['author'], 
                            "Available", 
                            "", 
                            "", 
                            book['cover']
                        ])
                        st.toast(f"Added to {st.session_state['display_name']}'s list!")
                st.divider()

# Tab 2: Manage
with tab2:
    st.subheader("Manage Your Books")
    all_data = sheet.get_all_records()
    df = pd.DataFrame(all_data)

    # Filter by Owner
    if not df.empty and 'Owner' in df.columns:
        my_books = df[df['Owner'].astype(str).str.lower() == st.session_state['username']]
        
        if my_books.empty:
            st.info("No books yet.")
        else:
            # Filter
            filter_txt = st.text_input("Filter your list:", placeholder="Type title...")
            if filter_txt:
                my_books = my_books[my_books['Title'].astype(str).str.contains(filter_txt, case=False)]

            # Selector
            titles = my_books['Title'].tolist()
            if titles:
                sel = st.selectbox("Select book to edit:", titles)
                
                # Find EXACT row match (Owner + Title)
                mask = (df['Title'] == sel) & (df['Owner'].astype(str).str.lower() == st.session_state['username'])
                if not df[mask].empty:
                    idx = df[mask].index[0]
                    row_num = idx + 2 # Header is 1, index starts at 0

                    cur_status = df.loc[idx, 'Status']
                    cur_borrower = df.loc[idx, 'Borrower']
                    cur_cover = df.loc[idx, 'Cover_URL'] if 'Cover_URL' in df.columns else ""

                    st.divider()
                    colA, colB = st.columns([1,2])
                    with colA:
                        if str(cur_cover).startswith("http"):
                            st.image(cur_cover, width=100)
                        else: st.write("📘")
                    
                    with colB:
                        with st.form("edit_status"):
                            st.markdown(f"**{sel}**")
                            new_stat = st.radio("Status", ["Available", "Borrowed"], index=0 if cur_status=="Available" else 1)
                            new_bor = st.text_input("Borrower Name", value=cur_borrower)
                            if st.form_submit_button("Save"):
                                sheet.update_cell(row_num, 5, new_stat) # Col E
                                sheet.update_cell(row_num, 6, new_bor if new_stat=="Borrowed" else "") # Col F
                                st.success("Updated!")
                                st.rerun()
