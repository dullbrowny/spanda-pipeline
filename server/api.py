from fastapi import FastAPI, WebSocket, File, UploadFile, status, HTTPException, Request, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from ollama import chat as ollama_chat
from httpx import AsyncClient
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import aiohttp
import torch
from typing import Optional
import json
import httpx
import re , asyncio
import zipfile
import ollama
from pydantic import BaseModel
import base64
import logging 
from typing import List
from fastapi import BackgroundTasks
import os
from pathlib import Path
from dotenv import load_dotenv
from starlette.websockets import WebSocketDisconnect
from goldenverba.server.types import CourseIDRequest,AuthDetails, Token, TokenData, Course, TokenWithRoles, RequestAGA
from wasabi import msg  # type: ignore[import]
import time
import hashlib
import random
import string
# from goldenverba.server.bitsp import(
#     ollama_afe,
#     ollama_aga,
#     ollama_aqg
# )
import logging
from typing import Optional, List, Dict, Any
from goldenverba import verba_manager
from goldenverba.server.types import (
    ResetPayload,
    ConfigPayload,
    QueryPayload,
    GeneratePayload,
    GetDocumentPayload,
    SearchQueryPayload,
    ImportPayload,
    QueryRequest,
    MoodleRequest,
    QueryRequestaqg
)
from typing import Dict
from goldenverba.server.spanda_utils import chatbot, dimensions_AFE
import requests
from docx import Document
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import re
import csv
import httpx
import asyncio
import jwt
import hashlib
from bs4 import BeautifulSoup
import random
import string
from datetime import datetime, timedelta 
from goldenverba.server.util import get_config, set_config, setup_managers
logger = logging.getLogger("API")
load_dotenv()
# Replace with your Moodle instance URL and token

current_dir = os.path.dirname(__file__)

# Step 2: Move up one directory level to 'goldenverba'
base_dir = os.path.abspath(os.path.join(current_dir, '..'))

# Step 3: Create the relative path to the .env file
dotenv_path = os.path.join(base_dir, '.env')

# Step 4: Load the .env file
load_dotenv(dotenv_path)

# Now you can access the environment variables
SECRET_KEY = os.getenv('SECRET_KEY')
ALGORITHM = os.getenv('ALGORITHM')
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES'))
MOODLE_URL = os.getenv('MOODLE_URL')
LOGIN_URL = f'{MOODLE_URL}/login/index.php' 
ACCESS_URL = f'{MOODLE_URL}/webservice/rest/server.php'
TOKEN = os.getenv('TOKEN')
# Check if runs in production
production_key = os.environ.get("VERBA_PRODUCTION", "")
tag = os.environ.get("VERBA_GOOGLE_TAG", "")
if production_key == "True":
    msg.info("API runs in Production Mode")
    production = True
else:
    production = False

manager = verba_manager.VerbaManager()
setup_managers(manager)

# FastAPI App
app = FastAPI()

origins = [
    "http://localhost:3000",
    "http://localhost:4000",
    "http://localhost:6000",
    "http://localhost:5000",
    "https://verba-golden-ragtriever.onrender.com",
    "http://localhost:8000",
    "http://localhost:1511",
    "http://localhost/moodle", 
    "http://localhost", 
    "https://taxila-spanda.wilp-connect.net",
    "https://bitsmart.vercel.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent

# Serve the assets (JS, CSS, images, etc.)
app.mount(
    "/static/_next",
    StaticFiles(directory=BASE_DIR / "frontend/out/_next"),
    name="next-assets",
)

# Serve the main page and other static files
app.mount("/static", StaticFiles(directory=BASE_DIR / "frontend/out"), name="app")


@app.get("/")
@app.head("/")
async def serve_frontend():
    return FileResponse(os.path.join(BASE_DIR, "frontend/out/index.html"))
# Constants
editing_teacher_courses: List[str] = []

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# Function to make a Moodle API call
def moodle_api_call(params, extra_params=None):
    if extra_params:
        params.update(extra_params)
    endpoint = f'{MOODLE_URL}/webservice/rest/server.php'
    response = requests.get(endpoint, params=params)
    print(f"API Call to {params['wsfunction']} - Status Code: {response.status_code}")
    print(f"API Request URL: {response.url}")  # Log the full URL for debugging

    try:
        result = response.json()
    except ValueError as e:
        raise ValueError(f"Error parsing JSON response: {response.text}") from e

    if 'exception' in result:
        raise Exception(f"Error: {result['exception']['message']}")

    return result


# Function to get the user ID by username
def authenticate_user(username: str, password: str) -> Optional[dict]:
    global editing_teacher_courses  # Access the global variable
    
    credentials = {
        'username': username,
        'password': password
    }
    
    with requests.Session() as session:
        try:
            response = session.get(LOGIN_URL)
            response.raise_for_status()
            print("Login page fetched successfully.")
        except requests.RequestException as e:
            print(f"Failed to get login page: {e}")
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        logintoken = soup.find('input', {'name': 'logintoken'})
        if logintoken:
            credentials['logintoken'] = logintoken['value']
            print("Login token found:", logintoken['value'])
        else:
            print("Login token not found. Check if the login page structure has changed.")
            return None
        
        try:
            response = session.post(LOGIN_URL, data=credentials)
            response.raise_for_status()
            print("Login attempt response status code:", response.status_code)
        except requests.RequestException as e:
            print(f"Login failed: {e}")
            return None
        
        if 'Log out' in response.text:
            print("Login successful.")
            userid = get_user_id_by_username(TOKEN, ACCESS_URL, username)
            if userid:
                print("User ID found:", userid)
                courses = get_user_courses(TOKEN, ACCESS_URL, userid)
                if not courses:
                    print("No courses found for user.")
                
                global editing_teacher_courses
                editing_teacher_courses = []  # Reset the global variable
                roles_found = []
                
                for course in courses:
                    roles = get_user_role_in_course(TOKEN, ACCESS_URL, course['id'], userid)
                    course_roles = [role['shortname'] for role in roles]
                    print("Roles found for course:", course.get('shortname', 'Unnamed Course'), course_roles)
                    
                    if 'editingteacher' in course_roles:
                        editing_teacher_courses.append(course['shortname'])  # Append only the shortname
                        roles_found.append('editingteacher')
                        print("User has 'editingteacher' role in course:", course.get('shortname', 'Unnamed Course'))
                    
                    if 'manager' in course_roles:
                        roles_found.append('manager')
                        print("User has 'manager' role in course:", course.get('shortname', 'Unnamed Course'))
                        
                print("Roles found for user:", roles_found)
                if roles_found:
                    # Generate an access token with the roles embedded in the payload
                    token = create_access_token(data={"sub": username, "roles": roles_found})
                    return {"access_token": token, "roles": roles_found}
                else:
                    print("No valid roles found for user.")
                    return None
            else:
                print("User ID not found.")
                return None
        else:
            print("Login failed or unexpected response.")
            return None
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise ValueError("Invalid authentication credentials")
        return TokenData(username=username)
    except jwt.PyJWTError as e:
        print(f"Token verification failed: {e}")
        raise ValueError("Invalid authentication credentials")

def get_current_user(request: Request) -> TokenData:
    auth_header = request.headers.get("Authorization")
    if auth_header is None or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or malformed"
        )
    
    token = auth_header[len("Bearer "):]
    return verify_token(token)

def get_user_id_by_username(token, moodle_url, username):
    params = {
        "wstoken": token,
        "wsfunction": "core_user_get_users_by_field",
        "moodlewsrestformat": "json",
        "field": "username",
        "values[0]": username
    }
    try:
        response = requests.get(moodle_url, params=params)
        response.raise_for_status()
        print("User ID fetch response status code:", response.status_code)
        print("Response Text:", response.text)
        users = response.json()
        if users:
            return users[0]['id']
    except (requests.RequestException, requests.exceptions.JSONDecodeError) as e:
        print(f"Error fetching user ID: {e}")
    return None

def get_user_courses(token, moodle_url, userid):
    params = {
        "wstoken": token,
        "wsfunction": "core_enrol_get_users_courses",
        "moodlewsrestformat": "json",
        "userid": userid
    }
    try:
        response = requests.get(moodle_url, params=params)
        response.raise_for_status()
        print("User courses fetch response status code:", response.status_code)
        print("Response Text:", response.text)
        return response.json()
    except (requests.RequestException, requests.exceptions.JSONDecodeError) as e:
        print(f"Error fetching user courses: {e}")
    return []

