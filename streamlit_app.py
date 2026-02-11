import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import pandas as pd
from PIL import Image
from pyzbar.pyzbar import decode

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

# --- 6. BARCODE & SEARCH LOGIC ---
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
                isbn = "Unknown"
                for ident in info.get("industryIdentifiers", []):
                    if ident["type"] == "ISBN_13":
                        isbn = ident["identifier"]
                        break
                results.append({
                    "source": "Google",
                    "title": info.get("title", "Unknown"),
                    "author": ", ".join(info.get("authors", ["Unknown"])),
                    "cover": info.get("imageLinks", {}).get("thumbnail", ""),
                    "isbn": isbn
                })
    except: pass

    try:
        if is_isbn:
            isbn_clean = clean_query.replace("-", "")
            url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn_clean}&format=json&jscmd=data"
            resp = requests.get(url).json()
            key = f"ISBN:{isbn_clean}"
            if key in resp:
                info = resp[key]
                results.insert(0, {
                    "source": "OpenLibrary",
                    "title": info.get("title", "Unknown"),
                    "author": ", ".join([a["name"] for a in info.get("authors", [])]),
                    "cover": info.get("cover", {}).get("medium", ""),
                    "isbn": isbn_clean
                })
        else:
            url = f"https://openlibrary.org/search.json?q={clean_query}&limit=15"
            resp = requests.get(url).json()
            for doc in resp.get("docs", []):
                cover_id = doc.get("cover_i")
                results.append({
                    "source": "OpenLibrary",
                    "title": doc.get("title", "Unknown"),
                    "author": ", ".join(doc.get("author_name", ["Unknown"])),
                    "cover": f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else "",
                    "isbn": doc.get("isbn", ["Unknown"])[0] if "isbn" in doc else "Unknown"
                })
    except: pass

    seen = set()
    unique = []
    for b in results:
        fp = (b['title'].lower(), b['author'].lower())
        if fp not in seen:
            seen.add(fp); unique.append(b)
    return unique

# --- 7. TABS ---
tab1, tab2 = st.tabs(["➕ Add Books", "📋 My Collection"])

with tab1:
    st.subheader("Option A: Scan or Search")
    
    img_file = st.camera_input("Scan Barcode")
    scanned_code = ""
    if img_file:
        scanned_code = decode_barcode(img_file)
        if scanned_code:
            st.success(f"Scanned: {scanned_code}")
        else:
            st.warning("Barcode not found.")

    default_val = scanned_code if scanned_code else ""
    q = st.text_input("Title, Author, or ISBN", value=default_val)
    
    if st.button("Search Books", type="primary") and q:
        with st.spinner("Searching..."):
            st.session_state['s_res'] = search_books_hybrid(q)
    
    if 's_res' in st.session_state:
        for i, b in enumerate(st.session_state['s_res']):
            with st.container():
                c1, c2, c3 = st.columns([1, 3, 1])
                with c1:
                    if b['cover']: st.image(b['cover'], width=60)
                    else: st.write("📘")
                with c2: 
                    st.markdown(f"**{b['title']}**")
                    st.caption(f"{b['author']} | Source: {b['source']}")
                with c3:
                    if st.button("Add", key=f"a_{i}"):
                        sheet.append_row([st.session_state['username'], b['isbn'], b['title'], b['author'], "Available", "", "", b['cover']])
                        st.toast("✅ Added!")
                st.divider()

    # --- NEW MANUAL ADD SECTION ---
    st.write("---")
    with st.expander("Option B: Add Book Manually"):
        with st.form("manual_add_form"):
            m_title = st.text_input("Book Title*")
            m_author = st.text_input("Author Name*")
            m_isbn = st.text_input("ISBN (optional)")
            m_cover = st.text_input("Cover Image URL (optional)")
            
            if st.form_submit_button("Add Manually"):
                if m_title and m_author:
                    sheet.append_row([
                        st.session_state['username'], 
                        m_isbn if m_isbn else "N/A", 
                        m_title, 
                        m_author, 
                        "Available", 
                        "", 
                        "", 
                        m_cover
                    ])
                    st.success(f"Successfully added '{m_title}'!")
                else:
                    st.error("Title and Author are required.")

with tab2:
    st.subheader("Manage Your Books")
    df_raw = pd.DataFrame(sheet.get_all_records())
    
    if not df_raw.empty and 'Owner' in df_raw.columns:
        my_books = df_raw[df_raw['Owner'].astype(str).str.lower() == st.session_state['username']]
        
        if my_books.empty:
            st.info("No books yet.")
        else:
            f_txt = st.text_input("Filter list:", placeholder="Type title...")
            d_books = my_books[my_books['Title'].astype(str).str.contains(f_txt, case=False)] if f_txt else my_books
            
            if not d_books.empty:
                sel = st.selectbox("Select book:", d_books['Title'].tolist())
                match = df_raw[(df_raw['Title'] == sel) & (df_raw['Owner'].astype(str).str.lower() == st.session_state['username'])]
                
                if not match.empty:
                    idx = match.index[0]
                    row_num = idx + 2
                    
                    st.divider()
                    colA, colB = st.columns([1, 2])
                    with colA:
                        cv = df_raw.loc[idx, 'Cover_URL']
                        if str(cv).startswith("http"): st.image(cv, width=120)
                        else: st.write("📘 No Cover")
                        st.write("---")
                        if st.button("🗑️ Delete Book", type="secondary"):
                            sheet.delete_rows(row_num)
                            st.rerun()
                    with colB:
                        with st.form("edit_loan"):
                            st.markdown(f"### {sel}")
                            ns = st.radio("Status", ["Available", "Borrowed"], index=0 if df_raw.loc[idx, 'Status']=="Available" else 1)
                            nb = st.text_input("Borrower", value=df_raw.loc[idx, 'Borrower'])
                            if st.form_submit_button("Save Changes"):
                                sheet.update_cell(row_num, 5, ns)
                                sheet.update_cell(row_num, 6, nb if ns=="Borrowed" else "")
                                st.rerun()
            st.divider()
            st.dataframe(my_books[['Title', 'Author', 'Status', 'Borrower']], use_container_width=True, hide_index=True)
