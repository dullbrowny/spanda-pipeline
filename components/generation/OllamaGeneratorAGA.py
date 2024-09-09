import os

import json
import aiohttp

from goldenverba.components.interfaces import Generator


class OllamaGeneratorAGA(Generator):
    def __init__(self):
        super().__init__()
        self.name = "Ollama"
        self.description = "Generator using a local running Ollama Model specified in the ` OLLAMA_MODEL` variable"
        self.requires_env = ["OLLAMA_URL", "OLLAMA_MODEL"]
        self.streamable = True
        self.context_window = 10000

    async def generate_stream(
        self,
        queries: list[str],
        context: list[str],
        conversation: dict = None,
    ):
        """Generate a stream of response dicts based on a list of queries and list of contexts, and includes conversational context
        @parameter: queries : list[str] - List of queries
        @parameter: context : list[str] - List of contexts
        @parameter: conversation : dict - Conversational context
        @returns Iterator[dict] - Token response generated by the Generator in this format {system:TOKEN, finish_reason:stop or empty}.
        """

        url = os.environ.get("OLLAMA_URL", "")
        model = os.environ.get("OLLAMA_MODEL", "")
        if url == "":
            yield {
                "message": "Missing Ollama URL",
                "finish_reason": "stop",
            }

        url += "/api/chat"

        if conversation is None:
            conversation = {}
        messages = self.prepare_messages(queries, context, conversation)

        try:
            data = {"model": model, "messages": messages}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    async for line in response.content:
                        if line.strip():  # Ensure line is not just whitespace
                            json_data = json.loads(
                                line.decode("utf-8")
                            )  # Decode bytes to string then to JSON
                            message = json_data.get("message", {}).get("content", "")
                            finish_reason = (
                                "stop" if json_data.get("done", False) else ""
                            )

                            yield {
                                "message": message,
                                "finish_reason": finish_reason,
                            }
                        else:
                            yield {
                                "message": "",
                                "finish_reason": "stop",
                            }

        except Exception:
            raise

    def prepare_messages(
        self, queries: list[str], context: list[str], conversation: dict[str, str]
    ) -> dict[str, str]:
        """
        Prepares a list of messages formatted for a Retrieval Augmented Generation chatbot system, including system instructions, previous conversation, and a new user query with context.

        @parameter queries: A list of strings representing the user queries to be answered.
        @parameter context: A list of strings representing the context information provided for the queries.
        @parameter conversation: A list of previous conversation messages that include the role and content.

        @returns A list of message dictionaries formatted for the chatbot. This includes an initial system message, the previous conversation messages, and the new user query encapsulated with the provided context.

        Each message in the list is a dictionary with 'role' and 'content' keys, where 'role' is either 'system' or 'user', and 'content' contains the relevant text. This will depend on the LLM used.
        """

        rubric_content = """Please act as an impartial judge and evaluate the quality of the provided answer which attempts to answer the provided question based on a provided context.
            You'll be given context, question and answer to submit your reasoning and score for the correctness, comprehensiveness and readability of the answer. 

            Below is your grading rubric: 
            - Correctness: If the answer correctly answer the question, below are the details for different scores:
            - Score 0: the answer is completely incorrect, doesn't mention anything about the question or is completely contrary to the correct answer.
                - For example, when asked “How to terminate a databricks cluster”, the answer is an empty string, or content that's completely irrelevant, or sorry I don't know the answer.
            - Score 1: the answer provides some relevance to the question and answers one aspect of the question correctly.
                - Example:
                    - Question: How to terminate a databricks cluster
                    - Answer: Databricks cluster is a cloud-based computing environment that allows users to process big data and run distributed data processing tasks efficiently.
                    - Or answer:  In the Databricks workspace, navigate to the "Clusters" tab. And then this is a hard question that I need to think more about it
            - Score 2: the answer mostly answers the question but is missing or hallucinating on one critical aspect.
                - Example:
                    - Question: How to terminate a databricks cluster”
                    - Answer: “In the Databricks workspace, navigate to the "Clusters" tab.
                    Find the cluster you want to terminate from the list of active clusters.
                    And then you'll find a button to terminate all clusters at once”
            - Score 3: the answer correctly answer the question and not missing any major aspect. In this case, to score correctness 3, the final answer must be correct, final solution for numerical problems is of upmost importance.
                - Example:
                    - Question: How to terminate a databricks cluster
                    - Answer: In the Databricks workspace, navigate to the "Clusters" tab.
                    Find the cluster you want to terminate from the list of active clusters.
                    Click on the down-arrow next to the cluster name to open the cluster details.
                    Click on the "Terminate" button. A confirmation dialog will appear. Click "Terminate" again to confirm the action.”
            - Comprehensiveness: How comprehensive is the answer, does it fully answer all aspects of the question and provide comprehensive explanation and other necessary information. Below are the details for different scores:
            - Score 0: typically if the answer is completely incorrect, then the comprehensiveness is also zero.
            - Score 1: if the answer is correct but too short to fully answer the question, then we can give score 1 for comprehensiveness.
                - Example:
                    - Question: How to use databricks API to create a cluster?
                    - Answer: First, you will need a Databricks access token with the appropriate permissions. You can generate this token through the Databricks UI under the 'User Settings' option. And then (the rest is missing)
            - Score 2: the answer is correct and roughly answer the main aspects of the question, but it's missing description about details. Or is completely missing details about one minor aspect.
                - Example:
                    - Question: How to use databricks API to create a cluster?
                    - Answer: You will need a Databricks access token with the appropriate permissions. Then you'll need to set up the request URL, then you can make the HTTP Request. Then you can handle the request response.
                - Example:
                    - Question: How to use databricks API to create a cluster?
                    - Answer: You will need a Databricks access token with the appropriate permissions. Then you'll need to set up the request URL, then you can make the HTTP Request. Then you can handle the request response.
            - Score 3: the answer is correct, and covers all the main aspects of the question
            - Readability: How readable is the answer, does it have redundant information or incomplete information that hurts the readability of the answer.
            - Score 0: the answer is completely unreadable, e.g. fully of symbols that's hard to read; e.g. keeps repeating the words that it's very hard to understand the meaning of the paragraph. No meaningful information can be extracted from the answer.
            - Score 1: the answer is slightly readable, there are irrelevant symbols or repeated words, but it can roughly form a meaningful sentence that cover some aspects of the answer.
                - Example:
                    - Question: How to use databricks API to create a cluster?
                    - Answer: You you  you  you  you  you  will need a Databricks access token with the appropriate permissions. And then then you'll need to set up the request URL, then you can make the HTTP Request. Then Then Then Then Then Then Then Then Then
            - Score 2: the answer is correct and mostly readable, but there is one obvious piece that's affecting the readability (mentioning of irrelevant pieces, repeated words)
                - Example:
                    - Question: How to terminate a databricks cluster
                    - Answer: In the Databricks workspace, navigate to the "Clusters" tab.
                    Find the cluster you want to terminate from the list of active clusters.
                    Click on the down-arrow next to the cluster name to open the cluster details.
                    Click on the "Terminate" button…………………………………..
                    A confirmation dialog will appear. Click "Terminate" again to confirm the action.
            - Score 3: the answer is correct and reader friendly, no obvious piece that affect readability.
            - Then final rating:
                - Ratio: 60 correctness + 20 comprehensiveness + 20 readability 
                - Example 1 of a final rating - 
                    Overall Score:
                        Correctness: 3
                        Comprehensiveness: 2
                        Readability: 2
                        Final Score = 60%' of 3(correctness score) + 20%' of 2(Comprehensiveness score) + 20%' of 2(Readability score)
                                    = 1.8 + 0.4 + 0.4 = 2.6/3
                - Example 2 of a final rating -
                    Overall Score:
                        Correctness: 3
                        Comprehensiveness: 3
                        Readability: 3
                        Final Score = 60%' of 3(correctness score) + 20%' of 3(Comprehensiveness score) + 20%' of 3(Readability score)
                                    = 1.8 + 0.6 + 0.6 = 3/3
            
            The format in which you should provide results-
                Confidence: (0 or 1)
                Correctness:
                    -Score(scale of 0 to 3)
                    -Explanation of score
                Readability:
                    -Score(scale of 0 to 3)
                    -Explanation of score
                Comprehensiveness:
                    -Score(scale of 0 to 3)
                    -Explanation of score
                
                Overall Score:
                    - Then final rating:
                        - Ratio: 60 %'correctness + 20 %'comprehensiveness + 20 %'readability 
                        Strictly follow this ratio of grading.
                            """

        messages = [
            {
                "role": "system",
                "content": rubric_content,
            }
        ]

        for message in conversation:
            messages.append({"role": message.type, "content": message.content})


        user_context = " ".join(context)
        query = " ".join(queries)

        messages.append(
            {
                "role": "user",
                "content": f"Please grade the following question-answer pair: '{query}', With this provided context: '{user_context}' ",
            }
        )

        return messages