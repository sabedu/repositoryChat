from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from dotenv import load_dotenv
from scripts.construct_graph import construct_graph
from scripts.generate_response import generate_response
from logging import getLogger, basicConfig, INFO
from os import makedirs, path
from consts import LOGS_DIR

logs_dir = LOGS_DIR
makedirs(logs_dir, exist_ok=True)

basicConfig(
    level=INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename=path.join(logs_dir, 'app_logs.log'),
    filemode='a'
)

logger = getLogger(__name__)

app = Flask(__name__)
CORS(app)
load_dotenv()


@app.route('/ingest', methods=["POST"])
def ingest():
    logger.info(f"Received request on '/ingest' endpoint from {request.remote_addr}")
    github_token = request.headers.get('GH-Token')
    data = request.get_json()
    repo_url = data['url']
    neo4j_uri = data['neo4j_uri']
    neo4j_user = data['neo4j_user']
    neo4j_password = data['neo4j_password']

    logger.info(f"Collecting data and contructing graph for '{repo_url}'")
    try:
        message = construct_graph(repo_url, github_token, neo4j_uri, neo4j_user, neo4j_password)
        logger.info(f"Graph constructed successfully for '{repo_url}'")
        response = {
            "status": "success",
            "code": 200,
            "message": message,
            "data": None
        }
        return make_response(jsonify(response), 200, {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        })
    except Exception as e:
        logger.error(f"Error occurred while constructing graph for '{repo_url}'", exc_info=True)
        response = {
            "status": "error",
            "error": {
                "code": 500,
                "message": "Error occurred while constructing graph",
                "details": str(e)
            }
        }
        return make_response(jsonify(response), 500, {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        })


@app.route('/chat', methods=["POST"])
def chat():
    logger.info(f"Received request on '/chat' endpoint from {request.remote_addr}")
    try:
        req_data = request.get_json()
        repo_url = req_data['url']
        user_query = req_data['query']
        session_id = req_data['session_id']

        neo4j_uri = req_data['neo4j_uri']
        neo4j_user = req_data['neo4j_user']
        neo4j_password = req_data['neo4j_password']

        model = req_data['model'] if 'model' in req_data else 'gpt-4o'
        if model != 'llama3':
            token = request.headers.get('Authorization')
        else:
            token = ''
        learning_type = req_data['learning_type'] if 'learning_type' in req_data and req_data[
            'learning_type'] is not None else 'zero-shot'

        logger.info(f"Generating response for '{user_query}' using '{model}' model")
        response_data = generate_response(repo_url, user_query, learning_type, session_id, token, model, neo4j_uri, neo4j_user, neo4j_password)
        response = {
            "status": "success",
            "code": 200,
            "message": "Response generated successfully",
            "data": response_data
        }

        return make_response(jsonify(response), 200, {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        })
    
    except Exception as e:
        logger.error(f"Error occurred while generating response for '{user_query}'", exc_info=True)
        response = {
            "status": "error",
            "error": {
                "code": 500,
                "message": "Error occurred while generating response",
                "details": str(e)
            }
        }

        return make_response(jsonify(response), 500, {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        })

@app.errorhandler(500)
def server_error(e):
    logger.error(e)
    return e.message, e, 500


if __name__ == "__main__":
    # app.run(port=8000, debug=True)
    app.run(host="0.0.0.0", port=8000)
