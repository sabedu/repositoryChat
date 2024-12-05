import streamlit as st
import uuid
from app_ingest import ingest_screen
from app_chat import chat_screen
from app_demo import demo_screen

st.set_page_config(page_title="Chatbot Interface", layout="centered")

if 'ingest_successful' not in st.session_state:
    st.session_state['ingest_successful'] = False

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "repo_url" not in st.session_state:
    st.session_state.repo_url = ""

if "in_demo_mode" not in st.session_state:
    st.session_state.in_demo_mode = False

def main():
    if not st.session_state.get('demo_used', False) and not st.session_state['ingest_successful']:
        demo_screen() 
    elif not st.session_state['ingest_successful']:
        ingest_screen()
    else:
        for k, v in st.session_state.items():
            st.session_state[k] = v
        chat_screen()

if __name__ == '__main__':
    main()
