import streamlit as st
import requests
import time

def ingest_data(gh_token):
    INGEST_URL = f"{st.secrets['BASE_URL']}/ingest"

    data = {
        "url": st.session_state['repo_url'],
        "neo4j_uri": st.session_state['neo4j_uri'],
        "neo4j_user": st.session_state['neo4j_user'],
        "neo4j_password": st.session_state['neo4j_password']
    }
    headers = {
        'Content-Type': 'application/json',
        'GH-Token': gh_token,
        'sessionId': st.session_state['session_id']
    }
    response = requests.post(INGEST_URL, json=data, headers=headers)
    return response

def ingest_screen():
    st.title("Ingest Your Data")

    st.session_state['ingest_successful'] = False
    st.session_state['messages'] = []

    with st.form("ingest_form"):
        st.session_state.repo_url = ""
        st.session_state.gh_token = ""
        st.session_state.neo4j_uri = ""
        st.session_state.neo4j_user = ""
        st.session_state.neo4j_password = ""
    
        repo_url = st.text_input("GitHub Repository URL", key='repo_url')
        gh_token = st.text_input("GitHub Token", type="password", key='gh_token')
        neo4j_uri = st.text_input("Neo4j URI", key='neo4j_uri')
        neo4j_user = st.text_input("Neo4j User", key='neo4j_user')
        neo4j_password = st.text_input("Neo4j Password", type="password", key='neo4j_password')

        submitted = st.form_submit_button("Ingest Data")
        if submitted:
            if not repo_url:
                st.error("Repository URL cannot be empty.")
            elif not gh_token:
                st.error("GitHub Token cannot be empty.")
            elif not neo4j_uri or not neo4j_user or not neo4j_password:
                st.error("All Neo4j fields must be filled.")
            else:
                with st.spinner("Ingesting data..."):
                    if repo_url == st.secrets.REPO_URL:
                        st.session_state['ingest_successful'] = True
                        st.rerun()
                    else:
                        response = ingest_data(gh_token)
                        if response.status_code == 200:
                            st.success("Data ingested successfully!")
                            st.session_state['ingest_successful'] = True
                            st.session_state['in_demo_mode'] = False
                            st.write("Session State after ingestion:", st.session_state)
                            st.rerun() 
                        else:
                            st.error(f"Ingest failed: {response.text}")
