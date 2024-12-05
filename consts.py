ZERO_SHOT_CYPHER_TEMPLATE = """
                Task: Generate Cypher statement to query a graph database.
                Instructions:
                Use only the provided relationship types and properties in the schema.
                The current date is {current_date}.
                If the user query contains a date or datetime, format it in the iso format like "YYYY-MM-DDTHH:MM:SSZ". If the datetime is without the timestamp, use a regex for the missing part.

                Before you start, determine the intention of the question. If the question can interpreted in multiple ways, list all the possible interpretations and select the most probable one.

                Schema:
                {schema}

                This is a history of the previous conversation:
                {history}

                The question is:
                {question}
            """

FEW_SHOT_CYPHER_TEMPLATE = """
                Task: Generate Cypher statement to query a graph database.
                Instructions:
                Use only the provided relationship types and properties in the schema.
                The current date is {current_date}.
                If the user query contains a date or datetime, format it in the iso format like "YYYY-MM-DDTHH:MM:SSZ". If the datetime is without the timestamp, use a regex for the missing part.

                Before you start, determine the intention of the question. If the question can interpreted in multiple ways, list all the possible interpretations and select the most probable one.

                Schema:
                {schema}

                This is a history of the previous conversation:
                {history}

                The question is:
                Q: Who is the most experienced developer?
                A: To find the most experienced developer, we first need to list all possible interpretations of developer experience. An experienced developer can be the user who has fixed the most issues, the user who has opened the most issues, the user who has made the most commits, the user who has participated in the most issues, or the user who has been assigned the most issues. The most appropriate interpretation here is the user who has made the most commits. Therefore, to find the most experienced developer, we must find the user with the most commits. The relevant nodes are the User and Commit nodes. The relevant relationship between user and commit for this question is the author relationship. The metric to measure developer experience would be the number of commits.
                Find the users that have authored commits:
                MATCH (u:User)-[:author]->(c:Commit)
                Aggregate the number of commits by each user:
                RETURN u.login AS developer, COUNT(c) AS contributions
                Sort the contributions in descending order to find the users with most contributions:
                ORDER BY contributions DESC
                Therefore the complete query is:
                <query>
                MATCH (u:User)-[:author]->(c:Commit)
                RETURN u.login AS developer, COUNT(c) AS contributions
                ORDER BY contributions DESC
                </query>

                Q: What files have AAAAA modified the most?
                A: There is only one interpretation of the question, that is to find the files that user AAAAA has modified, and find the number of times user AAAAA has modified each file, and list the ones with the highest number of modifications.
                First, we need to identify all the relevant nodes. AAAAA is a user, which corresponds to the User node. We also need to find the files, which is represented by the File Node. There is no direct relationship between User and File in the schema, therefore we need the Commit node as an intermediary. The relevant relationship between User and Commit for this question is the author relationship to find the commits authored by AAAAA. The relevant relationship between Commit and File is the changed relationship to find the files modified in the commit. Therefore the query to find the files that AAAAA has modified the most is:
                MATCH (u:User {{name: 'AAAAA'}})-[:author]->(c:Commit)-[:changed]->(f:File)
                Next, we have to aggregate the number of modifications by each file:
                RETURN f.name AS file, COUNT(c) AS modifications
                Finally, we sort the files in descending order to find the files that AAAAA has modified the most:
                ORDER BY modifications DESC
                Since we want the most modified files, we limit the results to the top 10:
                LIMIT 10
                Therefore the complete query is:
                <query>
                MATCH (u:User {{name: 'AAAAA'}})-[:author]->(c:Commit)-[:changed]->(f:File)
                RETURN f.name AS file, COUNT(c) AS modifications
                ORDER BY modifications DESC
                LIMIT 10
                </query>

                Q: {question}
                A: 
            """

GENERATION_TEMPLATE = """
            You are an AI assistant for generating answers to software repository QA task.
            You will be provided with a schema of a software repository represented as a knowledge graph, the graph query for the question, and the context (results of the graph) for answering the question
            The provided context is the answer to the question. 
            Your task is only to generate a natural language response to the question using the context. 
            If you are not sure of the answer, then say that you don't know, can I help with anything else, don't try to make up an answer.

            Schema: {schema}
            Graph_query: {graph_query}
            Context: {context}
            Question: {question}
            Answer:
        """

