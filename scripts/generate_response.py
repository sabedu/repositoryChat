from scripts.kg_chat import KGChat
from logging import getLogger
from scripts.neo4j_client import Neo4jClient

logger = getLogger(__name__)


def generate_response(repo_url, user_input, learning_type, session_id, api_key, model, neo4j_uri, neo4j_user, neo4j_password):
    # Check if the database exist for the repository
    # try:
    #     query = f"cypher MATCH (n:Repository) RETURN n.name, n.url LIMIT 25;"
    #     neo_client = Neo4jClient(neo4j_uri, neo4j_user, neo4j_password)
    #     result = neo_client.execute_query(query)
    #     neo_client.close()

    #     if result[0]['n.url'] == repo_url:
    #         logger.info(f"Database exist for the repository '{repo_url}'.")
    #     else:
    #         logger.error(f"Neo4j database already in use by {result[0]['n.url']}. Use a different database for '{repo_url}'.")
    #         raise Exception(f"Neo4j database credentials does not match database for '{repo_url.split('/')[-1]}'.")
    # except Exception as e:
    #     logger.error(f"Error occurred while checking the database for '{repo_url}'", exc_info=True)
    #     raise Exception(f"Error {str(e)} occurred while checking the database for '{repo_url.split('/')[-1]}'. Check details and try again.")
    
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
