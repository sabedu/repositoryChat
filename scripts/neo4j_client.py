from os import getenv
from dotenv import load_dotenv
from neo4j import GraphDatabase
from logging import getLogger

logger = getLogger(__name__)


class Neo4jClient:
    def __init__(self, neo4j_uri, neo4j_user, neo4j_password):
        # load_dotenv()
        self.uri = neo4j_uri #getenv("NEO4J_URI")
        self.user = neo4j_user #getenv('NEO4J_USER')
        self.password = neo4j_password #getenv('NEO4J_PASSWORD')
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def get_graph(self):
        return self.driver

    def upload_graph(self, graph):
        logger.info("Uploading graph to Neo4j")
        for node, data in graph.nodes(data=True):
            node_type = data.get('type', 'Node')
            query = f"""
                    MERGE (n:{node_type} {{id: $node}})
                    SET n += $attributes
                    """
            self.driver.execute_query(query_=query, node=node, attributes=data, database_="neo4j")
        logger.info("Nodes uploaded to Neo4j")

        for source, target, data in graph.edges(data=True):
            edge_type = data['relation']
            query = f"""
                    MATCH (n1 {{id: $source}})
                    WITH n1
                    MATCH (n2 {{id: $target}})
                    MERGE (n1)-[r:{edge_type}]->(n2)
                    SET r += $attributes
                    """

            self.driver.execute_query(query_=query, source=source, target=target, attributes=data, database_="neo4j")
        logger.info("Edges uploaded to Neo4j")

    def execute_query(self, query_, **kwargs):
        with self.driver.session() as session:
            result = session.run(query_, **kwargs)
            return list(result)

    def close(self):
        self.driver.close()
        logger.info("Closed Neo4j connection")
