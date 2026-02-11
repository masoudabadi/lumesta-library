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
    st.error(f"Database Error: {e}")
    st.stop()

# --- 3. AUTH LOGIC ---
def login_user(username, password):
    users = user_sheet.get_all_records()
    for user in users:
        if str(user['Username']).strip().lower() == username.strip().lower() and str(user['Password']) == str(password):
            return user['Name']
    return None

def signup_user(username, password, name):
    users = user_sheet.get_all_records()
    if any(str(user['Username']).strip().lower() == username.strip().lower() for user in users): return False
    user_sheet.append_row([username, password, name])
    return True

# --- 4. LOGIN SCREEN ---
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

# --- 5. MAIN APP ---
st.sidebar.title(f"Hi, {st.session_state['display_name']}!")
if st.sidebar.button("Logout"):
    st.session_state.update({"logged_in": False, "username": "", "display_name": ""})
    st.rerun()

st.title(f"{st.session_state['display_name']}'s Library")

def search_books_hybrid(query):
    results = []
    try:
        url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=15"
        data = requests.get(url).json()
        if "items" in data:
            for item in data["items"]:
                info = item.get("volumeInfo", {})
                isbn = next((i["identifier"] for i in info.get("industryIdentifiers", []) if i["type"] == "ISBN_13"), "Unknown")
                results.append({"title": info.get("title", "Unknown"), "author": ", ".join(info.get("authors", ["Unknown"])), "cover": info.get("imageLinks", {}).get("thumbnail", ""), "isbn": isbn})
    except: pass
    return results

tab1, tab2 = st.tabs(["➕ Add Books", "📋 My Collection"])

with tab1:
    q = st.text_input("Search Title, Author, or ISBN")
    if st.button("Search Books") and q: st.session_state['s_res'] = search_books_hybrid(q)
    if 's_res' in st.session_state:
        for i, b in enumerate(st.session_state['s_res']):
            with st.container():
                c1, c2, c3 = st.columns([1, 3, 1])
                with c1: st.image(b['cover'], width=60) if b['cover'] else st.write("📘")
                with c2: st.markdown(f"**{b['title']}**"); st.caption(b['author'])
                with c3:
                    if st.button("Add", key=f"a_{i}"):
                        sheet.append_row([st.session_state['username'], b['isbn'], b['title'], b['author'], "Available", "", "", b['cover']])
                        st.toast("Added!")
                st.divider()

with tab2:
    st.subheader("Manage Your Books")
    df = pd.DataFrame(sheet.get_all_records())
    if not df.empty and 'Owner' in df.columns:
        my_books = df[df['Owner'].astype(str).str.lower() == st.session_state['username']]
        if my_books.empty: st.info("No books yet.")
        else:
            f_txt = st.text_input("Quick Find:", placeholder="Type title...")
            d_books = my_books[my_books['Title'].astype(str).str.contains(f_txt, case=False)] if f_txt else my_books
            if not d_books.empty:
                sel = st.selectbox("Select book:", d_books['Title'].tolist())
                match = df[(df['Title'] == sel) & (df['Owner'].astype(str).str.lower() == st.session_state['username'])]
                if not match.empty:
                    idx, row_num = match.index[0], match.index[0] + 2
                    st.divider()
                    colA, colB = st.columns([1,2])
                    with colA:
                        cover_url = df.loc[idx, 'Cover_URL']
                        if str(cover_url).startswith("http"):
                            st.image(cover_url, width=120)
                        else: st.write("📘 No Cover")
                        
                        # DELETE BUTTON (New Feature)
                        st.write("---")
                        if st.button("🗑️ Delete Book", type="secondary", help="Remove this book permanently"):
                            sheet.delete_rows(row_num)
                            st.warning(f"Deleted '{sel}'")
                            st.rerun()

                    with colB:
                        with st.form("edit_status"):
                            st.markdown(f"### {sel}")
                            n_stat = st.radio("Status", ["Available", "Borrowed"], index=0 if df.loc[idx, 'Status']=="Available" else 1)
                            n_bor = st.text_input("Borrower Name", value=df.loc[idx, 'Borrower'])
                            if st.form_submit_button("Save Changes"):
                                sheet.update_cell(row_num, 5, n_stat)
                                sheet.update_cell(row_num, 6, n_bor if n_stat=="Borrowed" else "")
                                st.success("Updated!")
                                st.rerun()
            st.divider()
            st.subheader("Full Collection")
            st.dataframe(my_books[['Title', 'Author', 'Status', 'Borrower']], use_container_width=True, hide_index=True)