def get_user_role_in_course(token, moodle_url, courseid, userid):
    params = {
        "wstoken": token,
        "wsfunction": "core_enrol_get_enrolled_users",
        "moodlewsrestformat": "json",
        "courseid": courseid
    }
    try:
        response = requests.get(moodle_url, params=params)
        response.raise_for_status()
        print("User roles fetch response status code:", response.status_code)
        print("Response Text:", response.text)
        users = response.json()
        for user in users:
            if user['id'] == userid:
                return user['roles']
    except (requests.RequestException, requests.exceptions.JSONDecodeError) as e:
        print(f"Error fetching user roles: {e}")
    return []

# FastAPI endpoints
@app.post("/token", response_model=TokenWithRoles)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    auth_data = authenticate_user(form_data.username, form_data.password)
    print("AUTH", auth_data)
    if auth_data is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    print("Returning access token and roles:", auth_data)
    return {
        "access_token": auth_data["access_token"],
        "token_type": "bearer",
        "roles": auth_data["roles"]
    }


@app.get("/check-auth")
async def check_auth(current_user: TokenData = Depends(get_current_user)): 
    return {"status": "authenticated", "user": current_user.username}


@app.get("/editing_teacher_courses", response_model=List[str])
def get_editing_teacher_courses():
    if not editing_teacher_courses:
        raise HTTPException(status_code=404, detail="No courses found.")
    return editing_teacher_courses

# @app.post("/api/spandachat")
# async def spanda_chat(request: QueryRequest, token: str = Depends(oauth2_scheme)):
    
#     get_current_user(token)
#     context = await make_request(request.query)
#     if context is None:
#         raise HTTPException(status_code=500, detail="Failed to fetch context")
    
#     answer = await chatbot(request.query, context)
#     return {"answer": answer}


