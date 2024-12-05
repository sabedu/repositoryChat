from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional
from logging import getLogger
from langchain_core.callbacks import CallbackManagerForChainRun
from langchain.chains import GraphCypherQAChain

INTERMEDIATE_STEPS_KEY = "intermediate_steps"

logger = getLogger(__name__)


def extract_cypher(text: str) -> str:
    """Extract Cypher code from a text.

    Args:
        text: Text to extract Cypher code from.

    Returns:
        Cypher code extracted from the text.
    """
    # The pattern to find Cypher code enclosed in triple backticks
    pattern = r"```(.*?)```"

    # Find all matches in the input text
    matches = re.findall(pattern, text, re.DOTALL)

    return matches[-1] if matches else text


def construct_schema(structured_schema: Dict[str, Any], include_types: List[str], exclude_types: List[str], ) -> str:
    """Filter the schema based on included or excluded types"""

    def filter_func(x: str) -> bool:
        return x in include_types if include_types else x not in exclude_types

    filtered_schema: Dict[str, Any] = {
        "node_props": {
            k: v
            for k, v in structured_schema.get("node_props", {}).items()
            if filter_func(k)
        },
        "rel_props": {
            k: v
            for k, v in structured_schema.get("rel_props", {}).items()
            if filter_func(k)
        },
        "relationships": [
            r
            for r in structured_schema.get("relationships", [])
            if all(filter_func(r[t]) for t in ["start", "end", "type"])
        ],
    }

    # Format node properties
    formatted_node_props = []
    for label, properties in filtered_schema["node_props"].items():
        props_str = ", ".join(
            [f"{prop['property']}: {prop['type']}" for prop in properties]
        )
        formatted_node_props.append(f"{label} {{{props_str}}}")

    # Format relationship properties
    formatted_rel_props = []
    for rel_type, properties in filtered_schema["rel_props"].items():
        props_str = ", ".join(
            [f"{prop['property']}: {prop['type']}" for prop in properties]
        )
        formatted_rel_props.append(f"{rel_type} {{{props_str}}}")

    # Format relationships
    formatted_rels = [
        f"(:{el['start']})-[:{el['type']}]->(:{el['end']})"
        for el in filtered_schema["relationships"]
    ]

    return "\n".join(
        [
            "Node properties are the following:",
            ",".join(formatted_node_props),
            "Relationship properties are the following:",
            ",".join(formatted_rel_props),
            "The relationships are the following:",
            ",".join(formatted_rels),
        ]
    )


class PatchedGraphCypherQAChain(GraphCypherQAChain):

    def generate_cypher(self, question, chat_history, callbacks, error_context=None):
        logger.info('Generating Cypher statement')

        if error_context is None:
            logger.info("Standard prompt used to generate cypher statement")
            prompt = {"question": question, "schema": self.graph_schema, "error_context": "",
                      "history": chat_history,
                      "current_date": {datetime.now(timezone.utc).replace(microsecond=0).isoformat() + 'Z'}}

        else:
            logger.info("Error prompt used to generate cypher statement")
            prompt = {"question": question,
                      "schema": self.graph_schema,
                      "history": chat_history,
                      "error_context": error_context,
                      "current_date": {datetime.now(timezone.utc).replace(microsecond=0).isoformat() + 'Z'}}
        generated_cypher_text = self.cypher_generation_chain.invoke(prompt, callbacks=callbacks)
        logger.info(f"Generated Cypher text is {generated_cypher_text["text"]}")

        # Extract Cypher code if it is wrapped in backticks
        generated_cypher = extract_cypher(generated_cypher_text["text"])

        logger.info(f"Cypher statement before corrector is {generated_cypher}")
        # Correct Cypher query if enabled
        if self.cypher_query_corrector:
            generated_cypher = self.cypher_query_corrector(generated_cypher)

        logger.info(f"Cypher statement after corrector is {generated_cypher}")
        return generated_cypher, generated_cypher_text

    def get_context(self, question, generated_cypher, chat_history, callbacks):
        if generated_cypher:
            try:
                context = self.graph.query(generated_cypher)
                # context = self.graph.query(generated_cypher)[: self.top_k]
            except Exception as e:
                # If an error occurs, regenerate the Cypher query
                logger.error(f"Error executing Cypher query: {e}")
                logger.info("Regenerating query...")
                error_context = f"Original query: {generated_cypher}\nError: {e}\n"

                generated_cypher, _ = self.generate_cypher(question, chat_history, callbacks, error_context=error_context)
                # Execute the new query
                try:
                    # context = self.graph.query(generated_cypher)[: self.top_k]
                    context = self.graph.query(generated_cypher)
                except Exception as e:
                    logger.exception(f"Error executing Cypher query: {e} even after re-generating it.")
                    context = []
        else:
            logger.info("No cypher statement generated")
            context = []

        return context

    def _call(
        self,
        inputs: Dict[str, Any],
        run_manager: Optional[CallbackManagerForChainRun] = None,
    ) -> Dict[str, Any]:
        """Generate Cypher statement, use it to look up in db and answer question."""
        _run_manager = run_manager or CallbackManagerForChainRun.get_noop_manager()
        callbacks = _run_manager.get_child()
        question = inputs[self.input_key]
        
        chat_history = inputs.get("history", [])

        intermediate_steps: List = []

        generated_cypher, generated_cypher_text = self.generate_cypher(question, chat_history, callbacks)
        if generated_cypher == "":
            generated_cypher, generated_cypher_text = self.generate_cypher(question, chat_history, callbacks)

        _run_manager.on_text("Generated Cypher:", end="\n", verbose=self.verbose)
        _run_manager.on_text(
            generated_cypher, color="green", end="\n", verbose=self.verbose
        )

        intermediate_steps.append({"query": generated_cypher})

        # Retrieve and limit the number of results
        # Generated Cypher be null if query corrector identifies invalid schema

        context = self.get_context(question=question, generated_cypher=generated_cypher, chat_history=chat_history, callbacks=callbacks)
        if not context:
            logger.info("No context found")
            logger.info("Regenerating query...")
            generated_cypher, generated_cypher_text = self.generate_cypher(question, chat_history, callbacks)
            context = self.get_context(question, generated_cypher, chat_history, callbacks)
            if not context:
                logger.error(f"Unable to provide valid context information : Question : {question}, Cypher Query : {generated_cypher}")

        if self.return_direct:
            final_result = context
        else:
            _run_manager.on_text("Full Context:", end="\n", verbose=self.verbose)
            _run_manager.on_text(
                str(context), color="green", end="\n", verbose=self.verbose
            )

            intermediate_steps.append({"context": context})

            result = self.qa_chain(
                {
                    "schema": self.graph_schema,
                    "graph_query": generated_cypher,
                    "question": question,
                    "context": context},
                callbacks=callbacks,
            )
            final_result = result[self.qa_chain.output_key]

        chain_result: Dict[str, Any] = {self.output_key: final_result, "output": final_result, "cot_text": generated_cypher_text["text"]}
        chain_result["output"] = final_result
        # if self.return_intermediate_steps:
        chain_result[INTERMEDIATE_STEPS_KEY] = intermediate_steps

        return chain_result
