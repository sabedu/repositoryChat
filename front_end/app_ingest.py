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

    with st.expander("ℹ️ How to Use This App"):
        st.markdown("""
        **Setup Steps:**

        1. **Neo4j Instance:**
           - **Cloud:** [Neo4j Aura](https://neo4j.com/cloud/aura/) - Create a free or paid instance.
           - **Local:** Download and install from [Neo4j Download Center](https://neo4j.com/download-center/).

        2. **Obtain Neo4j Credentials:**
           - **URI:** e.g., `bolt://localhost:7687` or from Neo4j Aura dashboard.
           - **Username:** Typically `neo4j`.
           - **Password:** Set during Neo4j setup.

        3. **Generate GitHub Token:**
           - Go to GitHub **Settings > Developer settings > Personal access tokens > Tokens (classic) **.
           - Click **"Generate new token"**. 
           - Copy and save the token securely.

        4. **Permissions:**
           - Ensure the token has access to query GitHub's GraphQL API.

        **Using the App:**

        - Fill in the repository URL, GitHub token, and Neo4j credentials.
        - Click **"Ingest Data"** to start the process.
        """)

    st.session_state['ingest_successful'] = False
    st.session_state['messages'] = []

    with st.form("ingest_form"):
        repo_url = st.text_input("GitHub Repository URL", key='repo_url', value="")
        gh_token = st.text_input("GitHub Token", type="password", key='gh_token', value="")
        neo4j_uri = st.text_input("Neo4j URI", key='neo4j_uri', value="")
        neo4j_user = st.text_input("Neo4j User", key='neo4j_user', value="")
        neo4j_password = st.text_input("Neo4j Password", type="password", key='neo4j_password', value="")

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