# Define health check endpoint
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.get("/api/health")
async def health_check():
    try:
        logger.info("Health check initiated.")
        if manager.client.is_ready():
            logger.info("Database is ready.")
            return JSONResponse(
                content={"message": "Alive!", "production": production, "gtag": tag}
            )
        else:
            logger.warning("Database not ready.")
            return JSONResponse(
                content={
                    "message": "Database not ready!",
                    "production": production,
                    "gtag": tag,
                },
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
    except Exception as e:
        logger.error(f"Healthcheck failed with {str(e)}")
        return JSONResponse(
            content={
                "message": f"Healthcheck failed with {str(e)}",
                "production": production,
                "gtag": tag,
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

# Get Status meta data
@app.get("/api/get_status")
async def get_status():
    try:
        schemas = manager.get_schemas()
        sorted_schemas = dict(
            sorted(schemas.items(), key=lambda item: item[1], reverse=True)
        )

        sorted_libraries = dict(
            sorted(
                manager.installed_libraries.items(),
                key=lambda item: (not item[1], item[0]),
            )
        )
        sorted_variables = dict(
            sorted(
                manager.environment_variables.items(),
                key=lambda item: (not item[1], item[0]),
            )
        )

        data = {
            "type": manager.weaviate_type,
            "libraries": sorted_libraries,
            "variables": sorted_variables,
            "schemas": sorted_schemas,
            "error": "",
        }

        msg.info("Status Retrieved")
        return JSONResponse(content=data)
    except Exception as e:
        data = {
            "type": "",
            "libraries": {},
            "variables": {},
            "schemas": {},
            "error": f"Status retrieval failed: {str(e)}",
        }
        msg.fail(f"Status retrieval failed: {str(e)}")
        return JSONResponse(content=data)

# Get Configuration
@app.get("/api/config")
async def retrieve_config():
    try:
        config = get_config(manager)
        msg.info("Config Retrieved")
        return JSONResponse(status_code=200, content={"data": config, "error": ""})

    except Exception as e:
        msg.warn(f"Could not retrieve configuration: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "data": {},
                "error": f"Could not retrieve configuration: {str(e)}",
            },
        )

### WEBSOCKETS

@app.websocket("/ws/generate_stream")
async def websocket_generate_stream(websocket: WebSocket):
    await websocket.accept()
    while True:  # Start a loop to keep the connection alive.
        try:
            data = await websocket.receive_text()
            # Parse and validate the JSON string using Pydantic model
            payload = GeneratePayload.model_validate_json(data)
            msg.good(f"Received generate stream call for {payload.query}")
            full_text = ""
            async for chunk in manager.generate_stream_answer(
                [payload.query], [payload.context], payload.conversation
            ):
                full_text += chunk["message"]
                if chunk["finish_reason"] == "stop":
                    chunk["full_text"] = full_text
                await websocket.send_json(chunk)

        except WebSocketDisconnect:
            msg.warn("WebSocket connection closed by client.")
            break  # Break out of the loop when the client disconnects

        except Exception as e:
            msg.fail(f"WebSocket Error: {str(e)}")
            await websocket.send_json(
                {"message": e, "finish_reason": "stop", "full_text": str(e)}
            )
        msg.good("Succesfully streamed answer")

### POST

# Reset Verba
@app.post("/api/reset")
async def reset_verba(payload: ResetPayload):
    if production:
        return JSONResponse(status_code=200, content={})

    try:
        if payload.resetMode == "VERBA":
            manager.reset()
        elif payload.resetMode == "DOCUMENTS":
            manager.reset_documents()
        elif payload.resetMode == "CACHE":
            manager.reset_cache()
        elif payload.resetMode == "SUGGESTIONS":
            manager.reset_suggestion()
        elif payload.resetMode == "CONFIG":
            manager.reset_config()

        msg.info(f"Resetting Verba ({payload.resetMode})")

    except Exception as e:
        msg.warn(f"Failed to reset Verba {str(e)}")

    return JSONResponse(status_code=200, content={})

# Receive query and return chunks and query answer
@app.post("/api/import")
async def import_data(payload: ImportPayload):

    logging = []

    print(f"Received payload: {payload}")
    if production:
        logging.append(
            {"type": "ERROR", "message": "Can't import when in production mode"}
        )
        return JSONResponse(
            content={
                "logging": logging,
            }
        )

    try:
        set_config(manager, payload.config)
        documents, logging = manager.import_data(
            payload.data, payload.textValues, logging
        )

        return JSONResponse(
            content={
                "logging": logging,
            }
        )

    except Exception as e:
        logging.append({"type": "ERROR", "message": str(e)})
        return JSONResponse(
            content={
                "logging": logging,
            }
        )

@app.post("/api/set_config")
async def update_config(payload: ConfigPayload):

    if production:
        return JSONResponse(
            content={
                "status": "200",
                "status_msg": "Config can't be updated in Production Mode",
            }
        )

    try:
        set_config(manager, payload.config)
    except Exception as e:
        msg.warn(f"Failed to set new Config {str(e)}")

    return JSONResponse(
        content={
            "status": "200",
            "status_msg": "Config Updated",
        }
    )

# Receive query and return chunks and query answer
@app.post("/api/query")
async def query(payload: QueryPayload):
    msg.good(f"Received query: {payload.query}")
    msg.good(payload.query + "lol")
    start_time = time.time()  # Start timing
    # print(payload.course_id + "inapi.py")

    try:
        chunks, context = manager.retrieve_chunks(payload.query, payload.course_id)
        retrieved_chunks = [
            {
                "text": chunk.text,
                "doc_name": chunk.doc_name,
                "chunk_id": chunk.chunk_id,
                "doc_uuid": chunk.doc_uuid,
                "doc_type": chunk.doc_type,
                "score": chunk.score,
            }
            for chunk in chunks
        ]
        # print(retrieved_chunks)
        elapsed_time = round(time.time() - start_time, 2)  
        msg.good(f"Succesfully processed query: {payload.query} in {elapsed_time}s")    

        if len(chunks) == 0:
            return JSONResponse(
                content={
                    "chunks": [],
                    "took": 0,
                    "context": "",
                    "error": "No Chunks Available",
                }
            )

        return JSONResponse(
            content={
                "error": "",
                "chunks": retrieved_chunks,
                "context": context,
                "took": elapsed_time,
            }
        )

    except Exception as e:
        msg.warn(f"Query failed: {str(e)}")
        return JSONResponse(
            content={
                    "chunks": [],
                    "took": 0,
                    "context": "",
                    "error": f"Something went wrong: {str(e)}",
            }
        )

# Retrieve auto complete suggestions based on user input
@app.post("/api/suggestions")
async def suggestions(payload: QueryPayload):
    try:
        suggestions = manager.get_suggestions(payload.query)

        return JSONResponse(
            content={
                "suggestions": suggestions,
            }
        )
    except Exception:
        return JSONResponse(
            content={
                "suggestions": [],
            }
        )

# Retrieve specific document based on UUID
@app.post("/api/get_document")
async def get_document(payload: GetDocumentPayload):
    # TODO Standarize Document Creation
    msg.info(f"Document ID received: {payload.document_id}")

    try:
        document = manager.retrieve_document(payload.document_id)
        document_properties = document.get("properties", {})
        document_obj = {
            "class": document.get("class", "No Class"),
            "id": document.get("id", payload.document_id),
            "chunks": document_properties.get("chunk_count", 0),
            "link": document_properties.get("doc_link", ""),
            "name": document_properties.get("doc_name", "No name"),
            "type": document_properties.get("doc_type", "No type"),
            "text": document_properties.get("text", "No text"),
            "timestamp": document_properties.get("timestamp", ""),
        }

        msg.good(f"Succesfully retrieved document: {payload.document_id}")
        return JSONResponse(
            content={
                "error": "",
                "document": document_obj,
            }
        )
    except Exception as e:
        msg.fail(f"Document retrieval failed: {str(e)}")
        return JSONResponse(
            content={
                "error": str(e),
                "document": None,
            }
        )

## Retrieve and search documents imported to Weaviate
@app.post("/api/get_all_documents")
async def get_all_documents(payload: SearchQueryPayload):
    # TODO Standarize Document Creation
    msg.info("Get all documents request received")
    start_time = time.time()  # Start timing

    try:
        if payload.query == "":
            documents = manager.retrieve_all_documents(
                payload.doc_type, payload.page, payload.pageSize
            )
        else:
            documents = manager.search_documents(
                payload.query, payload.doc_type, payload.page, payload.pageSize
            )

        if not documents:
            return JSONResponse(
                content={
                    "documents": [],
                    "doc_types": [],
                    "current_embedder": manager.embedder_manager.selected_embedder,
                    "error": f"No Results found!",
                    "took": 0,
                }
            )

        documents_obj = []
        for document in documents:

            _additional = document["_additional"]

            documents_obj.append(
                {
                    "class": "No Class",
                    "uuid": _additional.get("id", "none"),
                    "chunks": document.get("chunk_count", 0),
                    "link": document.get("doc_link", ""),
                    "name": document.get("doc_name", "No name"),
                    "type": document.get("doc_type", "No type"),
                    "text": document.get("text", "No text"),
                    "timestamp": document.get("timestamp", ""),
                }
            )

        elapsed_time = round(time.time() - start_time, 2)  # Calculate elapsed time
        msg.good(
            f"Succesfully retrieved document: {len(documents)} documents in {elapsed_time}s"
        )

        doc_types = manager.retrieve_all_document_types()

        return JSONResponse(
            content={
                "documents": documents_obj,
                "doc_types": list(doc_types),
                "current_embedder": manager.embedder_manager.selected_embedder,
                "error": "",
                "took": elapsed_time,
            }
        )
    except Exception as e:
        msg.fail(f"All Document retrieval failed: {str(e)}")
        return JSONResponse(
            content={
                "documents": [],
                "doc_types": [],
                "current_embedder": manager.embedder_manager.selected_embedder,
                "error": f"All Document retrieval failed: {str(e)}",
                "took": 0,
            }
        )

# Delete specific document based on UUID
@app.post("/api/delete_document")
async def delete_document(payload: GetDocumentPayload):
    if production:
        msg.warn("Can't delete documents when in Production Mode")
        return JSONResponse(status_code=200, content={})

    msg.info(f"Document ID received: {payload.document_id}")

    manager.delete_document_by_id(payload.document_id)
    return JSONResponse(content={})

#for bitspprojs
async def make_request(query_user):
    # Escape the query to handle special characters and newlines
    formatted_query = json.dumps(query_user)
    
    # Create a payload with the formatted query
    payload = QueryPayload(query=formatted_query)

    # Retrieve chunks and context
    chunks, context = manager.retrieve_chunks([payload.query])
    
    return context



async def grading_assistant(question_answer_pair, context):
    user_context = "".join(context)
    rubric_content = f"""Please act as an impartial judge and evaluate the quality of the provided answer which attempts to answer the provided question based on a provided context.
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

    response = await asyncio.to_thread(ollama_chat, model='llama3.1', messages=payload['messages'], stream=payload['stream'])
    
    # Define a dictionary to store extracted scores
    scores_dict = {}

    # Extract the response content
    response_content = response['message']['content']

    # Define the criteria
    criteria = ["Correctness", "Readability", "Comprehensiveness"]

    # List to store individual scores
    scores = []

    for criterion in criteria:
        # Use regular expression to search for the criterion followed by 'Score:'
        criterion_pattern = re.compile(rf'{criterion}:\s*\**\s*Score\s*(\d+)', re.IGNORECASE)
        match = criterion_pattern.search(response_content)
        if match:
            # Extract the score value
            score_value = int(match.group(1).strip())
            scores.append(score_value)

    # Calculate the average score if we have scores
    avg_score = sum(scores) / len(scores) if scores else 0
    print(response['message']['content'])
    return response['message']['content'], avg_score


async def instructor_eval(instructor_name, context, score_criterion, explanation):
    # Ensure score_criterion is hashable by converting it to a string if necessary
    score_criterion = str(score_criterion)

    # Define the criterion to evaluate
    user_context = "".join(context)

    # Initialize empty dictionaries to store relevant responses and scores
    responses = {}
    scores_dict = {}

    # Evaluation prompt template
    evaluate_instructions = f"""
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
            -Consider the context surrounding the example statements, as the context in which a statement is made is extremely important.

            Rate strictly on a scale of 1 to 5 using whole numbers only.

            Ensure the examples are directly relevant to the evaluation criterion and discard any irrelevant excerpts.
    """

    output_format = f"""Strictly follow the output format-
        -Output Format:
            -{score_criterion}: Score(range of 1 to 5, or N/A) - note: Do not use bold or italics or any formatting in this line.

            -Detailed Explanation with Examples and justification for examples:
                -Example 1: "[Quoted text from transcript]" [Description] [Timestamp]
                -Example 2: "[Quoted text from transcript]" [Description] [Timestamp]
                -Example 3: "[Quoted text from transcript]" [Description] [Timestamp]
                -...
                -Example n: "[Quoted text from transcript]" [Description] [Timestamp]
            -Include both positive and negative instances.
            -Highlight poor examples if the score is not ideal."""
    
    system_message = """You are a judge. The judge gives helpful, detailed, and polite suggestions for improvement for a particular teacher from the given context - the context contains transcripts of videos. The judge should also indicate when the judgment can be found in the context."""
    
    formatted_transcripts = f"""Here are the transcripts for {instructor_name}-   
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
                "content": formatted_transcripts + "/n/n" + evaluate_instructions + "/n/n" + user_prompt + "/n/n" + output_format
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

    # Asynchronous call to the LLM API
    response = await asyncio.to_thread(ollama.chat, model='llama3.1', messages=payload['messages'], stream=payload['stream'])

    # Store the response
    content = response['message']['content']

    # Extract the score from the response content
    pattern = rf'(?i)(score:\s*(\d+)|\**{re.escape(score_criterion)}\**\s*[:\-]?\s*(\d+))'
    match = re.search(pattern, content, re.IGNORECASE)

    if match:
        # Check which group matched and extract the score
        score_value = match.group(2).strip() if match.group(2) else match.group(3).strip()
        scores_dict[score_criterion] = score_value
    else:
        scores_dict[score_criterion] = "N/A"

    # Return only the relevant content without any metadata
    return {"content": content}, scores_dict


# Function to generate answer using the Ollama API
async def answer_gen(question, context):
    user_context = "".join(context)
    # One shot example given in answer_inst should be the original question + original answer.
    answer_inst = f"""
        ### Context:
        Ensure that each generated answer is relevant to the following context:

        **[CONTEXT START]**
        {context}
        **[CONTEXT END]**

        ## Answer Instructions

        You are a highly knowledgeable and detailed assistant. Please follow these guidelines when generating answers:

        ### 1. Format
        Ensure the answer is nicely formatted and visually appealing. Use:
        - Bullet points
        - Numbered lists
        - Headings
        - Subheadings where appropriate

        ### 2. Clarity
        Provide clear and concise explanations. Avoid jargon unless it is necessary, and explain it when used.

        ### 3. Math Questions
        - Include all steps in the solution process.
        - Use a clear and logical progression from one step to the next.
        - Explain each step briefly to ensure understanding.
        - Use LaTeX formatting for mathematical expressions to ensure they are easy to read and understand.

        ### 4. Non-Math Questions
        - Provide detailed explanations and context.
        - Break down complex ideas into simpler parts.
        - Use examples where appropriate to illustrate points.
        - Ensure the answer is comprehensive and addresses all parts of the question.

        ### 5. Tone
        Maintain a professional and friendly tone. Aim to be helpful and approachable.

        ### Example
        Here are a couple of examples to illustrate the format:
        ONE-SHOT-EXAMPLE-GOES-HERE"""
    
    user_prompt = f"""Please answer the following question - {question}"""

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
            "top_k": 20,
            "top_p": 0.5,
            "temperature": 0.5,
            "seed": 100
        }
    }

    # Call ollama_chat function in a separate thread
    response = await asyncio.to_thread(ollama.chat, model='llama3.1', messages=payload['messages'], stream=payload['stream'])
    answer = response['message']['content']   

    return answer

