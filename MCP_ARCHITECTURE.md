# MCP Architecture for External APIs

This document describes the architecture for using Model Context Protocol (MCP) servers to access all external APIs in the SummitAssistant system.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      SummitAssistant Agent                        │
│                    (Strands Agent + Bedrock)                    │
└────────┬────────────────────────┬────────────────────┬──────────┘
         │                        │                    │
         │ HTTP                   │ HTTP               │ HTTP
         ▼                        ▼                    ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Calendar MCP   │    │   Weather MCP    │    │  Other MCP      │
│     Server      │    │     Server       │    │   Servers       │
└────────┬────────┘    └────────┬─────────┘    └────────┬────────┘
         │                      │                        │
         │ API                  │ API                    │ API
         ▼                      ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Google Calendar │    │   Open-Meteo     │    │  External APIs  │
│      API        │    │   Geolocation    │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Why MCP for All External APIs?

### Benefits

1. **Separation of Concerns**
   - Agent focuses on orchestration and reasoning
   - MCP servers handle API-specific logic
   - Clear boundaries between components

2. **Reusability**
   - MCP servers can be used by multiple agents
   - Standardized interface across different APIs
   - Easy to share and deploy independently

3. **Security**
   - Centralized credential management
   - API keys isolated in MCP servers
   - No credentials in agent code

4. **Scalability**
   - MCP servers can be scaled independently
   - Rate limiting per API
   - Caching at MCP layer

5. **Maintainability**
   - API changes isolated to MCP servers
   - Easier testing and debugging
   - Version control per API integration

6. **Observability**
   - Centralized logging per API
   - Metrics and monitoring per MCP server
   - Better error tracking

## Current Architecture

### ✅ Already Using MCP
- **Google Calendar** → Calendar MCP Server

### ❌ Direct API Access (Should Convert)
- **Open-Meteo API** → Weather Agent (direct)
- **Geolocation (Nominatim)** → Weather Agent (direct)

## Proposed Architecture

### Convert Weather Agent to Use Weather MCP Server

```
Weather Agent (Strands)
    ↓ HTTP
Weather MCP Server
    ↓ API
    ├─→ Open-Meteo API
    └─→ Nominatim Geolocation
```

## MCP Server Design Pattern

### Standard MCP Server Structure

```
mcp-server/
├── main.py                 # FastAPI application
├── requirements.txt        # Dependencies
├── Dockerfile             # Container image
├── k8s/
│   ├── deployment.yaml    # Kubernetes deployment
│   ├── service.yaml       # Kubernetes service
│   └── secret.yaml        # API credentials (if needed)
├── README.md              # Documentation
└── tests/                 # Unit tests
```

### Standard Endpoints

Every MCP server should implement:

1. **GET /health** - Health check
2. **GET /** - API information
3. **POST /[action]** - Action-specific endpoints

### Standard Response Format

```json
{
  "status": "success|error",
  "data": { ... },
  "error": "error message if status=error"
}
```

## Implementation Guide

### Step 1: Identify External APIs

Current external APIs in the system:
1. ✅ Google Calendar API (already MCP)
2. ❌ Open-Meteo Weather API
3. ❌ Nominatim Geolocation API
4. ✅ AWS Bedrock (managed service, no MCP needed)
5. ✅ AWS S3 (managed service, no MCP needed)

### Step 2: Create MCP Servers

For each external API, create a dedicated MCP server:

#### Weather MCP Server

**Purpose:** Provide weather and geolocation services

**Endpoints:**
- `POST /weather` - Get current weather for location
- `POST /geocode` - Get coordinates for location
- `POST /timezone` - Get timezone for location

**External APIs:**
- Open-Meteo API (weather data)
- Nominatim (geolocation)
- TimezoneFinder (timezone lookup)

#### Future MCP Servers (Examples)

**Email MCP Server:**
- SendGrid, AWS SES, Gmail API
- Endpoints: `/send`, `/read`, `/search`

**Database MCP Server:**
- PostgreSQL, MongoDB, DynamoDB
- Endpoints: `/query`, `/insert`, `/update`

**Notification MCP Server:**
- Slack, Teams, PagerDuty
- Endpoints: `/notify`, `/alert`

### Step 3: Update Agents to Use MCP

Agents should:
1. Define tools that call MCP servers via HTTP
2. Never access external APIs directly
3. Handle MCP server errors gracefully

### Step 4: Deploy MCP Servers

Each MCP server:
1. Runs as independent Kubernetes deployment
2. Has its own service (ClusterIP)
3. Manages its own credentials via secrets
4. Scales independently

## Security Best Practices

### 1. Credential Management

```yaml
# Store API keys in Kubernetes secrets
apiVersion: v1
kind: Secret
metadata:
  name: weather-mcp-credentials
type: Opaque
stringData:
  OPENMETEO_API_KEY: "your-key-here"
  NOMINATIM_USER_AGENT: "SummitAssistant-weather"
```

### 2. Network Policies

```yaml
# Restrict MCP server access
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: weather-mcp-policy
spec:
  podSelector:
    matchLabels:
      app: weather-mcp-server
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: weather-agent
```

### 3. Rate Limiting

Implement rate limiting in MCP servers:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/weather")
@limiter.limit("100/minute")
async def get_weather(request: WeatherRequest):
    # Implementation
    pass
```

### 4. API Key Rotation

```bash
# Rotate API keys regularly
kubectl create secret generic weather-mcp-credentials \
    --from-literal=OPENMETEO_API_KEY=new-key \
    --dry-run=client -o yaml | kubectl apply -f -

# Restart pods to pick up new credentials
kubectl rollout restart deployment/weather-mcp-server
```

## Monitoring and Observability

### Metrics to Track

Each MCP server should expose:

1. **Request metrics**
   - Total requests
   - Requests per endpoint
   - Response times
   - Error rates

2. **External API metrics**
   - API call count
   - API latency
   - API errors
   - Rate limit status

3. **Resource metrics**
   - CPU usage
   - Memory usage
   - Network I/O

### Logging Standards

```python
import logging
import json

logger = logging.getLogger(__name__)

# Structured logging
logger.info(json.dumps({
    "event": "api_call",
    "api": "open-meteo",
    "endpoint": "/forecast",
    "location": "Amsterdam",
    "duration_ms": 234,
    "status": "success"
}))
```

### Health Checks

```python
@app.get("/health")
async def health_check():
    """Comprehensive health check."""
    health = {
        "status": "healthy",
        "service": "weather-mcp-server",
        "version": "1.0.0",
        "checks": {}
    }
    
    # Check external API connectivity
    try:
        response = requests.get("https://api.open-meteo.com/v1/forecast?latitude=0&longitude=0", timeout=5)
        health["checks"]["open_meteo"] = "healthy" if response.status_code == 200 else "unhealthy"
    except:
        health["checks"]["open_meteo"] = "unhealthy"
        health["status"] = "degraded"
    
    return health
```

## Testing Strategy

### Unit Tests

Test MCP server logic in isolation:

```python
import pytest
from fastapi.testclient import TestClient

def test_weather_endpoint():
    client = TestClient(app)
    response = client.post("/weather", json={
        "location": "Amsterdam"
    })
    assert response.status_code == 200
    assert "temperature" in response.json()
```

### Integration Tests

Test with real external APIs:

```python
@pytest.mark.integration
def test_real_weather_api():
    response = get_weather("Amsterdam")
    assert response["status"] == "success"
    assert "temperature" in response["data"]
```

### End-to-End Tests

Test agent → MCP → external API flow:

```python
@pytest.mark.e2e
async def test_agent_weather_query():
    agent = WeatherAgent()
    response = await agent.chat("What's the weather in Amsterdam?")
    assert "temperature" in response.lower()
```

## Migration Checklist

- [ ] Create Weather MCP Server
  - [ ] Implement weather endpoint
  - [ ] Implement geocoding endpoint
  - [ ] Implement timezone endpoint
  - [ ] Add health checks
  - [ ] Add error handling
  - [ ] Add rate limiting
  - [ ] Add logging

- [ ] Update Weather Agent
  - [ ] Remove direct API calls
  - [ ] Add MCP client tools
  - [ ] Update error handling
  - [ ] Update tests

- [ ] Deploy Weather MCP Server
  - [ ] Build Docker image
  - [ ] Create Kubernetes manifests
  - [ ] Create secrets for credentials
  - [ ] Deploy to EKS
  - [ ] Verify health checks

- [ ] Test Integration
  - [ ] Unit tests
  - [ ] Integration tests
  - [ ] End-to-end tests
  - [ ] Load testing

- [ ] Documentation
  - [ ] Update architecture diagrams
  - [ ] Update README files
  - [ ] Create troubleshooting guide
  - [ ] Update deployment guide

## Future Enhancements

1. **MCP Server Registry**
   - Central registry of available MCP servers
   - Service discovery
   - Version management

2. **MCP Gateway**
   - Single entry point for all MCP servers
   - Request routing
   - Authentication/authorization
   - Rate limiting

3. **MCP SDK**
   - Standardized client library
   - Automatic retry logic
   - Circuit breaker pattern
   - Connection pooling

4. **MCP Monitoring Dashboard**
   - Real-time metrics
   - API health status
   - Cost tracking
   - Performance analytics

## References

- [Model Context Protocol Specification](https://modelcontextprotocol.io)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/configuration/overview/)
- [Microservices Patterns](https://microservices.io/patterns/index.html)
