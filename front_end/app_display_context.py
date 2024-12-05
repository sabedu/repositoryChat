import streamlit as st

def parse_context(context):
    """Function to parse the context into Query and Results."""
    query_text = ''
    results_text = ''

    if 'Results:' in context:
        query_part, results_part = context.split('Results:', 1)
    else:
        query_part = context
        results_part = ''

    if 'Query:' in query_part:
        query_text = query_part.split('Query:', 1)[1].strip()
    else:
        query_text = query_part.strip()

    results_text = results_part.strip()

    return query_text, results_text


def app_display_context(context):
    with st.expander("Context"):
        query_text, results_text = parse_context(context)
        st.subheader("Query:")
        st.code(query_text)
        st.subheader("Results:")
        st.write(results_text)