# Define the endpoint
@app.post("/api/answergen")
async def answergen_ollama(request: QueryRequest):
    query = request.query
    context = await make_request(query)
    if context is None:
        raise HTTPException(status_code=500, detail="Failed to fetch context")
    
    answer = await answer_gen(query, context)
    response = {
        "answer": answer
    }
    return response


async def generate_question_variants(base_question, n, context):
    # Join the context into a single string
    user_context = "".join(context)

    base_question_gen = f"""
        **Task: Design a Variety of Mathematical and Conceptual Problem Scenarios**

        ### Background:
        You are tasked with creating a set of unique problem scenarios based on the following context:

        **[CONTEXT START]**  
        {context}  
        **[CONTEXT END]**

        Your objective is to generate distinct variations of a core problem by creatively altering its numerical, conceptual, and contextual elements. Each scenario should challenge students to apply diverse problem-solving strategies and think critically about the concepts involved.

        ### Creation Guidelines:

        1. **Diversify Numerical Elements**: Transform the numerical aspects of the problem, such as changing quantities, constants, or measurements. These alterations should introduce new dimensions to the problem, encouraging varied computational approaches.

        2. **Reinvent Problem Conditions**: Adjust or replace conditions within the problem, such as shifting the relationships between variables, altering assumptions, or imposing new constraints. These modifications should lead to different methods of solution and analysis.

        3. **Introduce Novel Variables**: Add, remove, or substitute variables to change the nature of the problem. For example, altering the number of components in a sequence or changing the type of equation can lead to entirely different problem-solving paths.

        4. **Change the Setting or Application**: Place the problem in a new context or application, such as using different real-world scenarios or shifting the problem’s focus to another field (e.g., from physics to economics). This approach helps students see the problem from various perspectives and understand its broader relevance.

        5. **Redesign the Problem Statement**: Reword the problem to emphasize different theoretical aspects, such as shifting focus from procedure to concept or from application to theory. This encourages students to explore different dimensions of the same problem.

        6. **Combine or Fragment Concepts**: Either merge multiple concepts into a single complex problem or break down a problem into simpler, interrelated parts. This approach encourages deeper understanding and the ability to connect disparate ideas.

        7. **Engage with Current Developments**: Integrate contemporary trends or recent discoveries related to the problem’s context, making the scenario more engaging and relevant for students.

        ### Multi-Part Problem Design:

        1. **Consistency Across Parts**: Ensure that if the original problem is multi-part, the variations retain the same structure. Each part of the variant should correspond to the original, with appropriate changes to ensure uniqueness.

        2. **Layered Challenges**: Within each multi-part variant, introduce different layers of complexity by altering the relationships between parts. Ensure that each part adds depth to the overall problem.

        3. **Encourage Exploration**: Design each part to explore different aspects of the problem, pushing students to use a variety of techniques and perspectives to arrive at solutions.

        ### Problem Complexity:

        1. **Standalone Scenarios**: Ensure each problem is self-contained, providing enough information and complexity to stand on its own without reference to other problems.

        2. **Promote Analytical Thinking**: Create problems that require deep thought and analysis, moving beyond simple calculations to engage students in understanding and application.

        3. **Diverse Problem-Solving Approaches**: Design scenarios that encourage students to explore multiple methods of solving the problem, fostering creativity and flexibility in thinking.

        ### Essential Considerations:
        - **Complete Transformation**: Each scenario must differ significantly in numbers, conditions, and theoretical focus to provide a wide range of challenges.
        - **Independent Design**: Each problem variant should be independent, not relying on others for context or information.
        - **Variety and Depth**: Ensure a broad spectrum of challenges to stimulate critical thinking and in-depth analysis.
        - **Structural Integrity**: In multi-part problems, maintain the original structure while ensuring each variant part is thoughtfully designed and distinct.
        - **DO NOT INCLUDE ANSWERS OR SOLUTIONS**
                                
        ### Example 1: Single-Part Question with 3 Variants

        **Original Question:**
        *Question:* A sample of gas occupies 4 liters at a pressure of 2 atm and a temperature of 300 K. Calculate the number of moles of gas in the sample using the ideal gas law.
        
        Response-

        Spanda
        **Variant 1**:  
        a. A sample of gas occupies 6 liters at a pressure of 1.5 atm and a temperature of 310 K. Calculate the number of moles of gas in the sample using the ideal gas law.
        
        Spanda
        **Variant 2**:  
        a. A sample of gas occupies 3 liters at a pressure of 2.5 atm and a temperature of 280 K. Calculate the number of moles of gas in the sample using the ideal gas law.
        
        Spanda
        **Variant 3**:  
        a. A sample of gas occupies 5 liters at a pressure of 1 atm and a temperature of 350 K. Calculate the number of moles of gas in the sample using the ideal gas law.

        ### Example 2: Multi-Part Question with 2 Variants

        **Original Question:**
        *Question:*  
        a. Find the roots of the quadratic equation \(x^2 - 4x + 3 = 0\).  
        b. Determine the coordinates of the vertex of the parabola described by the equation \(y = x^2 - 4x + 3\).  
        c. Calculate the axis of symmetry for the parabola.
        
        Response -
        
        Spanda
        **Variant 1**:  
        a. Find the roots of the quadratic equation \(x^2 - 6x + 8 = 0\).  
        b. Determine the coordinates of the vertex of the parabola described by the equation \(y = x^2 - 6x + 8\).  
        c. Calculate the axis of symmetry for the parabola.

        Spanda
        **Variant 2**:  
        a. Find the roots of the quadratic equation \(2x^2 - 8x + 6 = 0\).  
        b. Determine the coordinates of the vertex of the parabola described by the equation \(y = 2x^2 - 8x + 6\).  
        c. Calculate the axis of symmetry for the parabola.

        Utilize these guidelines to generate distinct and engaging questions based on the given context.
    """


    # Define the payload for Ollama
    payload = {
        "messages": [
            {
                "role": "system",
                "content": f"""{base_question_gen}"""
            },
            {
                "role": "user",
                "content": f"""Please generate {n} variants of the question: '{base_question}'.

                In multi-part problems, maintain the original structure while ensuring each variant part is thoughtfully designed and distinct. Type 'Spanda' before the beggining of every variant. Make sure to add 'Spanda' before every variant, its important.
                """,
            }
        ],
        "stream": False,
        "options": {
            "top_k": 20, 
            "top_p": 0.7, 
            "temperature": 0.7, 
            # "seed": 100, 
        }
    }
    # print("Original question" + base_question)
    # Asynchronous call to Ollama API
    response = await asyncio.to_thread(ollama.chat, model='llama3.1', messages=payload['messages'], stream=payload['stream'])
    content = response['message']['content']
    # print("Response-" + content)
    variants_dict = extract_variants(base_question, content)
    # Return the response content
    return response['message']['content'], variants_dict


def extract_variants(base_question, content):
    # Regex pattern to capture everything after "Spanda" and before the next "Spanda" or the end of the content
    variant_pattern = re.compile(r'(Spanda.*?)(?=Spanda|\Z)', re.DOTALL)
    
    # Find all variants
    variants = variant_pattern.findall(content)
    
    variant_contents = []
    
    for variant in variants:
        variant_contents.append(variant.strip())  # Store the content in the list and remove leading/trailing whitespace
    
    return {base_question: variant_contents}

@app.post("/api/assignments")
async def get_the_assignments(request: CourseIDRequest):
    try:
        course_id, course_name = get_course_info_by_shortname(request.course_shortname)
        
        assignments = get_assignments(course_id)
        return JSONResponse(content={
            "course_name": course_name,
            "course_id": course_id,
            "assignments": assignments
        })
    except HTTPException as e:
        return JSONResponse(content={"error": e.detail}, status_code=e.status_code)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)



def get_all_courses():
    params = {
        'wstoken': TOKEN,
        'wsfunction': 'core_course_get_courses',
        'moodlewsrestformat': 'json'
    }
    return moodle_api_call(params) 

# Function to get enrolled users in a specific course
def get_enrolled_users(course_id):
    params = {
        'wstoken': TOKEN,
        'wsfunction': 'core_enrol_get_enrolled_users',
        'moodlewsrestformat': 'json',
        'courseid': course_id
    }
    return moodle_api_call(params)

