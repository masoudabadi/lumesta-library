import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import pandas as pd
from PIL import Image
from pyzbar.pyzbar import decode
from datetime import datetime

st.set_page_config(page_title="Lumesta Library", page_icon="📚", layout="centered")

# --- 1. SESSION INITIALIZATION ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = ""
if 'display_name' not in st.session_state:
    st.session_state['display_name'] = ""

# --- 2. DATABASE CONNECTION ---
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

# --- 3. AUTH FUNCTIONS ---
def login_user(username, password):
    users = user_sheet.get_all_records()
    for user in users:
        if str(user['Username']).strip().lower() == username.strip().lower() and str(user['Password']) == str(password):
            return user['Name']
    return None

def signup_user(username, password, name):
    users = user_sheet.get_all_records()
    if any(str(u['Username']).strip().lower() == username.strip().lower() for u in users):
        return False
    user_sheet.append_row([username, password, name])
    return True

# --- 4. ACCESS CONTROL ---
if not st.session_state['logged_in']:
    st.title("📚 Lumesta Library")
    t_log, t_sign = st.tabs(["Login", "Create Account"])
    with t_log:
        with st.form("login_form"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                res = login_user(u, p)
                if res:
                    st.session_state.update({"logged_in": True, "username": u.lower(), "display_name": res})
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
    with t_sign:
        with st.form("sign_form"):
            nu = st.text_input("Username")
            np = st.text_input("Password", type="password")
            nn = st.text_input("Full Name")
            if st.form_submit_button("Sign Up"):
                if nu and np and nn and signup_user(nu, np, nn):
                    st.session_state.update({"logged_in": True, "username": nu.lower(), "display_name": nn})
                    st.rerun()
                else:
                    st.error("Error creating account.")
    st.stop()

# --- 5. LOGGED-IN NAVIGATION ---
st.sidebar.title(f"Hi, {st.session_state['display_name']}!")
if st.sidebar.button("Logout"):
    st.session_state.update({"logged_in": False, "username": "", "display_name": ""})
    st.rerun()

st.title(f"{st.session_state['display_name']}'s Library")

# --- 6. SEARCH LOGIC ---
def decode_barcode(image_file):
    try:
        image = Image.open(image_file)
        decoded_objects = decode(image)
        for obj in decoded_objects:
            if obj.type in ['EAN13', 'ISBN13']:
                return obj.data.decode('utf-8')
    except: pass
    return None

def search_books_hybrid(query):
    results = []
    clean_query = str(query).strip()
    is_isbn = clean_query.replace("-", "").isdigit()
    try:
        url = f"https://www.googleapis.com/books/v1/volumes?q={clean_query}&maxResults=15"
        data = requests.get(url).json()
        if "items" in data:
            for item in data["items"]:
                info = item.get("volumeInfo", {})
                isbn = next((i["identifier"] for i in info.get("industryIdentifiers", []) if i["type"] == "ISBN_13"), "Unknown")
                results.append({"title": info.get("title", "Unknown"), "author": ", ".join(info.get("authors", ["Unknown"])), "cover": info.get("imageLinks", {}).get("thumbnail", ""), "isbn": isbn})
    except: pass
    try:
        if is_isbn:
            isbn_clean = clean_query.replace("-", "")
            url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn_clean}&format=json&jscmd=data"
            resp = requests.get(url).json()
            key = f"ISBN:{isbn_clean}"
            if key in resp:
                info = resp[key]
                results.insert(0, {"title": info.get("title", "Unknown"), "author": ", ".join([a["name"] for a in info.get("authors", [])]), "cover": info.get("cover", {}).get("medium", ""), "isbn": isbn_clean})
        else:
            url = f"https://openlibrary.org/search.json?q={clean_query}&limit=15"
            resp = requests.get(url).json()
            for doc in resp.get("docs", []):
                cover_id = doc.get("cover_i")
                results.append({"title": doc.get("title", "Unknown"), "author": ", ".join(doc.get("author_name", ["Unknown"])), "cover": f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else "", "isbn": doc.get("isbn", ["Unknown"])[0] if "isbn" in doc else "Unknown"})
    except: pass
    seen = set()
    unique = []
    for b in results:
        fp = (b['title'].lower(), b['author'].lower())
        if fp not in seen:
            seen.add(fp); unique.append(b)
    return unique

# --- 7. TABS ---
tab1, tab3, tab2 = st.tabs(["➕ Add Books", "🍽️ On My Plate", "📋 My Collection"])

