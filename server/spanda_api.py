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
from spanda_utils import answer_gen, grading_assistant, instructor_eval, generate_question_variants, extract_variants, make_request, dimensions

import os
from pathlib import Path

from dotenv import load_dotenv
from starlette.websockets import WebSocketDisconnect
from wasabi import msg  # type: ignore[import]
import time
from goldenverba.server.bitsp import(
    ollama_afe,
    ollama_aga,
    ollama_aqg
)
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

app = FastAPI()

manager = verba_manager.VerbaManager()
setup_managers(manager)

production_key = os.environ.get("VERBA_PRODUCTION", "")
# Define the origins that should be allowed to make cross-origin requests.
origins = [
    "http://localhost:3000",
    "https://verba-golden-ragtriever.onrender.com",
    "http://localhost:8000",
    "http://localhost:1511",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Spanda.API!"}

if production_key == "True":
    msg.info("API runs in Production Mode")
    production = True
else:
    production = False

# All 3 projects - AGA, AQG and AFE
# This endpoint is responsible for importing data and performing several operations, including loading, filtering, chunking, and embedding documents. 
@app.post("/api/spandaimport")
async def import_data(payload: ImportPayload):

    logging = []

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
    
# Automated grading assistant 
@app.post("/api/ollamaAGA")
async def ollama_aga(request: QueryRequest):
    query = request.query
    context = await make_request(query)
    if context is None:
        raise HTTPException(status_code=500, detail="Failed to fetch context")
    variants, scores = await grading_assistant(query, context)
    print(scores)
    response = {
        "justification": variants,
        "scores": scores
    }
    return response

# Variants of a question paper
@app.post("/api/ollamaAQG")
async def ollama_aqg(request: QueryRequest):
    query = request.query
    context = await make_request(query)
    variants, variants_dict = await generate_question_variants(query, context)
    response = {
        "variants": variants,
        "variants_dict": variants_dict
    }
    return {"variants": variants}


@app.post("/api/ollamaAFE")
async def ollama_afe(request: QueryRequest):
    instructor_name = request.query

    all_responses = {}
    all_scores = {}

    for dimension, explanation in dimensions.items():
        query = f"Judge {instructor_name} based on {dimension}."
        context = await make_request(query)  # Assuming make_request is defined elsewhere to get the context
        # print(f"CONTEXT for {dimension}:")
        # print(context)  # Print the context generated
        result_responses, result_scores = await instructor_eval(instructor_name, context, dimension, explanation)
        print(result_responses)
        print(result_scores)
        # Extract only the message['content'] part and store it
        all_responses[dimension] = result_responses[dimension]['message']['content']
        all_scores[dimension] = result_scores[dimension]
    
    print("SCORES:")
    print(json.dumps(all_scores, indent=2))
    response = {
        "DOCUMENT": all_responses,
        "SCORES": all_scores
    }
    
    return response

# Variants of a question paper - answergen
@app.post("/api/answergen")
async def ollama_aqg(request: QueryRequest):
    query = request.query
    context = await make_request(query)
    answer = await answer_gen(query, context)
    response = {
        "answer": answer,
    }
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