# Function to check admin capabilities
def check_admin_capabilities():
    params = {
        'wstoken': TOKEN,
        'wsfunction': 'core_webservice_get_site_info',
        'moodlewsrestformat': 'json',
    }
    site_info = moodle_api_call(params)
    print("Site Info:", site_info)


def get_course_info_by_shortname(course_shortname):
    params = {
        'wstoken': TOKEN,
        'wsfunction': 'core_course_get_courses_by_field',
        'moodlewsrestformat': 'json',
        'field': 'shortname',
        'value': course_shortname
    }
    result = moodle_api_call(params)
    if result['courses']:
        course = result['courses'][0]
        return course['id'], course['fullname']
    else:
        raise Exception("Course not found")
    
# Function to get assignments for a specific course
def get_assignments(course_id):
    params = {
        'wstoken': TOKEN,
        'wsfunction': 'mod_assign_get_assignments',
        'moodlewsrestformat': 'json',
        'courseids[0]': course_id
    }
    
    extra_params = {'includenotenrolledcourses': 1}
    assignments = moodle_api_call(params, extra_params)
    
    if not assignments.get('courses'):
        print("No courses found.")
        return []

    courses = assignments['courses']
    if not courses:
        print("No courses returned from API.")
        return []

    course_data = courses[0]

    if 'assignments' not in course_data:
        print(f"No assignments found for course: {course_data.get('fullname')}")
        return []

    return course_data['assignments']

# Function to get submissions for a specific assignment
def get_assignment_submissions(assignment_id):
    params = {
        'wstoken': TOKEN,
        'wsfunction': 'mod_assign_get_submissions',
        'moodlewsrestformat': 'json',
        'assignmentids[0]': assignment_id
    }
    submissions = moodle_api_call(params)

    if not submissions.get('assignments'):
        return []

    assignments_data = submissions.get('assignments', [])
    if not assignments_data:
        print("No assignments data returned from API.")
        return []

    assignment_data = assignments_data[0]

    if 'submissions' not in assignment_data:
        print(f"No submissions found for assignment: {assignment_id}")
        return []

    return assignment_data['submissions']

