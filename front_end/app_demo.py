import streamlit as st
from app_chat import chat_screen

def demo_screen():
    st.title("This is Demo Interaction!")

    repo_name = st.secrets.REPO_URL.split('/')[-1]
    st.write(f"You can interact with the {repo_name} project. This is the pre-ingested project for demonstration.")

    if st.button("Start Demo Chat"):
        st.session_state['repo_url'] = st.secrets.REPO_URL
        st.session_state['neo4j_uri'] = st.secrets.NEO4J_URI
        st.session_state['neo4j_user'] = st.secrets.NEO4J_USER
        st.session_state['neo4j_password'] = st.secrets.NEO4J_PASSWORD
        st.session_state['authorization'] = st.secrets.OPEN_AI_API_KEY
        st.session_state['ingest_successful'] = True
        st.session_state['demo_used'] = True
        st.session_state['in_demo_mode'] = True
        st.rerun()

    st.write("Or you can ingest your own data.")

    if st.button("Ingest Your Own Data"):
        st.session_state['demo_used'] = True 
        st.session_state['in_demo_mode'] = False
        st.rerun()
