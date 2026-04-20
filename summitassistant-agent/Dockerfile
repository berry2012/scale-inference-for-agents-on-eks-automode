# Use Python 3.11 slim base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project configuration
COPY pyproject.toml .

# Copy source code
COPY src/ ./src/

# Install the package in development mode
RUN pip install -e .

# Expose port 8080
EXPOSE 8080

# Set Python path
ENV PYTHONPATH=/app

# Run the agent
CMD ["summitassistant", "start"]