# Function to download a file from a given URL
def download_file(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.content
    else:
        raise Exception(f"Failed to download file: {response.status_code}, URL: {url}")

# Function to extract text from a PDF file
def extract_text_from_pdf(file_content):
    try:
        doc = fitz.open(stream=file_content, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        return f"Error extracting text from PDF: {str(e)}"

# Function to extract text from a DOCX file
def extract_text_from_docx(file_content):
    with io.BytesIO(file_content) as f:
        doc = Document(f)
        return "\n".join([para.text for para in doc.paragraphs])

# Function to extract text from a TXT file
def extract_text_from_txt(file_content):
    return file_content.decode('utf-8')

# Function to extract text from an image file
def extract_text_from_image(file_content):
    image = Image.open(io.BytesIO(file_content))
    return pytesseract.image_to_string(image)

# Function to extract text from a submission file based on file type
def extract_text_from_submission(file):
    file_url = file['fileurl']
    file_url_with_token = f"{file_url}&token={TOKEN}" if '?' in file_url else f"{file_url}?token={TOKEN}"
    print(f"Downloading file from URL: {file_url_with_token}")  # Log the file URL
    
    file_content = download_file(file_url_with_token)
    file_name = file['filename'].lower()
    print(f"Processing file: {file_name}")  # Log the file name

    try:
        if file_name.endswith('.pdf'):
            return extract_text_from_pdf(file_content)
        elif file_name.endswith('.docx'):
            return extract_text_from_docx(file_content)
        elif file_name.endswith('.txt'):
            return extract_text_from_txt(file_content)
        elif file_name.endswith(('.png', '.jpg', '.jpeg')):
            return extract_text_from_image(file_content)
        else:
            return "Unsupported file format."
    except Exception as e:
        return f"Error extracting text: {str(e)}"

# Function to extract Q&A pairs using regex
def extract_qa_pairs(text):
    qa_pairs = re.findall(r'(Q\d+:\s.*?\nA\d+:\s.*?(?=\nQ\d+:|\Z))', text, re.DOTALL)
    if not qa_pairs:
        return [text.strip()]
    return [pair.strip() for pair in qa_pairs]


# Function to send Q&A pair to grading endpoint and get response
async def process_user_submissions(user, submissions_by_user, activity_type):
    user_id = user['id']
    user_fullname = user['fullname']
    user_email = user['email']
    user_submission = submissions_by_user.get(user_id)
    
    if not user_submission:
        return {
            "Full Name": user_fullname,
            "User ID": user_id,
            "Email": user_email,
            "Total Score": 0,
            "Feedback": "No submission"
        }
    
    total_score = 0
    all_comments = []

    if activity_type == 'assignment':
        for plugin in user_submission['plugins']:
            if plugin['type'] == 'file':
                for filearea in plugin['fileareas']:
                    for file in filearea['files']:
                        try:
                            print(f"\nProcessing file: {file['filename']} for {user_fullname}...")
                            text = extract_text_from_submission(file)
                            qa_pairs = extract_qa_pairs(text)
                            print("QAPAIRS", qa_pairs)
                            for i, qa_pair in enumerate(qa_pairs):
                                try:
                                    # Convert the dictionary to QueryRequest instance
                                    query_request = QueryRequest(query=qa_pair)
                                    
                                    # Call the OllamaGA function directly
                                    result = await ollama_aga(query_request)
                                    justification = result.get("justification")
                                    avg_score = result.get("average_score")
                                    total_score += avg_score
                                    comment = f"Q{i+1}: {justification}"
                                    all_comments.append(comment)

                                    print(f"  Graded Q{i+1}: Avg. Score = {avg_score:.2f} - {justification}")
                                    
                                except Exception as e:
                                    print(f"  Error grading Q&A pair {i+1} for {user_fullname}: {str(e)}")
                        except Exception as e:
                            print(f"  Error extracting text for {user_fullname}: {str(e)}")

    feedback = " | ".join(all_comments)
    return {
        "Full Name": user_fullname,
        "User ID": user_id,
        "Email": user_email,
        "Total Score": total_score,
        "Feedback": feedback
    }

# Function to get course details by ID
def get_course_by_id(course_id):
    params = {
        'wstoken': TOKEN,
        'wsfunction': 'core_course_get_courses',
        'moodlewsrestformat': 'json',
        'options[ids][0]': course_id
    }
    return moodle_api_call(params)

# Function to write data to a CSV file in Moodle-compatible format
def write_to_csv(data, course_id, assignment_name):
    filename = f"Course_{course_id}_{assignment_name.replace(' ', '_')}_autograded.csv"
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        print("FILENAME",filename)
        writer.writerow(["Full Name", "User ID", "Email", "Total Score", "Feedback"])
        print("DATA",data,course_id,assignment_name)
        for row in data:
            writer.writerow([row["Full Name"], row["User ID"], row["Email"], row["Total Score"], row["Feedback"]])

async def process_user_submissions2(user, submissions_by_user, activity_type, token):
    user_id = user['id']
    user_fullname = user['fullname']
    user_email = user['email']
    user_submission = submissions_by_user.get(user_id)
    
    if not user_submission:
        return {
            "Full Name": user_fullname,
            "User ID": user_id,
            "Email": user_email,
            "Total Score": 0,
            "Feedback": "No submission"
        }
    
    total_score = 0
    all_comments = []

    if activity_type == 'assignment':
        for plugin in user_submission['plugins']:
            if plugin['type'] == 'file':
                for filearea in plugin['fileareas']:
                    for file in filearea['files']:
                        try:
                            print(f"\nProcessing file: {file['filename']} for {user_fullname}...")
                            text = extract_text_from_submission(file)
                            qa_pairs = extract_qa_pairs(text)
                            print("QAPAIRS", qa_pairs)
                            for i, qa_pair in enumerate(qa_pairs):
                                try:
                                    # Ensure qa_pair is a string
                                    query_request = QueryRequest(query=qa_pair)  # Remove the list brackets
                                    result = await ollama_aga2(query_request, token)
                                    justification = result.get("justification")
                                    avg_score = result.get("average_score")
                                    total_score += avg_score
                                    comment = f"Q{i+1}: {justification}"
                                    all_comments.append(comment)

                                    print(f"  Graded Q{i+1}: Avg. Score = {avg_score:.2f} - {justification}")
                                except Exception as e:
                                    print(f"  Error grading Q&A pair {i+1} for {user['fullname']}: {str(e)}")
                        except Exception as e:
                            print(f"  Error extracting text for {user_fullname}: {str(e)}")
        feedback = " | ".join(all_comments)
    return {
        "Full Name": user_fullname,
        "User ID": user_id,
        "Email": user_email,
        "Total Score": total_score,
        "Feedback": feedback
    }


# Function to update a user's grade in Moodle
def update_grade(user_id, assignment_id, grade, feedback):
    params = {
        'wstoken': TOKEN,
        'wsfunction': 'mod_assign_save_grade',
        'moodlewsrestformat': 'json',
        'assignmentid': assignment_id,
        'userid': user_id,
        'grade': grade, 
        'feedback': feedback
    }
    response = moodle_api_call(params)
    print(f"Grade updated for User ID: {user_id}, Status: {response}")

# Main function to integrate with Moodle
async def moodle_integration_pipeline(course_shortname, assignment_name, activity_type):
    try:

        print(f"\n=== Fetching Course Details for Shortname: {course_shortname} ===")
        course_id, course_name = get_course_info_by_shortname(course_shortname)
        print(f"Course ID: {course_id}, Course Name: {course_name}")
        # Fetching course details
        print(f"\n=== Fetching Course Details for Course ID: {course_id} ===")
        course_details = get_course_by_id(course_id)
        if not course_details:
            raise Exception("Course not found.")
        course_name = course_details[0]['fullname']
        print(f"Course Name: {course_name}")

        # Fetching enrolled users
        print("\n=== Fetching Enrolled Users ===")
        users = get_enrolled_users(course_id)
        print(f"Found {len(users)} enrolled users.")

        if activity_type == 'assignment':
            # Fetching assignments
            print("\n=== Fetching Assignments ===")
            activities = get_assignments(course_id)
        else:
            raise Exception("Unsupported activity type.")

        print(f"Found {len(activities)} {activity_type}s.")

        # Matching the activity by name
        activity = next((a for a in activities if a['name'].strip().lower() == assignment_name.strip().lower()), None)
        if not activity:
            raise Exception(f"{activity_type.capitalize()} not found.")

        activity_id = activity['id']
        print(f"{activity_type.capitalize()} '{assignment_name}' found with ID: {activity_id}")

        # Fetching submissions for the assignment
        print("\n=== Fetching Submissions ===")
        submissions = get_assignment_submissions(activity_id)

        print(f"Found {len(submissions)} submissions.")

        submissions_by_user = {s['userid']: s for s in submissions}

        # Processing submissions
        print("\n=== Processing Submissions ===")
        tasks = [process_user_submissions(user, submissions_by_user, activity_type) for user in users]
        processed_data = await asyncio.gather(*tasks)

        # Writing data to CSV
        print("\n=== Writing Data to CSV ===")
        write_to_csv(processed_data, course_id, assignment_name)

        print("\n=== Processing Completed Successfully ===")
        return processed_data

    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")
        raise

# Main function to integrate with Moodle
async def moodle_integration_pipeline2(course_shortname: str, assignment_name: str, activity_type: str, token: str):
    try:
        print(f"\n=== Fetching Course Details for Shortname: {course_shortname} ===")
        course_id, course_name = get_course_info_by_shortname(course_shortname)
        print(f"Course ID: {course_id}, Course Name: {course_name}")

        # Fetching course details
        print(f"\n=== Fetching Course Details for Course ID: {course_id} ===")
        course_details = get_course_by_id(course_id)
        if not course_details:
            raise Exception("Course not found.")
        course_name = course_details[0]['fullname']
        print(f"Course Name: {course_name}")

        # Fetching enrolled users
        print("\n=== Fetching Enrolled Users ===")
        users = get_enrolled_users(course_id)
        print(f"Found {len(users)} enrolled users.")

        if activity_type == 'assignment':
            # Fetching assignments
            print("\n=== Fetching Assignments ===")
            activities = get_assignments(course_id)
        else:
            raise Exception("Unsupported activity type.")

        print(f"Found {len(activities)} {activity_type}s.")

        # Matching the activity by name
        activity = next((a for a in activities if a['name'].strip().lower() == assignment_name.strip().lower()), None)
        if not activity:
            raise Exception(f"{activity_type.capitalize()} not found.")

        activity_id = activity['id']
        print(f"{activity_type.capitalize()} '{assignment_name}' found with ID: {activity_id}")

        # Fetching submissions for the assignment
        print("\n=== Fetching Submissions ===")
        submissions = get_assignment_submissions(activity_id)

        print(f"Found {len(submissions)} submissions.")

        submissions_by_user = {s['userid']: s for s in submissions}

        # Processing submissions
        print("\n=== Processing Submissions ===")
        tasks = [process_user_submissions2(user, submissions_by_user, activity_type, token) for user in users]
        processed_data = await asyncio.gather(*tasks)
        print("PROCESSED DATA",processed_data)
        # Writing data to CSV
        print("\n=== Writing Data to CSV ===")
        write_to_csv(processed_data, course_id, assignment_name)

        print("\n=== Processing Completed Successfully ===")
        return processed_data

    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")
        raise
# Main function to integrate with Moodle


@app.post("/api/process")
async def grade_assignment(request: RequestAGA):
    
    course_shortname = request.course_shortname
    assignment_name = request.assignment_name
    activity_type = "assignment"

    try:
        processed_data = await moodle_integration_pipeline(course_shortname, assignment_name, activity_type)
        return JSONResponse(content={"status": "success", "message": "Grading completed successfully", "data": processed_data})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/process2")
async def grade_assignment(request: RequestAGA, token: str = Depends(oauth2_scheme)):
    # Extract data from request
    # data = await request.json()
    course_shortname = request.course_shortname
    assignment_name = request.assignment_name
    activity_type = "assignment"

    try:
        # Call moodle_integration_pipeline with token
        processed_data = await moodle_integration_pipeline2(course_shortname, assignment_name, activity_type, token)
        return JSONResponse(content={"status": "success", "message": "Grading completed successfully", "data": processed_data})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)


    
@app.post("/api/ollamaAGA")
async def ollama_aga(request: QueryRequest):
    context = await make_request(request.query)
    if context is None:
        raise Exception("Failed to fetch context")
    
    variants, avg_score = await grading_assistant(request.query, context)
    
    response = {
        "justification": variants,
        "average_score": avg_score
    }
    
    return response

@app.post("/api/ollamaAGA2")
async def ollama_aga2(request: QueryRequest, current_user: TokenData = Depends(get_current_user)):
    context = await make_request(request.query)
    if context is None:
        raise HTTPException(status_code=500, detail="Failed to fetch context")
    
    variants, avg_score = await grading_assistant(request.query, context)
    return {"justification": variants, "average_score": avg_score}

@app.post("/api/ollamaAQG")
async def ollama_aqg(request: QueryRequestaqg):
    query = request.query
    n = request.NumberOfVariants
    context = await make_request(query)
    variants, variants_dict = await generate_question_variants(query, n, context)
    response = {
        "variants": variants,
        "variants_dict": variants_dict
    }
    return response



@app.post("/api/ollamaAQG2")
async def ollama_aqg(request: QueryRequestaqg, current_user: TokenData = Depends(get_current_user)):
   
    # Token has already been validated by get_current_user, so you can proceed
    context = await make_request(request.query)
    
    if context is None:
        raise HTTPException(status_code=500, detail="Failed to fetch context")
    
    variants, variants_dict = await generate_question_variants(request.query, request.NumberOfVariants, context)
    
    return {"variants": variants, "variants_dict": variants_dict}


@app.post("/api/spandachat")
async def spanda_chat(request: QueryRequest):
    context = await make_request(request.query)
    if context is None:
        raise Exception("Failed to fetch context")
    
    answer = await chatbot(request.query, context)
    
    response = {
        "answer": answer
    }
    
    return response

@app.post("/api/ollamaAFE")
async def ollama_afe(request: QueryRequest):
    dimensions = dimensions_AFE
    instructor_name = request.query
    dimension_scores = {}
    all_responses = {}

    for dimension, dimension_data in dimensions.items():
        sub_dimensions = dimension_data["sub-dimensions"]
        total_sub_weight = sum([sub_data["weight"] for sub_data in sub_dimensions.values()])
        weighted_sub_scores = 0
        
        all_responses[dimension] = {}

        for sub_dim_name, sub_dim_data in sub_dimensions.items():
            query = f"""
            Evaluate the {sub_dim_name.lower()} of the instructor "{instructor_name}" based on the following criteria:
            Definition: {sub_dim_data['definition']}
            Example: {sub_dim_data['example']}
            Criteria:
            {json.dumps(sub_dim_data['criteria'], indent=4)}
            Provide a score between 1 and 5 based on the criteria.
            """

            # Assuming make_request returns the context required for evaluation
            context = await make_request(instructor_name)
            response, score_dict = await instructor_eval(instructor_name, context, sub_dim_name, sub_dim_data["criteria"])

            # Store the response and score
            all_responses[dimension][sub_dim_name] = f"{sub_dim_name}: {score_dict.get(sub_dim_name, 'N/A')} - Detailed Explanation with Examples and justification for examples.\n\n{response}"
            score_str = score_dict.get(sub_dim_name, "0")
            score = int(score_str) if score_str.isdigit() else 0
            normalized_score = (score / 5) * sub_dim_data["weight"]
            weighted_sub_scores += normalized_score

        # Calculate the weighted average for this dimension
        dimension_score = (weighted_sub_scores / total_sub_weight) * dimension_data["weight"]
        dimension_scores[dimension] = dimension_score

    return {
        "dimension_scores": dimension_scores,
        "DOCUMENT": all_responses
    }

# Modified import endpoint to handle transcript uploads
@app.post("/api/importTranscript")
async def import_transcript(transcript_data: UploadFile = File(...)):
    try:
        contents = await transcript_data.file.read()

        # Convert to Base64
        base64_content = base64.b64encode(contents).decode('utf-8')

        # Upload to Weaviate using the existing endpoint
        upload_to_weaviate(base64_content, transcript_data.filename)

        return JSONResponse(content={"message": "Transcript uploaded successfully"})
    except ValidationError as e:
        # Handle validation errors
        return JSONResponse(content={"error": e.errors()}, status_code=422)
    except HTTPException as e:
        raise e  # Reraise the exception if it's a Weaviate import failure
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post("/api/upload_transcript")
async def upload_transcript(payload: ImportPayload):
    try:
        for file_data in payload.data:
            file_content = base64.b64decode(file_data.content)
            with open(file_data.filename, "wb") as file:
                file.write(file_content)
        
        logging = []

        print(f"Received payload: {payload}")
        if production:
            logging.append(
                {"type": "ERROR", "message": "Can't import when in production mode"}
            )
            return JSONResponse(
                content={
                    "logging": logging,
                }
            )

        try:
            set_config(manager, payload.config)
            documents, logging = manager.import_data(
                payload.data, payload.textValues, logging
            )

            return JSONResponse(
                content={
                    "logging": logging,
                }
            )

        except Exception as e:
            logging.append({"type": "ERROR", "message": str(e)})
            return JSONResponse(
                content={
                    "logging": logging,
                }
            )


    except Exception as e:
        print(f"Error during import: {e}")
        raise HTTPException(status_code=500, detail="Error processing the file")
    
@app.post("/api/evaluate_Transcipt")
async def evaluate_Transcipt(request: QueryRequest):
    dimensions = {
        "Communication Clarity": "The ability to convey information and instructions clearly and effectively so that students can easily understand the material being taught.\n"
                                "0: Instructions are often vague or confusing, leading to frequent misunderstandings among students.\n"
                                "Example: 'Read the text and do the thing.'\n"
                                "1: Occasionally provides clear instructions but often lacks detail, requiring students to ask for further clarification.\n"
                                "Example: 'Read the chapter and summarize it.'\n"
                                "2: Generally clear and detailed in communication, though sometimes slightly ambiguous.\n"
                                "Example: 'Read chapter 3 and summarize the main points in 200 words.'\n"
                                "3: Always communicates instructions and information clearly, precisely, and comprehensively, ensuring students fully understand what is expected.\n"
                                "Example: 'Read chapter 3, identify the main points, and write a 200-word summary. Make sure to include at least three key arguments presented by the author.'",

        "Punctuality": "Consistently starting and ending classes on time, as well as meeting deadlines for assignments and other class-related activities.\n"
                    "0: Frequently starts and ends classes late, often misses deadlines for assignments and class-related activities.\n"
                    "Example: Class is supposed to start at 9:00 AM but often begins at 9:15 AM, and assignments are returned late.\n"
                    "1: Occasionally late to start or end classes and sometimes misses deadlines.\n"
                    "Example: Class sometimes starts a few minutes late, and assignments are occasionally returned a day late.\n"
                    "2: Generally punctual with minor exceptions, mostly meets deadlines.\n"
                    "Example: Class starts on time 90%' of the time, and assignments are returned on the due date.\n"
                    "3: Always starts and ends classes on time, consistently meets deadlines for assignments and other activities.\n"
                    "Example: Class starts exactly at 9:00 AM every day, and assignments are always returned on the specified due date.",

        "Positivity": "Maintaining a positive attitude, providing encouragement, and fostering a supportive and optimistic learning environment.\n"
                    "0: Rarely displays a positive attitude, often appears disengaged or discouraging.\n"
                    "Example: Rarely smiles or offers encouragement, responds negatively to student questions.\n"
                    "1: Occasionally positive, but can be inconsistent in attitude and support.\n"
                    "Example: Sometimes offers praise but often seems indifferent.\n"
                    "2: Generally maintains a positive attitude and provides encouragement, though with occasional lapses.\n"
                    "Example: Usually offers praise and support but has off days.\n"
                    "3: Consistently maintains a positive and encouraging attitude, always fostering a supportive and optimistic environment.\n"
                    "Example: Always greets students warmly, frequently provides positive feedback and encouragement.",

    }


    instructor_name = request.query
    all_responses = {}
    all_scores = {}

    for dimension, explanation in dimensions.items():
        query = f"Judge document name {instructor_name} based on {dimension}."
        context = await make_request(query)  # Assuming make_request is defined elsewhere
        result_responses, result_scores = await instructor_eval(instructor_name, context, dimension, explanation)

        # Log the raw outputs for debugging
        print(f"Dimension: {dimension}")
        print(f"Raw Result Responses: {result_responses}")
        print(f"Raw Result Scores: {result_scores}")

        # Safely access and store the responses and scores
        all_responses[dimension] = result_responses.get('content', "No response available")
        all_scores[dimension] = result_scores.get(dimension, "No score available")

    print("Final Responses:", all_responses)
    print("Final Scores:", all_scores)
    
    response = {
        "DOCUMENT": all_responses,
        "SCORES": all_scores
    }

    return response

async def resume_eval(resume_name, jd_name, context, score_criterion, explanation):
    user_context = "".join(context)
    responses = {}
    scores_dict = {}

    evaluate_instructions = f"""
        [INST]
        -Instructions:
            You are tasked with evaluating a resume named {resume_name} in comparison to a job description named {jd_name} based on the criterion: {score_criterion} - {explanation}.

        -Evaluation Details:
            -Focus exclusively on the provided resume and job description.
            -Assign scores from 0 to 3:
                0: Poor performance
                1: Average performance
                2: Good performance
                3: Exceptional performance
        -Criteria:
            -Criterion Explanation: {explanation}
            -If the resume and job description lack sufficient information to judge {score_criterion}, mark it as N/A and provide a clear explanation.
            -Justify any score that is not a perfect 3.

        Strictly follow the output format-
        -Output Format:
            -{score_criterion}: Score: score(range of 0 to 3, or N/A)

            -Detailed Explanation with Examples and justification for examples:
                -Example 1: "[Quoted text from resume/job description]" [Description]
                -Example 2: "[Quoted text from resume/job description]" [Description]
                -Example 3: "[Quoted text from resume/job description]" [Description]
                -...
                -Example n: "[Quoted text from resume/job description]" [Description]
            -Include both positive and negative instances.
            -Highlight poor examples if the score is not ideal.

            -Consider the context surrounding the example statements, as the context in which a statement is made is extremely important.

            Rate strictly on a scale of 0 to 3 using whole numbers only.

            Ensure the examples are directly relevant to the evaluation criterion and discard any irrelevant excerpts.
        [/INST]
    """
    system_message = """This is a chat between a user and a judge. The judge gives helpful, detailed, and polite suggestions for improvement for a candidate's resume based on the given context - the context contains resumes and job descriptions. The assistant should also indicate when the judgement be found in the context."""

    formatted_context = f"""Here are given documents:
                    [RESUME START]
                    {user_context}
                    [RESUME END]
                    [JOB DESCRIPTION START]
                    {user_context}
                    [JOB DESCRIPTION END]"""

    user_prompt = f"""Please provide an evaluation of the resume named '{resume_name}' in comparison to the job description named '{jd_name}' on the following criteria: '{score_criterion}'. Only include information from the provided documents."""

    payload = {
        "messages": [
            {
                "role": "system",
                "content": system_message
            },
            {
                "role": "user",
                "content": formatted_context + "/n/n" + evaluate_instructions + "/n/n" + user_prompt + " Strictly follow the format of output provided."
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

    response = await asyncio.to_thread(ollama.chat, model='llama3.1', messages=payload['messages'], stream=payload['stream'])
    responses[score_criterion] = response
    content = response['message']['content']

    pattern = rf'(score:\s*([\s\S]*?)(\d+)|\**{score_criterion}\**\s*:\s*(\d+))'
    match = re.search(pattern, content, re.IGNORECASE)

    if match:
        if match.group(3):
            score_value = match.group(3).strip()
        elif match.group(4):
            score_value = match.group(4).strip()
        else:
            score_value = "N/A"
        scores_dict[score_criterion] = score_value
    else:
        scores_dict[score_criterion] = "N/A"

    return responses, scores_dict


# Define the extract_score function
def extract_score(response_content):
    # Regular expression to find the score in the response
    score_match = re.search(r'Score:\s*(\d+|N/A)', response_content)
    if score_match:
        score = score_match.group(1)
        if score == 'N/A':
            return score
        return int(score)
    return None

async def resume_eval(resume_name, jd_name, context, score_criterion, explanation):
    user_context = "".join(context)
    responses = {}
    scores_dict = {}

    evaluate_instructions = f"""
        [INST]
        -Instructions:
            You are tasked with evaluating a candidate's resume in comparison to a job description based on the criterion: {score_criterion} - {explanation}.

        -Evaluation Details:
            -Focus exclusively on the provided resume and job description.
            -Assign scores from 0 to 3:
                0: Poor performance
                1: Average performance
                2: Good performance
                3: Exceptional performance
        -Criteria:
            -Criterion Explanation: {explanation}
            -If the resume lacks sufficient information to judge {score_criterion}, mark it as N/A and provide a clear explanation.
            -Justify any score that is not a perfect 3.

        Strictly follow the output format-
        -Output Format:
            -{score_criterion}: Score: score(range of 0 to 3, or N/A)

            -Detailed Explanation with Examples and justification for examples:
                -Example 1: "[Quoted text from resume or job description]" [Description]
                -Example 2: "[Quoted text from resume or job description]" [Description]
                -Example 3: "[Quoted text from resume or job description]" [Description]
                -...
                -Example n: "[Quoted text from resume or job description]" [Description]
            -Include both positive and negative instances.
            -Highlight poor examples if the score is not ideal.

            -Consider the context surrounding the example statements, as the context in which a statement is made is extremely important.

            Rate strictly on a scale of 0 to 3 using whole numbers only.

            Ensure the examples are directly relevant to the evaluation criterion and discard any irrelevant excerpts.
        [/INST]
    """
    system_message = """This is a chat between a user and a judge. The judge gives helpful, detailed, and polite suggestions for improvement for a particular candidate from the given context - the context contains resumes and job descriptions. The assistant should also indicate when the judgment is found in the context."""
    
    formatted_documents = f"""Here are the given documents for {resume_name} and {jd_name}:
                    [RESUME START]
                    {user_context}
                    [RESUME END]
                    [JOB DESCRIPTION START]
                    {user_context}
                    [JOB DESCRIPTION END]"""
    
    user_prompt = f"""Please provide an evaluation of the candidate named '{resume_name}' in comparison to the job description named '{jd_name}' on the following criteria: '{score_criterion}'. Only include information from the resume and job description where '{resume_name}' is the candidate."""

    payload = {
        "messages": [
            {
                "role": "system",
                "content": system_message
            },
            {
                "role": "user",
                "content": formatted_documents + "\n\n" + evaluate_instructions + "\n\n" + user_prompt
            }
        ],
        "stream": False  # Assuming that streaming is set to False, adjust based on your implementation
    }

    eval_response = await asyncio.to_thread(ollama.chat, model='llama3.1', messages=payload['messages'])  # Assuming chat function is defined to handle the completion request

    # Log the eval_response to see its structure
    print("eval_response:", eval_response)
    
    try:
        eval_response_content = eval_response['message']['content']
    except KeyError as e:
        raise KeyError(f"Expected key 'message' not found in response: {eval_response}")

    response = {
        score_criterion: {
            "message": {
                "content": eval_response_content
            }
        }
    }
    score = extract_score(eval_response_content)
    scores_dict[score_criterion] = score

    return response, scores_dict

@app.post("/api/evaluate_Resume")
async def evaluate_Resume(request: QueryRequest):
    if len(request.query) != 2:
        raise HTTPException(status_code=400, detail="Invalid request format. Expected two items in query list.")
    
    resume_name, jd_name = request.query
    dimensions = {
        "Qualification Match": "The extent to which the candidate's educational background, certifications, and experience align with the specific requirements outlined in the job description.\n"
            "0: Qualifications are largely unrelated to the position.\n"
            "Example: The job requires a Master's degree in Computer Science, but the candidate has a Bachelor's in History.\n"
            "1: Some relevant qualifications but significant gaps exist.\n"
            "Example: The candidate has a Bachelor's in Computer Science but lacks the required 3 years of industry experience.\n"
            "2: Mostly meets the qualifications with minor gaps.\n"
            "Example: The candidate meets most qualifications but lacks experience with a specific programming language mentioned in the job description.\n"
            "3: Exceeds qualifications, demonstrating additional relevant skills or experience.\n"
            "Example: The candidate exceeds the required experience and has additional certifications in relevant areas.",
        "Experience Relevance": "The degree to which the candidate's prior teaching, research, or industry experience is relevant to the courses they would be teaching.\n"
            "0: Little to no relevant experience in the subject matter.\n"
            "Example: The candidate has no prior experience teaching or working with the programming languages listed in the course syllabus.\n"
            "1: Some relevant experience but mostly in unrelated areas.\n"
            "Example: The candidate has experience in web development but the course focuses on mobile app development.\n"
            "2: Solid experience in related fields but limited direct experience in the specific subject.\n"
            "Example: The candidate has taught general computer science courses but not the specific advanced algorithms course they are applying for.\n"
            "3: Extensive experience directly teaching or working in the subject area.\n"
            "Example: The candidate has 5+ years of experience teaching the specific course they are applying for and has published research in the field.",
        "Skillset Alignment": "How well the candidate's demonstrated skills (e.g., technical skills, communication, leadership) match the required competencies for the role.\n"
            "0: Skills are largely misaligned with the job requirements.\n"
            "Example: The job requires strong communication and presentation skills, but the candidate has no experience presenting or leading workshops.\n"
            "1: Possesses some required skills but lacks others.\n"
            "Example: The candidate has strong technical skills but lacks experience with collaborative project management tools.\n"
            "2: Demonstrates most of the required skills with some room for improvement.\n"
            "Example: The candidate has good communication skills but could benefit from additional training in public speaking.\n"
            "3: Possesses all required skills and demonstrates advanced abilities in some areas.\n"
            "Example: The candidate has excellent technical skills, is a highly effective communicator, and has a proven track record of mentoring junior developers.",
        "Potential Impact": "An assessment of the candidate's potential to contribute positively to the department and the institution as a whole, based on their resume and cover letter.\n"
            "0: Unclear or negative potential impact based on application materials.\n"
            "Example: The candidate's application materials are vague and do not highlight any specific contributions they could make.\n"
            "1: Potential for minimal impact or contribution.\n"
            "Example: The candidate's resume shows basic qualifications but no indication of going above and beyond.\n"
            "2: Demonstrates potential for moderate positive impact.\n"
            "Example: The candidate has experience with relevant projects and expresses enthusiasm for contributing to the department's research initiatives.\n"
            "3: Shows strong potential to significantly impact the department and institution through teaching, research, or other activities.\n"
            "Example: The candidate has a strong publication record, outstanding references, and a clear vision for how they would enhance the curriculum.",
        "Overall Fit": "A holistic assessment of how well the candidate aligns with the department's culture, values, and long-term goals.\n"
            "0: Poor overall fit with the department.\n"
            "Example: The candidate's values and goals conflict with the department's focus on collaborative learning.\n"
            "1: Some alignment but significant differences in values or goals.\n"
            "Example: The candidate is passionate about research but the department prioritizes teaching excellence.\n"
            "2: Good fit with some areas of potential misalignment.\n"
            "Example: The candidate aligns well with most of the department's values but has a different teaching style than is typical for the institution.\n"
            "3: Excellent fit with the department's culture, values, and goals.\n"
            "Example: The candidate's teaching philosophy, research interests, and collaborative spirit perfectly complement the department's existing strengths and future aspirations."
    }

    all_responses = {}
    all_scores = {}

    for dimension, explanation in dimensions.items():
        query = f"Judge Resume named {resume_name} in comparison to Job Description named {jd_name} based on {dimension}."
        context = await make_request(query)  # Assuming make_request is defined elsewhere to get the context
        result_responses, result_scores = await resume_eval(resume_name, jd_name, context, dimension, explanation)
        all_responses[dimension] = result_responses[dimension]['message']['content']
        all_scores[dimension] = result_scores[dimension]
    
    response = {
        "DOCUMENT": all_responses,
        "SCORES": all_scores
    }
    
    return response