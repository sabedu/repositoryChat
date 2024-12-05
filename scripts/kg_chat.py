from langchain_community.chat_models import ChatOllama
from langchain_community.graphs import Neo4jGraph
from langchain_openai import ChatOpenAI
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
from os import getenv
from langsmith import traceable
from consts import (FEW_SHOT_CYPHER_TEMPLATE, ZERO_SHOT_CYPHER_TEMPLATE, GENERATION_TEMPLATE,
                    ZERO_SHOT_CYPHER_TEMPLATE_LLAMA, FEW_SHOT_CYPHER_TEMPLATE_LLAMA, GENERATION_TEMPLATE_LLAMA)
from scripts.core.graph_cypher_chain_patch import PatchedGraphCypherQAChain
from logging import getLogger

logger = getLogger(__name__)


class KGChat:
    def __init__(self, api_key, model, neo4j_uri, neo4j_user, neo4j_password):
        # load_dotenv()
        logger.info("Creating KGChat Instance")
        self.uri = neo4j_uri #getenv("NEO4J_URI")
        self.user = neo4j_user #getenv('NEO4J_USER')
        self.password = neo4j_password #getenv('NEO4J_PASSWORD')
        self.api_key = api_key
        self.model = model
        self.graph = Neo4jGraph(url=self.uri, username=self.user, password=self.password)
        logger.info("Created KGChat Instance")

    def make_chain(self, learning_type):
        if self.model == "gpt-3.5-turbo" or self.model == "gpt-4o":

            cypher_llm = ChatOpenAI(temperature=0, model=self.model, api_key=self.api_key)
            qa_llm = ChatOpenAI(temperature=0.7, model=self.model, api_key=self.api_key)
            generation_template = GENERATION_TEMPLATE
            # if learning_type == 'zero-shot':
            #     cypher_template = ZERO_SHOT_CYPHER_TEMPLATE
            # elif learning_type == 'few-shot':
            #     cypher_template = FEW_SHOT_CYPHER_TEMPLATE
            # else:
            #     logger.exception(f"Unsupported learning type: {learning_type}")
            #     raise ValueError('Invalid learning type')
            cypher_template = FEW_SHOT_CYPHER_TEMPLATE

        elif self.model == "llama3":

            cypher_llm = ChatOllama(model='llama3:8b')
            qa_llm = ChatOllama(model='llama3:8b')
            generation_template = GENERATION_TEMPLATE_LLAMA

            if learning_type == 'zero-shot':
                cypher_template = ZERO_SHOT_CYPHER_TEMPLATE_LLAMA
            elif learning_type == 'few-shot':
                cypher_template = FEW_SHOT_CYPHER_TEMPLATE_LLAMA
            else:
                logger.exception(f"Unsupported learning type: {learning_type}")
                raise ValueError('Invalid learning type')
        else:
            logger.exception(f"Unsupported model type: {self.model}")
            raise ValueError("Invalid model type")

        cypher_prompt = PromptTemplate(input_variables=["current_date", "schema", "question", "error_context"], template=cypher_template)

        generation_prompt = PromptTemplate(input_variables=["schema", "graph_query", "question", "context"],
                                           template=generation_template)

        self.chain = PatchedGraphCypherQAChain.from_llm(
            cypher_prompt=cypher_prompt,
            qa_prompt=generation_prompt,
            cypher_llm=cypher_llm,
            qa_llm=qa_llm,
            verbose=True,
            validate_cypher=False,
            graph=self.graph,
            allow_dangerous_requests=True
        )
        logger.info(f"Created LLM chain, model: {self.model}, learning type: {learning_type}")
        return self.chain

    def get_chain_with_message_history(self, learning_type):
        chain = self.make_chain(learning_type)
        chain_with_history = RunnableWithMessageHistory(
            chain, 
            lambda session_id: RedisChatMessageHistory(
                session_id=session_id, 
                url=getenv('REDIS_HOST'),
            ),
            input_messages_key="query",
            history_messages_key="history",
            )
        return chain_with_history
    
    @traceable()
    def query(self, user_input, session_id: str,  learning_type='zero-shot'):
        # chain = self.make_chain(learning_type)
        # logger.info("Invoking LLM chain")
        # response = chain.invoke(user_input)
        config = {"configurable": {"session_id": session_id}}
        chain = self.get_chain_with_message_history(learning_type)
        response = chain.invoke(
            {"query": user_input},
            config
        )
        return response
