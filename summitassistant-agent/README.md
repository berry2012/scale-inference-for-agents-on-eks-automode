# SummitAssistant Agent

AI-powered meeting management agent for the AWS London Summit 2026 demo "From Models to Agents: Running LLM-Powered AI Applications on Amazon EKS Auto Mode".

## Overview

SummitAssistant is an AI agent built using the Strands Agents framework that orchestrates meeting-related tasks including:

- **Calendar Management**: Schedule meetings through Google Calendar via MCP server integration
- **AI Summarization**: Generate meeting summaries using AWS Bedrock (Claude Sonnet 4)
- **Persistent Storage**: Store meeting notes and session state in Amazon S3
- **Stateful Conversations**: Maintain context across agent restarts

## Architecture

The agent integrates with:
- **AWS Bedrock**: Claude Sonnet 4 for agent orchestration and meeting summarization
- **MCP Server**: Model Context Protocol server for Google Calendar API
- **Amazon S3**: Persistent storage for meeting data and session state

## Prerequisites

### For Local Development
- Python 3.11 or higher
- Docker and Docker Compose
- AWS CLI (optional, for S3 access)

### For EKS Deployment
- Amazon EKS cluster with Auto Mode enabled
- AWS Bedrock access with Claude Sonnet 4 model enabled
- S3 bucket created
- IAM roles configured for service accounts (IRSA) with permissions for:
  - Bedrock InvokeModel
  - S3 read/write access

## Setup Instructions

### Local Development with Docker Compose

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd summitassistant-agent
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start services with Docker Compose**
   ```bash
   docker-compose up -d
   ```

   This will start:
   - **SummitAssistant**: Main agent application (port 8080)
   - **s3**: LocalStack for S3-compatible storage (port 4566)
   - **mcp-server**: Mock MCP server for Google Calendar integration (port 8081)

   Note: For local development, you'll need AWS credentials configured for Bedrock access.
   All services include health checks and will wait for dependencies to be ready.

4. **Initialize mock data**
   ```bash
   docker-compose exec SummitAssistant python scripts/initialize_mock_data.py
   ```

5. **Access the agent**
   ```bash
   # The agent will be available at http://localhost:8080
   curl http://localhost:8080/health
   ```

6. **View logs**
   ```bash
   # View all service logs
   docker-compose logs -f
   
   # View specific service logs
   docker-compose logs -f SummitAssistant
   ```

7. **Stop services**
   ```bash
   docker-compose down
   
   # Stop and remove volumes
   docker-compose down -v
   ```

### Python Virtual Environment Setup

For development without Docker:

1. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -e ".[dev]"
   # Or using requirements.txt:
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your local configuration
   ```

4. **Run tests**
   ```bash
   pytest
   ```

### EKS Deployment

1. **Build and push Docker image**
   ```bash
   docker build -t <your-registry>/SummitAssistant:latest .
   docker push <your-registry>/SummitAssistant:latest
   ```

2. **Configure Kubernetes resources**
   ```bash
   # Update k8s/deployment.yaml with your image and configuration
   kubectl apply -f k8s/
   ```

3. **Verify deployment**
   ```bash
   kubectl get pods -l app=SummitAssistant
   kubectl logs -l app=SummitAssistant
   ```

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `BEDROCK_MODEL` | AWS Bedrock model ID | `us.anthropic.claude-sonnet-4-20250514-v1:0` | Yes |
| `AWS_REGION` | AWS region for Bedrock | `us-east-1` | Yes |
| `LLM_MAX_TOKENS` | Max tokens for summary | `500` | No |
| `S3_BUCKET_NAME` | S3 bucket for storage | `SummitAssistant-demo-bucket` | Yes |
| `S3_REGION` | AWS region for S3 | `us-east-2` | Yes |
| `S3_ENDPOINT_URL` | S3 endpoint (local dev) | `http://localhost:4566` | No |
| `MCP_SERVER_URL` | MCP server endpoint | `http://mcp-server:8080` | Yes |
| `MAX_RETRIES` | Max retry attempts | `3` | No |
| `SESSION_TIMEOUT` | Session timeout (seconds) | `3600` | No |

