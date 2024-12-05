import os
from scripts.github_data_collector import GitHubDataCollector
from scripts.graph_handler import GraphHandler, DataHandler
from scripts.link_bugs import LinkBugs
from scripts.neo4j_client import Neo4jClient
from logging import getLogger
from os.path import join

logger = getLogger(__name__)


def get_entities_path(current_working_dir, url, entity):
    path = join(current_working_dir, f"data/{url}/{url}_{entity}.json")
    updated_path = join(current_working_dir, f"data/{url}/new_{url}_{entity}.json")
    # updated = os.path.exists(updated_path)
    # return (updated_path, updated_path) if updated else (path, None)
    return path, updated_path

def construct_graph(repo_url, token, neo4j_uri, neo4j_user, neo4j_password):
    # Check if the database exist for the repository
    try:
        query = f"cypher MATCH (n:Repository) RETURN n.name, n.url LIMIT 25;"
        neo_client = Neo4jClient(neo4j_uri, neo4j_user, neo4j_password)
        result = neo_client.execute_query(query)
        neo_client.close()

        if not result:
            logger.info(f"Creating a new database for '{repo_url}'.")
        elif result[0]['n.url'] == repo_url:
            logger.info(f"Using the existing database for '{repo_url}'. Information in the database will be updated.")
        else:
            logger.error(f"Neo4j database already in use by {result[0]['n.url']}. Use a different database for '{repo_url}'.")
            raise Exception(f"Neo4j database already in use by a different project. Use a different database for '{repo_url.split('/')[-1]}'.")
    except Exception as e:
        logger.error(f"Error occurred while checking the database for '{repo_url}'", exc_info=True)
        raise Exception(f"Error {str(e)} occurred while checking the database for '{repo_url.split('/')[-1]}'. Check details and try again.")

    url = repo_url.split('/')[-1]
    current_working_dir = os.getcwd()
    repositories_path, repositories_updated = get_entities_path(current_working_dir, url, 'repositories')
    collaborators_path, collaborators_updated = get_entities_path(current_working_dir, url, 'collaborators')
    releases_path, releases_updated = get_entities_path(current_working_dir, url, 'releases')
    languages_path, languages_updated = get_entities_path(current_working_dir, url, 'languages')
    projects_path, projects_updated = get_entities_path(current_working_dir, url, 'projects')
    forks_path, forks_updated = get_entities_path(current_working_dir, url, 'forks')
    commits_path, commits_updated = get_entities_path(current_working_dir, url, 'commits')
    issues_path, issues_updated = get_entities_path(current_working_dir, url, 'issues')
    pull_requests_path, pull_requests_updated = get_entities_path(current_working_dir, url, 'pull_requests')
    bic_path, bics_updated = get_entities_path(current_working_dir, url, 'fixing_bic')

    first_run = not any([os.path.exists(path) for path in [repositories_path, collaborators_path, releases_path, languages_path,
                                                           projects_path, forks_path, commits_path, issues_path,
                                                           pull_requests_path, bic_path]])


    data_collector = GitHubDataCollector(token, repo_url)
    first_run = data_collector.collect_data()

    updated_file_paths = [repositories_updated, collaborators_updated, releases_updated, languages_updated, projects_updated,
                   forks_updated, commits_updated, issues_updated, pull_requests_updated, bics_updated]
    
    updated_files = [path for path in updated_file_paths if os.path.exists(path)]
    any_updates = bool(updated_files)
    
    # any_updates = (repositories_updated or releases_updated or languages_updated or projects_updated or
    #                forks_updated or commits_updated or issues_updated or pull_requests_updated or bics_updated)
    # first_run = True
    if first_run or any_updates:
        if first_run:
            logger.info("Creating graph for the first time")
            repositories = DataHandler(repositories_path).load_data()
            colaborators = DataHandler(collaborators_path).load_data()
            releases = DataHandler(releases_path).load_data()
            languages = DataHandler(languages_path).load_data()
            projects = DataHandler(projects_path).load_data()
            forks = DataHandler(forks_path).load_data()
            commits = DataHandler(commits_path).load_data()
            issues = DataHandler(issues_path).load_data()
            pull_requests = DataHandler(pull_requests_path).load_data()

            bics = LinkBugs(repo_url).process_issues()
            # bics = DataHandler(bic_path).load_data()
        elif any_updates:
            logger.info("Updating the graph")
            colaborators = DataHandler(collaborators_path).load_data()

            if os.path.exists(commits_updated):
                commits = DataHandler(commits_updated).load_data()
            else:
                commits = []

            if os.path.exists(issues_updated):
                issues = DataHandler(issues_updated).load_data()
            else:
                issues = []

            if os.path.exists(pull_requests_updated):
                pull_requests = DataHandler(pull_requests_updated).load_data()
            else:
                pull_requests = []

            if os.path.exists(issues_updated):
                # bics = DataHandler(bics_updated).load_data()
                bics = LinkBugs(repo_url).process_issues(True)
            else:
                bics = []
            
            repositories = DataHandler(repositories_path).load_data()
            # if os.path.exists(repositories_updated):
            #     repositories = DataHandler(repositories_updated).load_data()
            # else:
            #     repositories = []
            
            if os.path.exists(releases_updated):
                releases = DataHandler(releases_updated).load_data()
            else:
                releases = []

            if os.path.exists(languages_updated):
                languages = DataHandler(languages_updated).load_data()
            else:
                languages = []

            if os.path.exists(projects_updated):
                projects = DataHandler(projects_updated).load_data()
            else:
                projects = []

            if os.path.exists(forks_updated):
                forks = DataHandler(forks_updated).load_data()
            else:
                forks = []

        graph_handler = GraphHandler()
        collaborators = graph_handler.add_nodes_and_edges(repositories, colaborators, releases, languages, projects, forks, commits, issues,
                                          pull_requests)
        if collaborators:
            # save collaborators data
            DataHandler(collaborators_path).save_data(collaborators)
        if bics:
            graph_handler.add_bic_relationships(bics)

        for u, v, k in graph_handler.G.edges(keys=True):
            graph_handler.G[u][v][k]['label'] = k

        # repo_name = repo_url.split('/')[-1]
        # graph_handler.save_graph(f'graphs/{repo_name}.graphml')

        neo_client = Neo4jClient(neo4j_uri, neo4j_user, neo4j_password)
        neo_client.upload_graph(graph_handler.G)
        neo_client.close()

        if first_run:
            message = "Graph created successfully"
        elif any_updates:
            message = "Graph updated successfully"
            for path in updated_files:
                os.remove(path)
        logger.info(message)
        return message
    else:
        message = "No new data to update the graph."
        logger.info(message)
        return message
