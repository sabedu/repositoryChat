# app_chat.py
import streamlit as st
import requests
import time
from app_display_context import app_display_context

def chat_with_bot(model, query):
    CHAT_URL = f"{st.secrets['BASE_URL']}/chat"

    data = {
        "url": st.session_state['repo_url'],
        "neo4j_uri": st.session_state['neo4j_uri'],
        "neo4j_user": st.session_state['neo4j_user'],
        "neo4j_password": st.session_state['neo4j_password'],
        "session_id": st.session_state['session_id'],
        "query": query,
        'model': model,
        'learning_type': 'few-shot' if st.session_state.get('precision', False) else 'zero-shot'
    }
    headers = {
        'Content-Type': 'application/json',
        'Authorization': st.session_state.get('authorization', ''),
        'sessionId': st.session_state.session_id
    }
    response = requests.post(CHAT_URL, json=data, headers=headers)
    return response

def chat_screen():
    """Function to render the chat interface."""
    repo_url = st.session_state.get('repo_url', st.secrets.REPO_URL)
    repo_name = repo_url.split('/')[-1] if repo_url else "Demo Repository"
    st.title(f"Chatting with {repo_name}")

    _, col3_ = st.columns([0.4, 0.6])

    with col3_:
        if st.session_state.get('in_demo_mode', False):
            if st.button("Ingest Your Own Data"):
                st.session_state['demo_used'] = True
                st.session_state['ingest_successful'] = False  # Reset ingest status
                st.session_state['in_demo_mode'] = False
                st.rerun()
        else:
            token = st.text_input(
                label="Enter your OpenAI API key",
                type="password",
                label_visibility="visible",
                key="openai_api_key"
            )
            if token:
                st.session_state['authorization'] = token
            else:
                st.session_state['authorization'] = st.secrets.get('OPEN_AI_API_KEY', '')

    if 'messages' not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.markdown(message["content"])
            else:
                content = message["content"]
                context = message.get("context", "")
                st.markdown(content)
                app_display_context(context)

    query = st.chat_input("Enter your query:")

    if query:
        with st.chat_message("user"):
            st.markdown(query)
            st.session_state.messages.append(
                {"role": "user", "content": query, "query": "", 'result': "", 'context': ""}
            )

        model_mapping = {
            "GPT 3.5": "gpt-3.5-turbo",
            "GPT-4o": "gpt-4o",
            "Llama3": "llama3"
        }
        model = model_mapping.get(st.session_state.get("model_selection"), "gpt-4o")

        response = chat_with_bot(model, query)

        with st.chat_message("assistant"):
            if response.status_code == 200:
                result = response.json()
                bot_response = result.get('data', {}).get('response', 'No response found.')
                context = result.get('data', {}).get('context', '')
                assistant_placeholder = st.empty()
                partial_response = ""
                for char in bot_response:
                    partial_response += char
                    assistant_placeholder.markdown(partial_response)
                    time.sleep(0.005)
                app_display_context(context)
            else:
                st.error(f"Chat failed: {response.text}")
                bot_response = f"Error: {response.text}"
                context = ''

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": bot_response,
                    "context": context,
                    'query': query,
                    "result": result if response.status_code == 200 else {}
                }
            )