## Project Structure

```
summitassistant-agent/
├── src/
│   └── SummitAssistant/
│       ├── __init__.py
│       ├── agent.py              # Main agent implementation
│       ├── models.py             # Data models
│       ├── calendar_manager.py   # MCP server integration
│       ├── summarization_manager.py  # LLM service integration
│       ├── storage_manager.py    # S3 operations
│       ├── state_manager.py      # Session state management
│       └── retry_manager.py      # Retry logic
├── tests/
│   ├── unit/                     # Unit tests
│   └── property/                 # Property-based tests
├── scripts/
│   └── initialize_mock_data.py   # Mock data initialization
├── k8s/                          # Kubernetes manifests
├── docker-compose.yml            # Local development setup
├── Dockerfile                    # Container image
├── pyproject.toml               # Python project configuration
├── requirements.txt             # Dependencies for Docker
├── .env.example                 # Example environment variables
└── README.md                    # This file
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit/

# Run property-based tests
pytest tests/property/

# Run with coverage
pytest --cov=src/SummitAssistant --cov-report=html
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint code
ruff check src/ tests/

# Type checking
mypy src/
```

### Hot Reload

When using Docker Compose, code changes are automatically reflected:
```bash
# The src/ directory is mounted as a volume
# Changes to Python files will trigger automatic reload
```

### Docker Compose Services

The `docker-compose.yml` configuration includes:

**SummitAssistant**:
- Built from local Dockerfile
- Mounts `./src/SummitAssistant` and `./tests` for hot-reload
- Depends on vllm, s3, and mcp-server services
- Configured with all required environment variables

**vllm**:
- Uses `vllm/vllm-openai:latest` image
- Runs mistralai/Mistral-7B-Instruct-v0.3 model
- Health check on `/health` endpoint
- Model cache persisted in named volume
- For GPU support, uncomment the deploy section in docker-compose.yml

**s3 (LocalStack)**:
- Provides S3-compatible storage for local development
- Data persisted in named volume
- Health check on LocalStack health endpoint

**mcp-server**:
- Mock implementation using FastAPI
- Returns simulated Google Calendar responses
- Useful for development without real Google Calendar API access

## Usage Examples

### Schedule a Meeting

```python
from SummitAssistant import SummitAssistant

agent = SummitAssistant()

result = await agent.schedule_meeting(
    date="2026-02-01",
    time="14:00",
    duration_minutes=60,
    attendees=["alice@example.com", "bob@example.com"],
    title="Sprint Planning"
)

print(f"Meeting scheduled: {result.data['meeting_id']}")
```

### Summarize Meeting Notes

```python
result = await agent.summarize_meeting(
    meeting_id="meeting-123",
    notes="Discussion about Q1 roadmap..."
)

print(f"Summary: {result.data['summary']}")
```

### Search Past Meetings

```python
results = await agent.search_meetings(
    attendee="alice@example.com",
    date_range=("2026-01-01", "2026-01-31")
)

for meeting in results.data:
    print(f"{meeting.title}: {meeting.timestamp}")
```

## Troubleshooting

### Common Issues

**Issue**: Agent cannot connect to AWS Bedrock
- **Solution**: Verify AWS credentials and IAM permissions for Bedrock
- **Check**: Ensure the IAM role has `bedrock:InvokeModel` permission
- **Check**: Verify the model ID is correct and available in your region

**Issue**: S3 operations fail with permission errors
- **Solution**: Verify AWS credentials or IRSA configuration
- **Check**: `aws s3 ls s3://SummitAssistant-demo-bucket/`

**Issue**: MCP server returns authentication errors
- **Solution**: Verify MCP server credentials and configuration
- **Check**: MCP server logs for authentication details

### Logs

```bash
# Docker Compose logs
docker-compose logs -f SummitAssistant

# Kubernetes logs
kubectl logs -l app=SummitAssistant -f

# View specific container logs
docker-compose logs -f vllm
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Demo Information

This project is part of the AWS London Summit 2026 demo "From Models to Agents: Running LLM-Powered AI Applications on Amazon EKS Auto Mode".

For demo-specific instructions and presentation materials, see the `demo/` directory.
