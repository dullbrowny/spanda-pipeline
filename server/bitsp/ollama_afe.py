import httpx
import asyncio
import json
import re
from ollama import chat

async def make_request(query):
    async with httpx.AsyncClient(timeout=None) as client:  # Set timeout to None to wait indefinitely
        query_url = "http://localhost:8000/api/query"
        payload = {"query": query}

        try:
            response_query = await client.post(query_url, json=payload)
            if response_query.status_code == 200:
                response_data = response_query.json()
                print("Successfully retrieved context!")

                chunks = response_data.get("chunks", [])
                for chunk in chunks:
                    doc_name = chunk.get("doc_name", "Unknown document")
                    print(f"Document name: {doc_name}")

                return response_data.get("context", "No context provided")
            else:
                print(f"Query Request failed with status code {response_query.status_code}")
                return None
        except httpx.RequestError as exc:
            print(f"An error occurred while requesting {exc.request.url!r}: {exc}")
            return None

async def instructor_eval(instructor_name, context, score_criterion, explanation):
    user_context = " ".join(context)

    responses = {}
    scores_dict = {}

    evaluate_instructor = f"""
    You are Verba, The Golden RAGtriever, a chatbot for Retrieval Augmented Generation (RAG). You will receive a user query and context pieces that have a semantic similarity to that specific query. Please answer these user queries only with their provided context. If the provided documentation does not provide enough information, say so. If the user asks questions about you as a chatbot specifically, answer them naturally. If the answer requires code examples, encapsulate them with ```programming-language-name ```. Don't do pseudo-code.
    """

    payload = {
        "messages": [
            {"role": "system", "content": evaluate_instructor},
            {
                "role": "user",
                "content": f"""
                Here are your transcripts -
                [TRANSCRIPT START]
                {context}
                [TRANSCRIPT END]

                [INST] 
                -Instructions:
                    You are tasked with evaluating a teacher's performance based on the criterion: {score_criterion}. 
                [/INST]
                -Evaluation Details:
                    -Criterion Explanation: {explanation}
                    -Focus exclusively on the provided video transcript.
                    -Ignore interruptions from student entries/exits and notifications of participants 'joining' or 'leaving' the meeting.'
                    -Assign scores from 0 to 3:
                        0: Poor performance
                        1: Average performance
                        2: Good
                        3: Exceptional performance
                -Criteria:
                    -If the transcript lacks sufficient information to judge {score_criterion}, mark it as N/A and provide a clear explanation.
                    -Justify any score that is not a perfect 3.
                -Format for Evaluation:
                {score_criterion}:
                -Score: [SCORE]

                -Detailed Explanation with Examples:

                    -Overall Summary:
                    -Example 1: "[Quoted text from transcript]" [Description] [Timestamp]
                    -Example 2: "[Quoted text from transcript]" [Description] [Timestamp]
                    -Example 3: "[Quoted text from transcript]" [Description] [Timestamp]
                    -...
                    -Example n: "[Quoted text from transcript]" [Description] [Timestamp]
                -Include both positive and negative instances.
                -Highlight poor examples if the score is not ideal.

                Please evaluate the instructor: {instructor_name}

                Rate strictly on a scale of 0 to 3 using whole numbers only.

                Ensure the examples are directly relevant to the evaluation criterion and discard any irrelevant excerpts.
                """
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

    response = await asyncio.to_thread(chat, model='llama3', messages=payload['messages'], stream=payload['stream'])

    responses[score_criterion] = response

    content = response['message']['content']

    match = re.search(r'score:', content, re.IGNORECASE)
    if match:
        score_index = match.start()
        score_value = content[score_index + len("Score:"):].strip().split("\n")[0].strip()
        scores_dict[score_criterion] = score_value
    else:
        scores_dict[score_criterion] = "N/A"

    return responses, scores_dict