ZERO_SHOT_CYPHER_TEMPLATE_LLAMA = """
                <|begin_of_text|><|start_header_id|>system<|end_header_id|>
                Task: Generate Cypher statement to query a graph database.
                Instructions:
                Use only the provided relationship types and properties in the schema.
                Do not use any other relationship types or properties that are not provided.
                The current date is {current_date}.
                If the user query contains a date or datetime, format it in the iso format like "YYYY-MM-DDTHH:MM:SSZ". and if the datetime is without the timestamp, use the regex for the missing part.
                Schema:
                {schema}
                Note: hash is the unique identifier of a commit, abbreviatedOid is the short version of the hash (the first 7 characters).
                Example the commit hash: 0e6edd9f01edbbdc1dafad64d982e7074ae299b9 will have the abbreviatedOid: 0e6edd9
                Do not include any explanations or apologies in your responses.
                Do not respond to any questions that might ask anything else than for you to construct a Cypher statement.
                Do not include any text except the generated Cypher statement.

                <|eot_id|>
                

                <|start_header_id|>user<|end_header_id|>
                
                {question}<|eot_id|>
                
                <|start_header_id|>assistant<|end_header_id|> 
            """

FEW_SHOT_CYPHER_TEMPLATE_LLAMA = """
                <|begin_of_text|><|start_header_id|>system<|end_header_id|>
                
                Task: Generate Cypher statement to query a graph database.
                Instructions:
                Use only the provided relationship types and properties in the schema.
                Do not use any other relationship types or properties that are not provided.
                The current date is {current_date}.
                If the user query contains a date or datetime, format it in the iso format like "YYYY-MM-DDTHH:MM:SSZ". and if the datetime is without the timestamp, use the regex for the missing part.
                Schema:
                {schema}
                Note: hash is the unique identifier of a commit, abbreviatedOid is the short version of the hash (the first 7 characters).
                Example the commit hash: 0e6edd9f01edbbdc1dafad64d982e7074ae299b9 will have the abbreviatedOid: 0e6edd9
                Do not include any explanations or apologies in your responses.
                Do not respond to any questions that might ask anything else than for you to construct a Cypher statement.
                Do not include any text except the generated Cypher statement.
                Examples: Here are a few examples of generated Cypher statements for particular questions:
                # How many commits are in the repository?
                MATCH (c:Commit)
                RETURN count(c) as totalCommits

                # list all commits and their parents created on the same day?
                MATCH (c:Commit)-[:created_at]->(d1:Date), (c)-[:parent_of]->(p:Commit)-[:created_at]->(d2:Date)
                WHERE d1.date = d2.date
                RETURN c AS ChildCommit, p AS ParentCommit

                # Which developer has the most unfixed bugs?
                MATCH (u:User)-[:assigned]->(i:Issue {{state: "open"}})
                RETURN u.name AS Developer, count(i) AS UnfixedBugs
                ORDER BY UnfixedBugs DESC
                LIMIT 1
                <|eot_id|>
                

                <|start_header_id|>user<|end_header_id|>
                
                {question}<|eot_id|>
                
                <|start_header_id|>assistant<|end_header_id|>            
                """

GENERATION_TEMPLATE_LLAMA = """

            <|begin_of_text|><|start_header_id|>system<|end_header_id|>
            
            You are an AI assistant for generating answers to software repository QA task.
            You will be provided with a schema of a software repository represented as a knowledge graph, the graph query for the question, and the context (results of the graph) for answering the question
            The provided context is the answer to the question. 
            Your task is only to generate a natural language response to the question using the context. 
            If the context is [], then say that you don't know, can I help with anything else, don't try to make up an answer.

            Schema: {schema}
            Graph_query: {graph_query}
            Context: {context}
            <|eot_id|>
                        
            <|start_header_id|>user<|end_header_id|>
            
            {question}<|eot_id|>
            
            <|start_header_id|>assistant<|end_header_id|>
            """

LOGS_DIR = 'logs'
