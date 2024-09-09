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


Spanda Backend - Goldenverba
Overview
This directory contains the backend services and scripts that power the Spanda platform's core functionalities, including data collection, vector storage, model training, inference, and monitoring. The following describes the various components and their roles within the system.

Directory Structure
bash
Copy code
/goldenverba
├── data_collection
│   ├── etl.py                  # Script to handle ETL processes from Medium, Substack, etc.
│   ├── cdc.py                  # Script for change data capture (Debezium integration)
├── vector_db
│   ├── qdrant_client.py         # Script to interact with Qdrant for storing and retrieving vectors
├── training
│   ├── fine_tune_llm.py         # Script to fine-tune the LLM using Hugging Face
│   ├── prompt_layer.py          # Script to convert data into prompt format
├── inference
│   ├── inference_service.py     # FastAPI/Flask service to handle LLM inference requests
│   ├── query_to_prompt.py       # Script to handle converting user queries into prompts for LLM
├── monitoring
│   ├── prometheus_exporter.py   # Script to expose Prometheus metrics for monitoring
│   ├── grafana_dashboard.json   # Configuration for Grafana dashboards
├── utils
│   └── common_helpers.py        # Utility scripts for common functions
Key Components
Data Collection
etl.py: Manages extraction, transformation, and loading (ETL) of data from external sources like Medium and Substack to bring content into the pipeline.
cdc.py: Implements Change Data Capture (CDC) using Debezium for real-time updates from databases, ensuring the system stays in sync with external data changes.
Vector Database
qdrant_client.py: Interacts with the Qdrant vector database to store and retrieve vector representations of textual data for efficient similarity search and retrieval.
Model Training
fine_tune_llm.py: Fine-tunes a pre-trained large language model (LLM) using data tailored to the specific domain via Hugging Face transformers.
prompt_layer.py: Transforms raw data into prompt-ready format for effective use during training and inference, improving the overall quality of generated outputs.
Inference
inference_service.py: Provides a FastAPI or Flask-based service to handle real-time inference requests to the LLM. This service converts user inputs into prompts, submits them to the model, and returns the results.
query_to_prompt.py: Converts user queries into prompts compatible with the LLM, ensuring seamless communication between the front-end and back-end systems.
Monitoring
prometheus_exporter.py: Exposes various system metrics in a format compatible with Prometheus, allowing for real-time monitoring of system health and performance.
grafana_dashboard.json: Contains configuration for Grafana dashboards to visualize Prometheus metrics and track the performance and reliability of the platform.
Utilities
common_helpers.py: Includes common helper functions used across multiple scripts to avoid redundancy and improve maintainability.
Next Steps for the Pipeline
Integration: Complete the integration of data ingestion, vector storage, and inference components.
Testing: Perform load testing, end-to-end testing, and quality assurance (QA) processes to verify system reliability.
Monitoring: Set up and finalize monitoring with Prometheus and Grafana dashboards for performance tracking.
Deployment: Deploy the system in a staging environment for testing, followed by production deployment.
Contribution
For contributions, follow the standard branching model and submit your changes through pull requests. Ensure that each contribution is documented and includes relevant tests.

This structure provides an organized breakdown of the components and their respective roles in the refactoring process. Let me know if you'd like any additional refinements or details!