with tab1:
    st.subheader("Add by Scan or Search")
    img_file = st.camera_input("Scan Barcode")
    scanned = decode_barcode(img_file) if img_file else ""
    if scanned: st.success(f"Scanned: {scanned}")
    q = st.text_input("Title, Author, or ISBN", value=scanned if scanned else "")
    if st.button("Search Books", type="primary") and q:
        with st.spinner("Searching..."):
            st.session_state['s_res'] = search_books_hybrid(q)
    if 's_res' in st.session_state:
        for i, b in enumerate(st.session_state['s_res']):
            with st.container():
                c1, c2, c3 = st.columns([1, 3, 1])
                with c1: st.image(b['cover'], width=60) if b['cover'] else st.write("📘")
                with c2: st.markdown(f"**{b['title']}**"); st.caption(b['author'])
                with c3:
                    if st.button("Add", key=f"a_{i}"):
                        sheet.append_row([st.session_state['username'], b['isbn'], b['title'], b['author'], "Available", "", "", b['cover'], ""])
                        st.toast("✅ Added!")
                st.divider()
    with st.expander("Add Book Manually"):
        with st.form("manual_add"):
            mt, ma = st.text_input("Title*"), st.text_input("Author*")
            if st.form_submit_button("Save"):
                if mt and ma:
                    sheet.append_row([st.session_state['username'], "N/A", mt, ma, "Available", "", "", "", ""])
                    st.success("Added!")
                else: st.error("Missing fields.")

with tab3:
    st.header("Active Reading")
    raw_df = pd.DataFrame(sheet.get_all_records())
    if not raw_df.empty and 'Owner' in raw_df.columns:
        reading = raw_df[(raw_df['Owner'].astype(str).str.lower() == st.session_state['username']) & (raw_df['Status'] == "Reading")]
        if reading.empty: st.info("No active books.")
        else:
            prog_vals = ["10% or less", "20%", "30%", "40%", "Half way there", "60%", "70%", "80%", "Almost done", "Finished"]
            for idx, row in reading.iterrows():
                with st.container():
                    cA, cB = st.columns([1, 3])
                    with cA: st.image(row['Cover_URL'], width=80) if str(row['Cover_URL']).startswith("http") else st.write("📖")
                    with cB:
                        st.subheader(row['Title'])
                        cur_p = row['Reading_Progress'] if row['Reading_Progress'] in prog_vals else "10% or less"
                        with st.form(f"p_form_{idx}"):
                            new_p = st.selectbox("Progress", prog_vals, index=prog_vals.index(cur_p))
                            if st.form_submit_button("Save"):
                                row_num = idx + 2
                                if new_p == "Finished":
                                    sheet.update_cell(row_num, 5, "Available"); sheet.update_cell(row_num, 9, "")
                                else: sheet.update_cell(row_num, 9, new_p)
                                st.rerun()
                st.divider()

with tab2:
    st.subheader("Manage Your Books")
    df = pd.DataFrame(sheet.get_all_records())
    if not df.empty and 'Owner' in df.columns:
        my_books = df[df['Owner'].astype(str).str.lower() == st.session_state['username']]
        if not my_books.empty:
            f = st.text_input("Filter list:", placeholder="Type title...")
            d_books = my_books[my_books['Title'].astype(str).str.contains(f, case=False)] if f else my_books
            if not d_books.empty:
                sel = st.selectbox("Select book:", d_books['Title'].tolist())
                match = df[(df['Title'] == sel) & (df['Owner'].astype(str).str.lower() == st.session_state['username'])]
                if not match.empty:
                    idx, row_n = match.index[0], match.index[0] + 2
                    st.divider()
                    col_i, col_f = st.columns([1, 2])
                    with col_i:
                        cv = df.loc[idx, 'Cover_URL']
                        st.image(cv, width=120) if str(cv).startswith("http") else st.write("📘 No Cover")
                        st.write("---")
                        if st.button("🗑️ Delete Book"):
                            sheet.delete_rows(row_n); st.rerun()
                    with col_f:
                        # !!! REACTIVE STATUS RADIO (Outside the form) !!!
                        current_db_status = df.loc[idx, 'Status']
                        status_options = ["Available", "Borrowed", "Reading"]
                        
                        new_status = st.radio(
                            "Status", 
                            status_options, 
                            index=status_options.index(current_db_status) if current_db_status in status_options else 0
                        )
                        
                        # These fields now react INSTANTLY to the radio button above
                        is_borrowed = (new_status == "Borrowed")
                        
                        with st.form("loan_form"):
                            st.markdown(f"### {sel}")
                            
                            n_borrower = st.text_input("Borrower", value=df.loc[idx, 'Borrower'], disabled=not is_borrowed)
                            
                            try:
                                default_date = datetime.strptime(str(df.loc[idx, 'Due_Date']), "%Y-%m-%d").date()
                            except:
                                default_date = datetime.now().date()
                            
                            n_due = st.date_input("Due Date", value=default_date, disabled=not is_borrowed)
                            
                            if st.form_submit_button("Save Changes"):
                                sheet.update_cell(row_n, 5, new_status)
                                sheet.update_cell(row_n, 6, n_borrower if is_borrowed else "")
                                sheet.update_cell(row_n, 7, str(n_due) if is_borrowed else "")
                                if new_status == "Reading": sheet.update_cell(row_n, 9, "10% or less")
                                st.rerun()
            st.divider()
            st.dataframe(my_books[['Title', 'Author', 'Status', 'Borrower', 'Due_Date', 'Reading_Progress']], use_container_width=True, hide_index=True)
