from scripts.kg_chat import KGChat
from logging import getLogger

logger = getLogger(__name__)


def generate_response(repo_url, user_input, learning_type, session_id, api_key, model, neo4j_uri, neo4j_user, neo4j_password):
    logger.info(f"Generating response for '{user_input}' using '{model}' model")
    kg_chat = KGChat(api_key, model, neo4j_uri, neo4j_user, neo4j_password)
    res = kg_chat.query(user_input, session_id, learning_type)
    data = {
        "query": res['query'],
        "response": res['result'],
        "context": f'Query: {res["intermediate_steps"][0]["query"]}\nResults: {res["intermediate_steps"][1]["context"]}'
    }
    logger.info(f"Response generated successfully for '{user_input}' using '{model}' model. \nResponse: {data}")

    return data
