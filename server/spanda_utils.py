from fastapi import FastAPI, WebSocket, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from ollama import chat as ollama_chat
from httpx import AsyncClient
import asyncio
import json
import httpx
import re
import ollama

import os
from pathlib import Path

from dotenv import load_dotenv
from starlette.websockets import WebSocketDisconnect
from wasabi import msg  # type: ignore[import]
import time
import logging
from goldenverba import verba_manager
from goldenverba.server.types import (
    ResetPayload,
    ConfigPayload,
    QueryPayload,
    GeneratePayload,
    GetDocumentPayload,
    SearchQueryPayload,
    ImportPayload,
    QueryRequest
)
from goldenverba.server.util import get_config, set_config, setup_managers

manager = verba_manager.VerbaManager()
setup_managers(manager)


async def chatbot(query, context):
    user_context = "".join(context)
    instructions = f"""You are an academic assistant chatbot. Your role is to answer questions based solely on the given context. If a question is outside the provided context, politely inform the user that you can only respond to questions within the given context. If someone asks about the chatbot, explain that you are an assistant designed to help users by answering academic and course-oriented questions."""
    payload = {
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": f"""
             Context: {user_context}"
             Query: {query}
             """
             }
        ],
        "stream": False,
        "options": {"top_k": 1, "top_p": 1, "temperature": 0, "seed": 100}
    }

    response = await asyncio.to_thread(ollama_chat, model='llama3.1', messages=payload['messages'], stream=payload['stream'])
    print(response['message']['content'])
    return response['message']['content']



# Retrieve context, prompt engineering and generation of AGA
async def grading_assistant(question_answer_pair, context):
    user_context = " ".join(context)
    # print(context)
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
                    -Score
                    -Explanation of score
                Readability:
                    -Score
                    -Explanation of score
                Comprehensiveness:
                    -Score
                    -Explanation of score
                            """
    payload = {
        "messages": [
            {"role": "system", "content": rubric_content},
            {"role": "user", "content": f"""Grade the following question-answer pair using the grading rubric and context provided - {question_answer_pair}"""}
        ],
        "stream": False,
        "options": {"top_k": 1, "top_p": 1, "temperature": 0, "seed": 100}
    }

    response = await asyncio.to_thread(ollama_chat, model='dolphin-llama3', messages=payload['messages'], stream=payload['stream'])
    
    # Define a dictionary to store extracted scores
    scores_dict = {}

    # Extract the response content
    response_content = response['message']['content']

    # Define the criteria to look for
    criteria = ["Correctness", "Readability", "Comprehensiveness"]

    # Iterate over each criterion
    for criterion in criteria:
        # Use regular expression to search for the criterion followed by 'Score:'
        criterion_pattern = re.compile(rf'{criterion}:\s*-?\s*Score\s*(\d+)', re.IGNORECASE)
        match = criterion_pattern.search(response_content)
        if match:
            # Extract the score value
            score_value = match.group(1).strip()
            scores_dict[criterion] = score_value
        else:
            scores_dict[criterion] = "N/A"


    return response['message']['content'], scores_dict


# Retrieve context, prompt engineering and generation of AFE
async def instructor_eval(instructor_name, context, score_criterion, explanation):
    # Define the criterion to evaluate
    user_context = "".join(context)
    # print(context)
    # Initialize empty dictionaries to store relevant responses and scores
    responses = {}
    scores_dict = {}

    # Evaluation prompt template
    # Evaluation prompt template
    evaluate_instructions = f"""
        [INST]
        -Instructions:
            You are tasked with evaluating a teacher's performance based on the criterion: {score_criterion} - {explanation}.

        -Evaluation Details:
            -Focus exclusively on the provided video transcript.
            -Ignore interruptions from student entries/exits and notifications of participants 'joining' or 'leaving' the meeting.
            -Assign scores from 1 to 5:
        -Criteria:
            -Criterion Explanation: {explanation}
            -If the transcript lacks sufficient information to judge {score_criterion}, mark it as N/A and provide a clear explanation.
            -Justify any score that is not a perfect 5.

        Strictly follow the output format-
        -Output Format:
            -{score_criterion}: score_obtained: score(range of 1 to 5, or N/A) - note: do not use any formatting in this

            -Detailed Explanation with Examples and justification for examples:
                -Example 1: "[Quoted text from transcript]" [Description] [Timestamp]
                -Example 2: "[Quoted text from transcript]" [Description] [Timestamp]
                -Example 3: "[Quoted text from transcript]" [Description] [Timestamp]
                -...
                -Example n: "[Quoted text from transcript]" [Description] [Timestamp]
            -Include both positive and negative instances.
            -Highlight poor examples if the score is not ideal.

            -Consider the context surrounding the example statements, as the context in which a statement is made is extremely important.

            Rate strictly on a scale of 1 to 5 using whole numbers only.

            Ensure the examples are directly relevant to the evaluation criterion and discard any irrelevant excerpts.
        [/INST]
    """
    system_message = """This is a chat between a user and a judge. The judge gives helpful, detailed, and polite suggestions for improvement for a particular teacher from the given context - the context contains transcripts of videos. The assistant should also indicate when the judgement be found in the context."""
    
    formatted_transcripts = f"""Here are given transcripts for {instructor_name}-   
                    [TRANSCRIPT START]
                    {user_context}
                    [TRANSCRIPT END]"""
    
    user_prompt = f"""Please provide an evaluation of the teacher named '{instructor_name}' on the following criteria: '{score_criterion}'. Only include information from transcripts where '{instructor_name}' is the instructor."""

    # Define the payload
    payload = {
        "messages": [
            {
                "role": "system",
                "content": system_message
            },
            {
                "role": "user",
                "content": formatted_transcripts + "/n/n" + evaluate_instructions + "/n/n" + user_prompt + " Strictly follow the format of output provided."
            }
        ],
        "stream": False,
        "options": {
            "top_k": 1, 
            "top_p": 1, 
            "temperature": 0, 
            "seed": 100, 
            # "num_ctx": 10000
            # "num_predict": 100,  # Reduced for shorter outputs
            # "repeat_penalty": 1.2,  # Adjusted to reduce repetition
            # "presence_penalty": 1.5, # Adjusted to discourage repeated concepts
            # "frequency_penalty": 1.0 # Adjusted to reduce frequency of repeated tokens
        }
    }

    # Asynchronous call to the LLM API
    response = await asyncio.to_thread(ollama.chat, model='llama3', messages=payload['messages'], stream=payload['stream'])

    # Store the response
    responses[score_criterion] = response

    # Extract the score from the response content
    content = response['message']['content']

    # Adjust the regular expression to handle various cases including 'Score:', direct number, asterisks, and new lines
    pattern = rf'(score:\s*([\s\S]*?)(\d+)|\**{score_criterion}\**\s*:\s*(\d+))'
    match = re.search(pattern, content, re.IGNORECASE)

    if match:
        # Check which group matched and extract the score
        if match.group(3):  # This means 'Score:' pattern matched
            score_value = match.group(3).strip()  # group(3) contains the number after 'Score:'
        elif match.group(4):  # This means direct number pattern matched
            score_value = match.group(4).strip()  # group(4) contains the number directly after score criterion
        else:
            score_value = "N/A"  # Fallback in case groups are not as expected
        scores_dict[score_criterion] = score_value
    else:
        scores_dict[score_criterion] = "N/A"

    # Return the responses dictionary and scores dictionary
    return responses, scores_dict


# Retrieve context, prompt engineering and generation of AQG
async def generate_question_variants(base_question, context):
    # Join the context into a single string
    user_context = " ".join(context)

    base_question_gen = f"""
            <s> [INST] As an inventive educator dedicated to nurturing critical thinking skills, your task is to devise a series of a number of distinct iterations of a mathematical problem or a textual problem. Each iteration should be rooted in a fundamental problem-solving technique, but feature diverse numerical parameters and creatively reworded text to discourage students from sharing answers. Your objective is to generate a collection of unique questions that not only promote critical thinking but also thwart easy duplication of solutions. Ensure that each variant presents different numerical values, yielding disparate outcomes. Each question should have its noun labels changed. Additionally, each question should stand alone without requiring reference to any other question, although they may share the same solving concept. Your ultimate aim is to fashion an innovative array of challenges that captivate students and inspire analytical engagement.
            Strictly ensure that the questions are relevant to the following context-
            {context}

            Strictly follow the format for your responses:
            generated_question_variants:
            1:Variant 1
            2:Variant 2
            3:Variant 3
            ..
            ..
            n:Variant n
            
            -Few-shot examples-
            *Example 1 (Textual):*
            Please generate 3 variants of the question: What is the capital of France?

            generated_question_variants-
            1:In which European country is Paris located?
            2:What is the capital of Italy?
            3:What is the capital of Spain?
            -This is a trivia quiz about geography.

            *Example 2 (Math):*
            Please generate 10 variants of the question: "What is the area of a rectangle with length 10 units and width 5 units?"
    
            generated_question_variants-
            1. Find the region enclosed by a shape with a length of 12 inches and a width of 6 inches.
            2. What is the total surface area of a rectangle that measures 8 meters in length and 4 meters in width?
            3. Determine the amount of space occupied by an object with dimensions 15 feet long and 7 feet wide.
            4. Calculate the region covered by a shape with a length of 9 centimeters and a width of 5 centimeters.
            5. What is the total area enclosed by a rectangle with a length of 11 meters and a width of 3 meters?
            6. Find the surface area of an object that measures 16 inches long and 8 inches wide.
            7. Discover the region occupied by a shape with dimensions 10 feet long and 4 feet wide.
            8. Calculate the total area enclosed by a rectangle with a length of 13 centimeters and a width of 6 centimeters.
            9. What is the surface area of an object that measures 12 meters long and 5 meters wide?
            10. Determine the amount of space occupied by an object with dimensions 9 inches long and 3 inches wide.
            -These are practice problems for basic geometry.

            Explanation: Notice how the the numerical values are changing. It is essential that the numerical values are different for each variant. The generated questions are similar to the originals but rephrased using different wording or focusing on a different aspect of the problem (area vs. perimeter, speed vs. time).
            [/INST]
        """

    # Define the payload for Ollama
    payload = {
        "messages": [
            {
                "role": "system",
                "content": base_question_gen
            },
            {
                "role": "user",
                "content": f"'{base_question}'",
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
    response = await asyncio.to_thread(ollama_chat, model='dolphin-llama3', messages=payload['messages'], stream=payload['stream'])
   
    content = response['message']['content']    

    variants_dict = extract_variants(base_question, content)
    print(variants_dict)
    # Return the response content
    return response['message']['content'], variants_dict

def extract_variants(base_question, content):
    pattern = r"\d+:\s*(.*)"
    matches = re.findall(pattern, content)
    variants = {base_question: matches}
    return variants

#for Ollama AGA
async def make_request(query_user):
    # Escape the query to handle special characters and newlines
    formatted_query = json.dumps(query_user)

    # Create a payload with the formatted query
    payload = QueryPayload(query=formatted_query)

    # Retrieve chunks and context
    chunks, context = manager.retrieve_chunks([payload.query])
    
    return context

# Answer generation function
async def answer_gen(question, context):
    user_context = "".join(context)
    answer_inst = """
        [INST]
        You are a highly knowledgeable and detailed assistant. Please follow these guidelines when generating answers:
        
        1. **Format**: Ensure the answer is nicely formatted and visually appealing. Use bullet points, numbered lists, headings, and subheadings where appropriate.
        
        2. **Clarity**: Provide clear and concise explanations. Avoid jargon unless it is necessary and explain it when used.
        
        3. **Math Questions**: 
        - Include all steps in the solution process.
        - Use clear and logical progression from one step to the next.
        - Explain each step briefly to ensure understanding.
        - Use LaTeX formatting for mathematical expressions to ensure they are easy to read and understand.

        4. **Non-Math Questions**:
        - Provide detailed explanations and context.
        - Break down complex ideas into simpler parts.
        - Use examples where appropriate to illustrate points.
        - Ensure the answer is comprehensive and addresses all parts of the question.
        
        5. **Tone**: Maintain a professional and friendly tone. Aim to be helpful and approachable.
        
        Here are a couple of examples to illustrate the format:

        **Math Question Example:**
        **Question:** Solve the equation \(2x^2 + 3x - 2 = 0\).
        
        **Answer:**
        To solve the quadratic equation \(2x^2 + 3x - 2 = 0\), we will use the quadratic formula:
        
        \[
        x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}
        \]
        
        Here, \(a = 2\), \(b = 3\), and \(c = -2\).
        
        1. Calculate the discriminant:
        \[
        b^2 - 4ac = 3^2 - 4 \cdot 2 \cdot (-2) = 9 + 16 = 25
        \]
        
        2. Find the square root of the discriminant:
        \[
        \sqrt{25} = 5
        \]
        
        3. Apply the quadratic formula:
        \[
        x = \frac{-3 \pm 5}{4}
        \]
        
        4. Solve for \(x\):
        \[
        x_1 = \frac{-3 + 5}{4} = \frac{2}{4} = 0.5
        \]
        \[
        x_2 = \frac{-3 - 5}{4} = \frac{-8}{4} = -2
        \]
        
        Therefore, the solutions are \(x = 0.5\) and \(x = -2\).
        
        **Non-Math Question Example:**
        **Question:** Explain the causes and effects of the Industrial Revolution.
        
        **Answer:**
        The Industrial Revolution, which began in the late 18th century, was a period of significant technological, socioeconomic, and cultural change. Here are the main causes and effects:
        
        **Causes:**
        1. **Technological Innovations**: Inventions such as the steam engine, spinning jenny, and power loom revolutionized production processes.
        2. **Agricultural Improvements**: Enhanced farming techniques increased food production, supporting a growing population.
        3. **Economic Factors**: Capital accumulation, the rise of banking, and the expansion of trade networks facilitated industrial growth.
        4. **Political Stability**: Stable governments in countries like Britain provided an environment conducive to industrial investment.
        
        **Effects:**
        1. **Urbanization**: Massive migration to cities led to urban growth and the development of new urban centers.
        2. **Economic Growth**: Industrialization spurred unprecedented economic expansion and wealth creation.
        3. **Social Changes**: The rise of a factory-based economy altered social structures, leading to the emergence of a new working class and changing labor dynamics.
        4. **Environmental Impact**: Industrial activities resulted in significant environmental changes, including pollution and deforestation.
        
        Overall, the Industrial Revolution had profound and lasting impacts on virtually every aspect of society.
        [/INST]
    """
    user_prompt = f"""Based on the context : {user_context}, 

                    Please answer the following question - {question}"""

    payload = {
        "messages": [
            {
                "role": "system",
                "content": answer_inst
            },
            {
                "role": "user",
                "content": f"""Query: {user_prompt}"""
            }
        ],
        "stream": False,
        "options": {
            "top_k": 1,
            "top_p": 1,
            "temperature": 0,
            "seed": 100
        }
    }

# AFE traits
dimensions = {
        "Knowledge of Content and Pedagogy": "Understanding the subject matter and employing effective teaching methods.\n"
                                            "1: The transcript demonstrates minimal knowledge of content and ineffective pedagogical practices.\n"
                                            "2: The transcript demonstrates basic content knowledge but lacks pedagogical skills.\n"
                                            "3: The transcript demonstrates adequate content knowledge and uses some effective pedagogical practices.\n"
                                            "4: The transcript demonstrates strong content knowledge and consistently uses effective pedagogical practices.\n"
                                            "5: The transcript demonstrates exceptional content knowledge and masterfully employs a wide range of pedagogical practices.",

        "Breadth of Coverage": "Extent to which the instructor covers the required curriculum.\n"
                            "1: The transcript shows that the instructor covers minimal content with significant gaps in the curriculum.\n"
                            "2: The transcript shows that the instructor covers some content but with notable gaps in the curriculum.\n"
                            "3: The transcript shows that the instructor covers most of the required content with minor gaps.\n"
                            "4: The transcript shows that the instructor covers all required content thoroughly.\n"
                            "5: The transcript shows that the instructor covers all required content and provides additional enrichment material.",

        "Knowledge of Resources": "Awareness and incorporation of teaching resources.\n"
                                "1: The transcript shows that the instructor demonstrates minimal awareness of resources available for teaching.\n"
                                "2: The transcript shows that the instructor demonstrates limited knowledge of resources and rarely incorporates them.\n"
                                "3: The transcript shows that the instructor demonstrates adequate knowledge of resources and sometimes incorporates them.\n"
                                "4: The transcript shows that the instructor demonstrates strong knowledge of resources and frequently incorporates them.\n"
                                "5: The transcript shows that the instructor demonstrates extensive knowledge of resources and consistently incorporates a wide variety of them.",

        "Content Clarity": "Ability to explain complex concepts clearly and effectively.\n"
                        "1: Does not break down complex concepts, uses confusing, imprecise, and inappropriate language, and does not employ any relevant techniques or integrate them into the lesson flow.\n"
                        "2: Inconsistently breaks down complex concepts using language that is sometimes confusing or inappropriate, employing few minimally relevant techniques that contribute little to student understanding, struggling to integrate them into the lesson flow.\n"
                        "3: Generally breaks down complex concepts using simple, precise language and some techniques that are somewhat relevant and contribute to student understanding, integrating them into the lesson flow with occasional inconsistencies.\n"
                        "4: Frequently breaks down complex concepts using simple, precise language and a variety of relevant, engaging techniques that contribute to student understanding.\n"
                        "5: Consistently breaks down complex concepts using simple, precise language and a wide variety of highly relevant, engaging techniques such as analogies, examples, visuals, etc., seamlessly integrating them into the lesson flow.",

        "Differentiation Strategies": "Using strategies to meet diverse student needs.\n"
                                    "1: Uses no differentiation strategies to meet diverse student needs.\n"
                                    "2: Uses minimal differentiation strategies with limited effectiveness.\n"
                                    "3: Uses some differentiation strategies with moderate effectiveness.\n"
                                    "4: Consistently uses a variety of differentiation strategies effectively.\n"
                                    "5: Masterfully employs a wide range of differentiation strategies to meet the needs of all learners.",

        "Communication Clarity": "The ability to convey information and instructions clearly and effectively so that students can easily understand the material being taught.\n"
                                "1: Communicates poorly with students, leading to confusion and misunderstandings.\n"
                                "2: Communicates with some clarity but often lacks precision or coherence.\n"
                                "3: Communicates clearly most of the time, with occasional lapses in clarity.\n"
                                "4: Consistently communicates clearly and effectively with students.\n"
                                "5: Communicates with exceptional clarity, precision, and coherence, ensuring full understanding.",

        "Punctuality": "Consistently starting and ending classes on time.\n"
                    "1: Transcripts consistently show late class start times and/or early end times.\n"
                    "2: Transcripts occasionally show late class start times and/or early end times.\n"
                    "3: Transcripts usually show on-time class start and end times.\n"
                    "4: Transcripts consistently show on-time class start and end times.\n"
                    "5: Transcripts always show early class start times and full preparation to begin class on time.",

        "Managing Classroom Routines": "Implementing strategies to maintain order, minimize disruptions, and ensure a productive and respectful classroom environment.\n"
                                    "1: Classroom routines are poorly managed, leading to confusion and lost instructional time.\n"
                                    "2: Classroom routines are somewhat managed but with frequent disruptions.\n"
                                    "3: Classroom routines are adequately managed with occasional disruptions.\n"
                                    "4: Classroom routines are well-managed, leading to smooth transitions and minimal disruptions.\n"
                                    "5: Classroom routines are expertly managed, maximizing instructional time and creating a seamless learning environment.",

        "Managing Student Behavior": "Managing student behavior effectively to promote a positive and productive learning environment.\n"
                                    "1: Struggles to manage student behavior, leading to frequent disruptions and an unproductive learning environment. Rarely encourages student participation, with little to no effort to ensure equal opportunities for engagement; provides no or inappropriate feedback and compliments that do not support learning or motivation.\n"
                                    "2: Manages student behavior with limited effectiveness, with some disruptions and off-task behavior. Inconsistently encourages student participation, with unequal opportunities for engagement; provides limited or generic feedback and compliments that minimally support learning and motivation.\n"
                                    "3: Manages student behavior adequately, maintaining a generally productive learning environment. Generally encourages student participation and provides opportunities for engagement, but some students may dominate or be overlooked; provides feedback and compliments, but they may not always be specific or constructive.\n"
                                    "4: Effectively manages student behavior, promoting a positive and productive learning environment. Frequently encourages student participation, provides fair opportunities for engagement, and offers appropriate feedback and compliments that support learning and motivation.\n"
                                    "5: Expertly manages student behavior, fostering a highly respectful, engaged, and self-regulated learning community. Consistently encourages active participation from all students, ensures equal opportunities for engagement, and provides specific, timely, and constructive feedback and compliments that enhance learning and motivation.",

        "Adherence to Rules": "Consistently following and enforcing classroom and school policies, ensuring that both the teacher and students abide by established guidelines.\n"
                            "1: Consistently disregards or violates school rules and policies.\n"
                            "2: Occasionally disregards or violates school rules and policies.\n"
                            "3: Generally adheres to school rules and policies with occasional lapses.\n"
                            "4: Consistently adheres to school rules and policies.\n"
                            "5: Strictly adheres to school rules and policies and actively promotes compliance among students.",

        "Organization": "Organizing and presenting content in a structured and logical manner.\n"
                        "1: Transcripts indicate content that is poorly organized, with minimal structure and no clear emphasis on important content. Linking between content is absent or confusing.\n"
                        "2: Transcripts indicate content that is somewhat organized but lacks a consistent structure and comprehensive coverage. Emphasis on important content is inconsistent, and linking between content is weak.\n"
                        "3: Transcripts indicate content that is adequately organized, with a generally clear structure and comprehensive coverage. Important content is usually emphasized, and linking between content is present.\n"
                        "4: Transcripts indicate content that is well-organized, with a consistent and clear structure and comprehensive coverage. Important content is consistently emphasized, and linking between content is effective.\n"
                        "5: Transcripts indicate content that is exceptionally well-organized, with a highly structured, logical, and comprehensive presentation. Important content is strategically emphasized, and linking between content is seamless and enhances learning.",

        "Clarity of Instructional Objectives": "Presenting content clearly and effectively to facilitate understanding and mastery.\n"
                                            "1: Content is presented in a confusing or unclear manner.\n"
                                            "2: Content is presented with some clarity but with frequent gaps or inconsistencies.\n"
                                            "3: Content is presented with adequate clarity, allowing for general understanding.\n"
                                            "4: Content is presented with consistent clarity, promoting deep understanding.\n"
                                            "5: Content is presented with exceptional clarity, facilitating mastery and transfer of knowledge.",

        "Alignment with the Curriculum": "Ensuring instruction aligns with curriculum standards and covers required content.\n"
                                        "1: Instruction is poorly aligned with the curriculum, with significant gaps or deviations.\n"
                                        "2: Instruction is somewhat aligned with the curriculum but with frequent inconsistencies.\n"
                                        "3: Instruction is generally aligned with the curriculum, covering most required content.\n"
                                        "4: Instruction is consistently aligned with the curriculum, covering all required content.\n"
                                        "5: Instruction is perfectly aligned with the curriculum, covering all required content and providing meaningful extensions.",

        "Instructor Enthusiasm And Positive Demeanor": "Exhibiting a positive attitude and enthusiasm for teaching, inspiring student engagement.\n"
                                                    "1: Instructor exhibits a negative or indifferent demeanor and lacks enthusiasm for teaching.\n"
                                                    "2: Instructor exhibits a neutral demeanor and occasional enthusiasm for teaching.\n"
                                                    "3: Instructor exhibits a generally positive demeanor and moderate enthusiasm for teaching.\n"
                                                    "4: Instructor exhibits a consistently positive demeanor and strong enthusiasm for teaching.\n"
                                                    "5: Instructor exhibits an exceptionally positive demeanor and infectious enthusiasm for teaching, greatly inspiring student engagement.",

        "Awareness and Responsiveness to Student Needs": "Demonstrating attentiveness and responding appropriately to student needs and feedback.\n"
                                                        "1: Lacks awareness of or fails to respond to student needs and feedback.\n"
                                                        "2: Occasionally demonstrates awareness of and responds to student needs and feedback.\n"
                                                        "3: Generally demonstrates awareness of and responds to student needs and feedback.\n"
                                                        "4: Consistently demonstrates awareness of and responds to student needs and feedback.\n"
                                                        "5: Highly attuned to and proactively responds to student needs and feedback, fostering a supportive learning environment."
    }





dimensions_AFE = {
        # Example structure, fill in with actual dimensions and sub-dimensions
      "Mastery of the Subject": {
            "weight": 0.169,
            "sub-dimensions": {
                "Knowledge of Content and Pedagogy": {
                    "weight": 0.362,
                    "definition": "A deep understanding of their subject matter and the best practices for teaching it.",
                    "example": "In a mathematics course on real analysis, the professor demonstrates best practices by Guiding students through the process of constructing formal proofs step-by-step, highlighting common pitfalls and techniques for overcoming them.",
                    "criteria": {
                        1: "The transcript demonstrates minimal knowledge of content and ineffective pedagogical practices",
                        2: "The transcript demonstrates basic content knowledge but lacks pedagogical skills",
                        3: "The transcript demonstrates adequate content knowledge and uses some effective pedagogical practices",
                        4: "The transcript demonstrates strong content knowledge and consistently uses effective pedagogical practices",
                        5: "The transcript demonstrates exceptional content knowledge and masterfully employs a wide range of pedagogical practices"
                    }
                },
                # "Breadth of Coverage": {
                #     "weight": 0.327,
                #     "definition": "Awareness of different possible perspectives related to the topic taught",
                #     "example": "Teacher discusses different theoretical views, current and prior scientific developments, etc.",
                #     "criteria": {
                #         1: "The transcript shows that the instructor covers minimal content with significant gaps in the curriculum",
                #         2: "The transcript shows that the instructor covers some content but with notable gaps in the curriculum",
                #         3: "The transcript shows that the instructor covers most of the required content with minor gaps",
                #         4: "The transcript shows that the instructor covers all required content thoroughly",
                #         5: "The transcript shows that the instructor covers all required content and provides additional enrichment material"
                #     }
                # },
                "Knowledge of Resources": {
                    "weight": 0.310,
                    "definition": "Awareness of and utilization of a variety of current resources in the subject area to enhance instruction",
                    "example": "The teacher cites recent research studies or books while explaining relevant concepts.",
                    "criteria": {
                        1: "The transcript shows that the instructor demonstrates minimal awareness of resources available for teaching",
                        2: "The transcript shows that the instructor demonstrates limited knowledge of resources and rarely incorporates them",
                        3: "The transcript shows that the instructor demonstrates adequate knowledge of resources and sometimes incorporates them",
                        4: "The transcript shows that the instructor demonstrates strong knowledge of resources and frequently incorporates them",
                        5: "The transcript shows that the instructor demonstrates extensive knowledge of resources and consistently incorporates a wide variety of them"
                    }
                }
            }
        },
        "Expository Quality": {
            "weight": 0.179,
            "sub-dimensions": {
                "Content Clarity": {
                    "weight": 0.266,
                    "definition": "Extent to which the teacher is able to explain the content to promote clarity and ease of understanding.",
                    "example": "Teacher uses simple vocabulary and concise sentences to explain complex concepts.",
                    "criteria": {
                        1: "Does not break down complex concepts, uses confusing, imprecise, and inappropriate language, and does not employ any relevant techniques or integrate them into the lesson flow.",
                        2: "Inconsistently breaks down complex concepts using language that is sometimes confusing or inappropriate, employing few minimally relevant techniques that contribute little to student understanding, struggling to integrate them into the lesson flow.",
                        3: "Generally breaks down complex concepts using simple, precise language and some techniques that are somewhat relevant and contribute to student understanding, integrating them into the lesson flow with occasional inconsistencies.",
                        4: "Frequently breaks down complex concepts using simple, precise language and a variety of relevant, engaging techniques that contribute to student understanding.",
                        5: "Consistently breaks down complex concepts using simple, precise language and a wide variety of highly relevant, engaging techniques such as analogies, examples, visuals, etc. to student understanding, seamlessly integrating them into the lesson flow."
                    }
                },
                # "Demonstrating Flexibility and Responsiveness": {
                #     "weight": 0.248,
                #     "definition": "Ability to adapt to the changing needs of the students in the class while explaining the concepts.",
                #     "example": "The teacher tries to explain a concept using a particular example. On finding that the students are unable to understand, the teacher is able to produce alternate examples or explanation strategies to clarify the concept.",
                #     "criteria": {
                #         1: "Fails to adapt explanations based on student needs and does not provide alternate examples or strategies.",
                #         2: "Rarely adapts explanations, often sticking to the same methods even when students struggle to understand.",
                #         3: "Sometimes adapts explanations and provides alternate examples or strategies, but with limited effectiveness.",
                #         4: "Frequently adapts explanations and offers a variety of alternate examples or strategies that aid student understanding.",
                #         5: "Consistently and seamlessly adapts explanations, providing a wide range of highly effective alternate examples or strategies tailored to student needs."
                #     }
                # },
                "Differentiation Strategies": {
                    "weight": 0.246,
                    "definition": "The methods and approaches used by the teacher to accommodate diverse student needs, backgrounds, learning styles, and abilities.",
                    "example": "During a lesson, the teacher divides the class into small groups based on their readiness levels. She provides more advanced problems for students who grasp the concept quickly, while offering additional support and manipulatives for students who need more help.",
                    "criteria": {
                        1: "Uses no differentiation strategies to meet diverse student needs",
                        2: "Uses minimal differentiation strategies with limited effectiveness",
                        3: "Uses some differentiation strategies with moderate effectiveness",
                        4: "Consistently uses a variety of differentiation strategies effectively",
                        5: "Masterfully employs a wide range of differentiation strategies to meet the needs of all learners"
                    }
                },
                "Communication Clarity": {
                    "weight": 0.238,
                    "definition": "The ability of the teacher to effectively convey information and instructions to students in a clear and understandable manner.",
                    "example": "The teachers voice and language is clear with the use of appropriate voice modulation, tone, and pitch to facilitate ease of understanding.",
                    "criteria": {
                        1: "Communicates poorly with students, leading to confusion and misunderstandings",
                        2: "Communicates with some clarity but often lacks precision or coherence",
                        3: "Communicates clearly most of the time, with occasional lapses in clarity",
                        4: "Consistently communicates clearly and effectively with students",
                        5: "Communicates with exceptional clarity, precision, and coherence, ensuring full understanding"
                    }
                }
            }
        },
        "Class Management": {
            "weight": 0.150,
            "sub-dimensions": {
                "Punctuality": {
                    "weight": 0.261,
                    "definition": "The consistency and timeliness of the teacher's arrival to class sessions, meetings, and other professional obligations.",
                    "example": "The teacher starts and completes live lectures as per the designated time.",
                    "criteria": {
                        1: "Transcripts consistently show late class start times and/or early end times",
                        2: "Transcripts occasionally show late class start times and/or early end times",
                        3: "Transcripts usually show on-time class start and end times",
                        4: "Transcripts consistently show on-time class start and end times",
                        5: "Transcripts always show early class start times and full preparation to begin class on time"
                    }
                },
                "Managing Classroom Routines": {
                    "weight": 0.255,
                    "definition": "The Teacher establishes and maintains efficient routines and procedures to maximize instructional time.",
                    "example": "The teacher starts every session with a recap quiz to remind learners of what was taught earlier. Students prepare for the recap even before the teacher enters the class in a habitual manner.",
                    "criteria": {
                        1: "Classroom routines are poorly managed, leading to confusion and lost instructional time",
                        2: "Classroom routines are somewhat managed but with frequent disruptions",
                        3: "Classroom routines are adequately managed with occasional disruptions",
                        4: "Classroom routines are well-managed, leading to smooth transitions and minimal disruptions",
                        5: "Classroom routines are expertly managed, maximizing instructional time and creating a seamless learning environment"
                    }
                },
                "Managing Student Behavior": {
                    "weight": 0.240,
                    "definition": "The teacher sets clear expectations for behavior and uses effective strategies to prevent and address misbehavior. The teacher encourages student participation and provides fair and equal opportunities to all students in class. The teacher also provides appropriate compliments and feedback to learners’ responses.",
                    "example": "The teacher addresses a students misbehavior in the class in a professional manner and provides constructive feedback using clear guidelines for student behavior expected in the course.",
                    "criteria": {
                        1: "Struggles to manage student behavior, leading to frequent disruptions and an unproductive learning environment. Rarely encourages student participation, with little to no effort to ensure equal opportunities for engagement; provides no or inappropriate feedback and compliments that do not support learning or motivation.",
                        2: "Manages student behavior with limited effectiveness, with some disruptions and off-task behavior. Inconsistently encourages student participation, with unequal opportunities for engagement; provides limited or generic feedback and compliments that minimally support learning and motivation.",
                        3: "Manages student behavior adequately, maintaining a generally productive learning environment. Generally encourages student participation and provides opportunities for engagement, but some students may dominate or be overlooked; provides feedback and compliments, but they may not always be specific or constructive.",
                        4: "Effectively manages student behavior, promoting a positive and productive learning environment. Frequently encourages student participation, provides fair opportunities for engagement, and offers appropriate feedback and compliments that support learning and motivation.",
                        5: "Expertly manages student behavior, fostering a highly respectful, engaged, and self-regulated learning community. Consistently encourages active participation from all students, ensures equal opportunities for engagement, and provides specific, timely, and constructive feedback and compliments that enhance learning and motivation."
                    }
                },
                # "Adherence to Rules": {
                #     "weight": 0.242,
                #     "definition": "The extent to which the teacher follows established rules, procedures, and policies governing classroom conduct and professional behavior.",
                #     "example": "The teacher reminds the students to not circulate cracked versions of a software on the class discussion forum.",
                #     "criteria": {
                #         1: "Consistently disregards or violates school rules and policies",
                #         2: "Occasionally disregards or violates school rules and policies",
                #         3: "Generally adheres to school rules and policies with occasional lapses",
                #         4: "Consistently adheres to school rules and policies",
                #         5: "Strictly adheres to school rules and policies and actively promotes compliance among students"
                #     }
                # }
            }
        },
        "Structuring of Objectives and Content": {
            "weight": 0.168,
            "sub-dimensions": {
                "Organization": {
                    "weight": 0.338,
                    "definition": "The extent to which content is presented in a structured and comprehensive manner with emphasis on important content and proper linking content.",
                    "example": "Teacher starts the class by providing an outline of what all will be covered in that particular class and connects it to previous knowledge of learners.",
                    "criteria": {
                        1: "Transcripts indicate content that is poorly organized, with minimal structure and no clear emphasis on important content. Linking between content is absent or confusing.",
                        2: "Transcripts indicate content that is somewhat organized but lacks a consistent structure and comprehensive coverage. Emphasis on important content is inconsistent, and linking between content is weak",
                        3: "Transcripts indicate content that is adequately organized, with a generally clear structure and comprehensive coverage. Important content is usually emphasized, and linking between content is present.",
                        4: "Transcripts indicate content that is well-organized, with a consistent and clear structure and comprehensive coverage. Important content is consistently emphasized, and linking between content is effective.",
                        5: "Transcripts indicate content that is exceptionally well-organized, with a highly structured, logical, and comprehensive presentation. Important content is strategically emphasized, and linking between content is seamless and enhances learning."
                    }
                },
                "Clarity of Instructional Objectives": {
                    "weight": 0.342,
                    "definition": "The clarity and specificity of the learning objectives communicated to students, guiding the focus and direction of instruction.",
                    "example": "At the start of the lesson, the teacher displays the learning objectives and takes a few moments to explain them to the students.",
                    "criteria": {
                        1: "Content is presented in a confusing or unclear manner",
                        2: "Content is presented with some clarity but with frequent gaps or inconsistencies",
                        3: "Content is presented with adequate clarity, allowing for general understanding",
                        4: "Content is presented with consistent clarity, promoting deep understanding",
                        5: "Content is presented with exceptional clarity, facilitating mastery and transfer of knowledge"
                    }
                },
                "Alignment with the Curriculum": {
                    "weight": 0.319,
                    "definition": "The degree to which the teacher's instructional plans and activities align with the prescribed curriculum objectives and standards.",
                    "example": "The teacher discusses a unit plan that clearly shows the connections between her learning objectives, instructional activities, assessments, and the corresponding curriculum standards.",
                    "criteria": {
                        1: "Instruction is poorly aligned with the curriculum, with significant gaps or deviations",
                        2: "Instruction is somewhat aligned with the curriculum but with frequent inconsistencies",
                        3: "Instruction is generally aligned with the curriculum, covering most required content",
                        4: "Instruction is consistently aligned with the curriculum, covering all required content",
                        5: "Instruction is perfectly aligned with the curriculum, covering all required content and providing meaningful extensions"
                    }
                }
            }
        },
        "Qualities of Interaction": {
            "weight": 0.168,
            "sub-dimensions": {
                "Instructor Enthusiasm And Positive demeanor": {
                    "weight": 0.546,
                    "definition": "Extent to which a teacher is enthusiastic and committed to making the course interesting, active, dynamic, humorous, etc.",
                    "example": "Teacher uses an interesting fact or joke to engage the class.",
                    "criteria": {
                        1: "Instructor exhibits a negative or indifferent demeanor and lacks enthusiasm for teaching",
                        2: "Instructor exhibits a neutral demeanor and occasional enthusiasm for teaching",
                        3: "Instructor exhibits a generally positive demeanor and moderate enthusiasm for teaching",
                        4: "Instructor exhibits a consistently positive demeanor and strong enthusiasm for teaching",
                        5: "Instructor exhibits an exceptionally positive demeanor and infectious enthusiasm for teaching, inspiring student engagement"
                    }
                },
                "Individual Rapport": {
                    "weight": 0.453,
                    "definition": "Extent to which the teacher develops a rapport with individual students and their concerns during and beyond class hours. The teacher provides assistance, guidance, and resources to help students overcome obstacles, address challenges, and achieve success.",
                    "example": "Teacher shows an interest in student concerns, and attempts to resolve individual queries both during the class and through forums/individual communication.",
                    "criteria": {
                        1: "Minimal or negative rapport with individual students interactions",
                        2: "Limited rapport with individual students, with infrequent personalized",
                        3: "Adequate rapport with individual students, with some personalized interactions",
                        4: "Strong rapport with individual students, with frequent personalized interactions and support",
                        5: "Exceptional rapport with each individual student, with highly personalized interactions, support, and guidance"
                    }
                }
            }
        },
        "Evaluation of Learning": {
            "weight": 0.163,
            "sub-dimensions": {
                "Course Level Assessment": {
                    "weight": 0.333,
                    "definition": "The course level assessment is in line with the curriculum of the course and effectively checks whether the course outcomes are being met.",
                    "example": "The teacher selects or uses test items that reflect the course outcome.",
                    "criteria": {
                        1: "The course level assessment is not aligned with the curriculum, does not cover course outcomes, and uses methods that are ineffective in measuring student achievement of these outcomes.",
                        2: "The course level assessment is poorly aligned with the curriculum, covers few course outcomes, and uses methods that are limited in their ability to effectively measure student achievement of these outcomes.",
                        3: "The course level assessment is generally aligned with the curriculum, covers some course outcomes, and uses methods that adequately measure student achievement of these outcomes, but may have minor gaps or inconsistencies.",
                        4: "The course level assessment is well-aligned with the curriculum, covers most course outcomes, and uses appropriate methods to effectively measure student achievement of these outcomes.",
                        5: "The course level assessment is perfectly aligned with the curriculum, comprehensively covers all course outcomes, and employs highly effective methods to accurately measure student achievement of these outcomes."
                    }
                },
                "Clear Grading Criteria": {
                    "weight": 0.333,
                    "definition": "The teacher uses a clear and structured rubric which is communicated to the learners prior to any evaluation. The teacher is not biased in their assessment of learner performance.",
                    "example": "The teacher discusses the assessment rubric by providing examples of good responses and the criteria for grading with the learners before conducting any tests.",
                    "criteria": {
                        1: "The teacher rarely or never uses a rubric, does not communicate assessment criteria to learners before evaluation, and the teacher's assessment is highly biased and unfair.",
                        2: "The teacher inconsistently uses a rubric that is poorly structured or not clearly communicated to learners before evaluation, and the teacher's assessment may be noticeably biased at times.",
                        3: "The teacher generally uses a rubric that is communicated to learners before evaluation, but the rubric may lack some clarity or structure, and the teacher's assessment may occasionally show minor bias.",
                        4: "The teacher frequently uses a clear and structured rubric that is communicated to learners prior to evaluation, and applies the rubric fairly to all learners with minimal bias.",
                        5: "The teacher consistently uses a well-defined, comprehensive rubric that is clearly communicated to learners well in advance of any evaluation, and applies the rubric objectively and fairly to all learners without any bias."
                    }
                },
                "Assignments/readings": {
                    "weight": 0.332,
                    "definition": "The teacher provides assignments/homework/literature which is relevant and contributes to a deeper understanding of the topics taught to track the progress of learners. The teacher also discusses the solutions and feedback based on previously assigned homework/assignment.",
                    "example": "The teacher provides clear instructions on the homework task that the students are given and how it is relevant to the topics taught in class. In the following class, the teacher discusses the answers and any common mistakes made by learners.",
                    "criteria": {
                        1: "The teacher rarely or never provides relevant assignments, homework, or literature that contribute to understanding the topics taught, does not track learner progress, and fails to discuss solutions and feedback based on previous work.",
                        2: "The teacher inconsistently provides assignments, homework, and literature that are minimally relevant and contribute little to understanding the topics taught, rarely tracks learner progress, and seldom discusses solutions and feedback based on previous work.",
                        3: "The teacher generally provides assignments, homework, and literature that are somewhat relevant and contribute to understanding the topics taught, occasionally tracks learner progress, and sometimes discusses solutions and feedback based on previous work.",
                        4: "The teacher frequently provides relevant assignments, homework, and literature that contribute to a deeper understanding of the topics taught, tracks learner progress, and discusses solutions and feedback based on previously assigned work.",
                        5: "The teacher consistently provides highly relevant and challenging assignments, homework, and literature that significantly deepen learners' understanding of the topics taught, regularly tracks learner progress, and engages in thorough discussions of solutions and feedback based on previous work."
                    }
                }
            }
        }
    
    }
