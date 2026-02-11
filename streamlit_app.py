import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import pandas as pd
from PIL import Image
from pyzbar.pyzbar import decode

st.set_page_config(page_title="Lumesta Library", page_icon="📚", layout="centered")

# --- 1. INITIALIZE SESSION ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'username' not in st.session_state: st.session_state['username'] = ""
if 'display_name' not in st.session_state: st.session_state['display_name'] = ""

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
    st.error(f"Database Connection Error: {e}")
    st.stop()

# --- 3. AUTHENTICATION LOGIC ---
def login_user(username, password):
    users = user_sheet.get_all_records()
    for user in users:
        if str(user['Username']).strip().lower() == username.strip().lower() and str(user['Password']) == str(password):
            return user['Name']
    return None

def signup_user(username, password, name):
    users = user_sheet.get_all_records()
    if any(str(u['Username']).strip().lower() == username.strip().lower() for u in users): return False
    user_sheet.append_row([username, password, name])
    return True

# --- 4. LOGIN / SIGNUP SCREEN ---
if not st.session_state['logged_in']:
    st.title("📚 Lumesta Library")
    t_log, t_sign = st.tabs(["Login", "Create Account"])
    with t_log:
        with st.form("login_form"):
            u, p = st.text_input("Username"), st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                res = login_user(u, p)
                if res:
                    st.session_state.update({"logged_in": True, "username": u.lower(), "display_name": res})
                    st.rerun()
                else: st.error("Invalid credentials.")
    with t_sign:
        with st.form("sign_form"):
            nu, np, nn = st.text_input("Username"), st.text_input("Password", type="password"), st.text_input("Full Name")
            if st.form_submit_button("Sign Up"):
                if nu and np and nn and signup_user(nu, np, nn):
                    st.session_state.update({"logged_in": True, "username": nu.lower(), "display_name": nn})
                    st.rerun()
                else: st.error("Error creating account.")
    st.stop()

# --- 5. RESTORED HYBRID SEARCH LOGIC ---
def search_books_hybrid(query):
    results = []
    clean_query = str(query).strip()
    is_isbn = clean_query.replace("-", "").isdigit()

    # Strategy A: Google Books
    try:
        url = f"https://www.googleapis.com/books/v1/volumes?q={clean_query}&maxResults=20"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if "items" in data:
                for item in data["items"]:
                    info = item.get("volumeInfo", {})
                    isbn = next((i["identifier"] for i in info.get("industryIdentifiers", []) if i["type"] == "ISBN_13"), "Unknown")
                    results.append({
                        "source": "Google",
                        "title": info.get("title", "Unknown"),
                        "author": ", ".join(info.get("authors", ["Unknown"])),
                        "cover": info.get("imageLinks", {}).get("thumbnail", ""),
                        "isbn": isbn,
                        "year": info.get("publishedDate", "")[:4]
                    })
    except: pass

    # Strategy B: Open Library (Backup & Parallel)
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
                    "isbn": isbn_clean,
                    "year": info.get("publish_date", "")
                })
        else:
            url = f"https://openlibrary.org/search.json?q={clean_query}&limit=20"
            resp = requests.get(url).json()
            for doc in resp.get("docs", []):
                cover_id = doc.get("cover_i")
                results.append({
                    "source": "OpenLibrary",
                    "title": doc.get("title", "Unknown"),
                    "author": ", ".join(doc.get("author_name", ["Unknown"])),
                    "cover": f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else "",
                    "isbn": doc.get("isbn", ["Unknown"])[0] if "isbn" in doc else "Unknown",
                    "year": str(doc.get("first_publish_year", ""))
                })
    except: pass

    # Deduplicate & Sort (Cover-First)
    seen = set()
    unique = []
    for b in results:
        fp = (b['title'].lower(), b['author'].lower())
        if fp not in seen:
            seen.add(fp)
            unique.append(b)
    unique.sort(key=lambda x: x['cover'] == "", reverse=False)
    return unique

# --- 6. MAIN APP INTERFACE ---
st.sidebar.title(f"Hi, {st.session_state['display_name']}!")
if st.sidebar.button("Logout"):
    st.session_state.update({"logged_in": False, "username": "", "display_name": ""})
    st.rerun()

st.title(f"{st.session_state['display_name']}'s Library")

tab1, tab2 = st.tabs(["➕ Add Books", "📋 My Collection"])

with tab1:
    st.subheader("Add to Your Collection")
    q = st.text_input("Search Title, Author, or ISBN")
    if st.button("Search Books", type="primary") and q:
        with st.spinner("Searching multiple libraries..."):
            st.session_state['s_res'] = search_books_hybrid(q)
    
    if 's_res' in st.session_state:
        st.write(f"Found {len(st.session_state['s_res'])} results:")
        for i, b in enumerate(st.session_state['s_res']):
            with st.container():
                c1, c2, c3 = st.columns([1, 3, 1])
                with c1: st.image(b['cover'], width=60) if b['cover'] else st.write("📘")
                with c2: 
                    st.markdown(f"**{b['title']}**")
                    st.caption(f"{b['author']} ({b['year']}) | Source: {b['source']}")
                with c3:
                    if st.button("Add", key=f"a_{i}"):
                        sheet.append_row([st.session_state['username'], b['isbn'], b['title'], b['author'], "Available", "", "", b['cover']])
                        st.toast(f"✅ Added {b['title']}!")
                st.divider()

with tab2:
    st.subheader("Manage Your Books")
    df = pd.DataFrame(sheet.get_all_records())
    if not df.empty and 'Owner' in df.columns:
        my_books = df[df['Owner'].astype(str).str.lower() == st.session_state['username']]
        if my_books.empty: st.info("No books yet.")
        else:
            f_txt = st.text_input("Quick Find in Collection:", placeholder="Type title...")
            d_books = my_books[my_books['Title'].astype(str).str.contains(f_txt, case=False)] if f_txt else my_books
            
            if not d_books.empty:
                sel = st.selectbox("Select book to edit:", d_books['Title'].tolist())
                match = df[(df['Title'] == sel) & (df['Owner'].astype(str).str.lower() == st.session_state['username'])]
                if not match.empty:
                    idx, row_num = match.index[0], match.index[0] + 2
                    st.divider()
                    colA, colB = st.columns([1, 2])
                    with colA:
                        cv = df.loc[idx, 'Cover_URL']
                        st.image(cv, width=120) if str(cv).startswith("http") else st.write("📘 No Cover")
                        st.write("---")
                        if st.button("🗑️ Delete Book", type="secondary"):
                            sheet.delete_rows(row_num)
                            st.warning(f"Removed '{sel}'")
                            st.rerun()
                    with colB:
                        with st.form("edit_loan"):
                            st.markdown(f"### {sel}")
                            st.caption(f"Author: {df.loc[idx, 'Author']}")
                            ns = st.radio("Status", ["Available", "Borrowed"], index=0 if df.loc[idx, 'Status']=="Available" else 1)
                            nb = st.text_input("Borrower Name", value=df.loc[idx, 'Borrower'])
                            if st.form_submit_button("Save Changes"):
                                sheet.update_cell(row_num, 5, ns)
                                sheet.update_cell(row_num, 6, nb if ns=="Borrowed" else "")
                                st.success("Updated!")
                                st.rerun()
            st.divider()
            st.subheader("Full Collection View")
            st.dataframe(my_books[['Title', 'Author', 'Status', 'Borrower']], use_container_width=True, hide_index=True)
