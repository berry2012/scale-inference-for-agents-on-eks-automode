# Calendar MCP Server

A production-ready MCP (Model Context Protocol) server for Google Calendar integration, designed to be deployed on Amazon EKS.

## Features

- REST API for meeting scheduling
- FastAPI-based implementation
- Health check endpoints
- Kubernetes-ready with deployment manifests
- Docker containerized

## API Endpoints

### POST /schedule
Schedule a meeting in Google Calendar.

**Request Body**:
```json
{
  "date": "2026-03-15",
  "time": "14:00",
  "duration_minutes": 60,
  "attendees": ["alice@example.com", "bob@example.com"],
  "title": "Team Meeting",
  "description": "Optional description"
}
```

**Response**:
```json
{
  "meeting_id": "uuid-here",
  "status": "confirmed",
  "calendar_link": "https://calendar.google.com/event/uuid-here",
  "created_at": "2026-03-02T10:30:00Z"
}
```

### GET /health
Health check endpoint.

**Response**:
```json
{
  "status": "healthy",
  "service": "calendar-mcp-server",
  "version": "1.0.0"
}
```

## Local Development

### Run with Python

```bash
cd calendar-mcp-server
pip install -r requirements.txt
python main.py
```

The server will start on `http://localhost:8080`.

### Run with Docker

```bash
cd calendar-mcp-server
docker build -t calendar-mcp-server .
docker run -p 8080:8080 calendar-mcp-server
```

### Test the API

```bash
# Health check
curl http://localhost:8080/health

# Schedule a meeting
curl -X POST http://localhost:8080/schedule \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-03-15",
    "time": "14:00",
    "duration_minutes": 60,
    "attendees": ["alice@example.com"],
    "title": "Test Meeting"
  }'
```

## Deployment to EKS

### 1. Build and Push Docker Image

```bash
# Set your ECR registry
export ECR_REGISTRY=<your-account-id>.dkr.ecr.<region>.amazonaws.com

# Build image
docker build -t calendar-mcp-server .

# Tag for ECR
docker tag calendar-mcp-server:latest $ECR_REGISTRY/calendar-mcp-server:latest

# Login to ECR
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin $ECR_REGISTRY

# Push to ECR
docker push $ECR_REGISTRY/calendar-mcp-server:latest
```

### 2. Update Kubernetes Manifests

Edit `k8s/deployment.yaml` and replace `<ECR_REGISTRY>` with your actual ECR registry URL.

### 3. Deploy to EKS

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

# Verify deployment
kubectl get pods -l app=calendar-mcp-server
kubectl get svc calendar-mcp-server

# Check logs
kubectl logs -l app=calendar-mcp-server --tail=50
```

### 4. Update SummitAssistant Configuration

Update the SummitAssistant agent's ConfigMap to point to the calendar MCP server:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: SummitAssistant-config
data:
  MCP_SERVER_URL: "http://calendar-mcp-server:8080"
```

## Integration with SummitAssistant

The calendar MCP server is designed to work seamlessly with the SummitAssistant agent. The agent will call the `/schedule` endpoint to create calendar events.

## Production Considerations

### Google Calendar Integration

This is currently a mock implementation. For production use with real Google Calendar:

1. Set up Google Cloud Project and enable Calendar API
2. Create OAuth 2.0 credentials
3. Install Google Calendar API client: `pip install google-api-python-client google-auth`
4. Update `main.py` to use actual Google Calendar API calls
5. Add environment variables for credentials:
   - `GOOGLE_CALENDAR_CREDENTIALS_JSON`
   - `GOOGLE_CALENDAR_ID`

### Security

- Add authentication/authorization (API keys, OAuth)
- Use HTTPS/TLS for production
- Implement rate limiting
- Add request validation and sanitization

### Monitoring

- Add Prometheus metrics
- Configure CloudWatch logging
- Set up alerts for failures

### Scaling

- Adjust replica count based on load
- Configure horizontal pod autoscaling
- Use pod disruption budgets for high availability

## Environment Variables

- `PORT`: Server port (default: 8080)
- `HOST`: Server host (default: 0.0.0.0)

## License

MIT
