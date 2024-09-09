# Spanda-Pipeline

## Overview

The **Spanda-Pipeline** repository is a refactored version of the original Spanda platform's backend, aligning with the new architecture for large language model (LLM) pipelines. This repository is designed to manage the ingestion, processing, and serving of requests using LLMs in a pipeline-based structure. The intent of this refactoring is to modularize the backend components and improve scalability, maintainability, and performance of the overall system. 

## Key Changes in Refactoring

1. **Modular Architecture**: The backend is now refactored into distinct pipeline stages. Each stage is responsible for a specific operation, such as ingestion, processing, embedding, and inference.
   
2. **Enhanced LLM Pipeline Support**: This refactoring includes optimizations to support LLM frameworks and a retrieval-augmented generation (RAG) framework using **Verba**.

3. **Weaviate Integration**: The system has been updated to leverage two embedded Weaviate instances for indexing and inference. These instances now operate independently to streamline data ingestion and model serving.

4. **Vector Database Integration**: Full integration of Weaviate for vector storage and retrieval, improving the system's ability to handle large-scale data indexing and similarity search.

5. **Docker Support**: Refactored Docker Compose setup to support the pipeline-based architecture. All services, including ingestion, vector storage, and inference, are containerized for easy deployment.

6. **Improved Scalability**: The system has been designed with scalability in mind, allowing for easier addition of new models and services without disruption.

## Folder Structure

- `/src/`: Contains the pipeline components.
  - `ingestion/`: Manages ingestion and pre-processing of data.
  - `processing/`: Handles data transformation and embedding.
  - `inference/`: Responsible for querying the model and retrieving results.

- `/config/`: Configuration files, including the integration setup for Weaviate instances and LLM models.

- `/docker/`: Docker and Docker Compose files for setting up the environment.

## Getting Started

To run the pipeline, ensure that you have Docker installed. You can use the provided `docker-compose.yml` file to set up the necessary containers.

1. Clone the repository:
   ```bash
   git clone https://github.com/dullbrowny/spanda-pipeline.git
   cd spanda-pipeline

