import ollama
import httpx
import asyncio

async def make_request(query):
    async with httpx.AsyncClient(timeout=None) as client:  # Set timeout to None to wait indefinitely
        # Define the endpoint URL
        query_url = "http://localhost:8000/api/query"

        # Define the payload
        payload = {
            "query": query
        }

        try:
            # Make a POST request to the /api/query endpoint
            response_query = await client.post(query_url, json=payload)
            if response_query.status_code == 200:
                response_data = response_query.json()
                print("Successfully retrieved context!")
                return response_data.get("context", "No context provided")
            else:
                print(f"Query Request failed with status code {response_query.status_code}")
                return None
        except httpx.RequestError as exc:
            print(f"An error occurred while requesting {exc.request.url!r}: {exc}")
            return None
        

async def grading_assistant(question_answer_pair, context):
    print(context)
    user_context = " ".join(context)
    # answer_key = "The Turing Test: A Benchmark for Artificial Intelligence and a Redefinition of Intelligence Itself - The Turing Test stands as a landmark in the quest to understand artificial intelligence. It proposes a clear and thought-provoking criterion: if a machine can carry on a conversation indistinguishable from a human, then it can be considered intelligent. This simple yet profound idea challenges our very definition of intelligence. By forcing us to consider conversation as a key marker of intelligence, the Turing Test becomes a valuable benchmark for measuring progress in AI."
    rubric_content = f"""<s> [INST] Please act as an impartial judge and evaluate the quality of the provided answer which attempts to answer the provided question based on a provided context.
            You'll be given context, question and answer to submit your reasoning and score for the correctness, comprehensiveness and readability of the answer. 

            Here is the context - 
            [CONTEXT START]
            {user_context}. 
            [CONTEXT START]

            Below is your grading rubric: 
            - Correctness: If the answer correctly answers the question, below are the details for different scores:
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
            - Score 3: the answer correctly answers the question and is not missing any major aspect. In this case, to score correctness 3, the final answer must be correct, final solution for numerical problems is of utmost importance.
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
            - Score 2: the answer is correct and roughly answers the main aspects of the question, but it's missing description about details. Or is completely missing details about one minor aspect.
                - Example:
                    - Question: How to use databricks API to create a cluster?
                    - Answer: You will need a Databricks access token with the appropriate permissions. Then you'll need to set up the request URL, then you can make the HTTP Request. Then you can handle the request response.
                - Example:
                    - Question: How to use databricks API to create a cluster?
                    - Answer: You will need a Databricks access token with the appropriate permissions. Then you'll need to set up the request URL, then you can make the HTTP Request. Then you can handle the request response.
            - Score 3: the answer is correct, and covers all the main aspects of the question
            - Readability: How readable is the answer, does it have redundant information or incomplete information that hurts the readability of the answer.
            - Score 0: the answer is completely unreadable, e.g. full of symbols that's hard to read; e.g. keeps repeating the words that it's very hard to understand the meaning of the paragraph. No meaningful information can be extracted from the answer.
            - Score 1: the answer is slightly readable, there are irrelevant symbols or repeated words, but it can roughly form a meaningful sentence that covers some aspects of the answer.
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
            The format in which you should provide results-
                Correctness:
                    -Score(scale of 0 to 3)
                    -Explanation of score
                Readability:
                    -Score(scale of 0 to 3)
                    -Explanation of score
                Comprehensiveness:
                    -Score(scale of 0 to 3)
                    -Explanation of score
                
            # Overall Score Calculation:

            # The final rating is determined using the following weighted formula:

            # - Correctness Score: 60%
            # - Readability Score: 20%
            # - Comprehensiveness Score: 20%

            # Note: Scores must be whole numbers (0, 1, 2, or 3).

            # The final rating, out of a total of 3 points, is calculated as:

            # Final Rating = (0.6 * Correctness Score) + (0.2 * Readability Score) + (0.2 * Comprehensiveness Score)

            # Example:
            # If Correctness Score is 2, Readability Score is 2, and Comprehensiveness Score is 3:
            # Final Rating = (0.6 * 2) + (0.2 * 2) + (0.2 * 3)
            #              = 1.2 + 0.4 + 0.6
            #              = 2.2
            #              = 2 (rounded to the nearest whole number)

            # Please adhere strictly to this grading system.
                            """
    
    # Define the payload
    payload = {
        "messages": [
            {
                "role": "system",
                "content": rubric_content
            },
            {
                "role": "user",
                "content": f"Grade the following question-answer pair using the grading rubric and context provided - {question_answer_pair}."
            }
        ],
        "stream": False,
        "options": {
            "top_k": 1, 
            "top_p": 1, 
            "temperature": 0, 
            "seed": 100, 
        }
    }

    # Asynchronous call to Ollama API
    response = await asyncio.to_thread(ollama.chat, model='llama3', messages=payload['messages'], stream=payload['stream'])

    # Return the response content
    return response['message']['content']

async def query_to_context_match(query, context):
    # Join the context into a single string
    user_context = " ".join(context)

    context_query_match = "<s> [INST] You are an expert Google searcher, whose job is to determine if the following document is relevant to the query (true/false). Answer using only one word, one of those two choices.[/INST]"

    # Define the payload for Ollama
    payload = {
        "messages": [
            {
                "role": "system",
                "content": context_query_match
            },
            {
                "role": "user",
                "content": f"With this provided context: '{context}' Please look at this query: '{query}'.",
            }
        ],
        "stream": False,
        "options": {
            "top_k": 1, 
            "top_p": 1, 
            "temperature": 0, 
            "seed": 100, 
        }
    }

# # Example usage
# async def main():
#     query = "Q: What is the significance of the Turing Test in the field of artificial intelligence? A: The Turing Test is significant because it proposes a criterion for determining whether a computer is capable of exhibiting intelligent behavior equivalent to, or indistinguishable from, that of a human. It challenges the notion of what it means to be intelligent and serves as a benchmark for evaluating AI capabilities."
#     context = await make_request(query)
#     variants = await grading_assistant(query, context)
#     print(variants)

# # Run the async main function
# asyncio.run(main())
