# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the current directory contents into the container
COPY . /app

# Install any necessary dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run the inference server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
