# Weather MCP Server

Model Context Protocol (MCP) server for weather and geolocation services. Provides a standardized API for accessing Open-Meteo weather data and Nominatim geocoding.

## Features

- Weather information for any location
- Current time with timezone support
- Geocoding (location name to coordinates)
- Health checks with external API monitoring
- Structured logging
- Kubernetes-ready with health probes

## API Endpoints

### POST /weather

Get current weather for a location.

**Request:**
```json
{
  "location": "Amsterdam"
}
```

**Response:**
```json
{
  "status": "success",
  "location": "Amsterdam",
  "temperature": 12.5,
  "weather_description": "Partly cloudy",
  "weather_code": 2,
  "latitude": 52.3676,
  "longitude": 4.9041
}
```

### POST /time

Get current time for a location.

**Request:**
```json
{
  "location": "Tokyo"
}
```

**Response:**
```json
{
  "status": "success",
  "location": "Tokyo",
  "current_time": "2026-03-05 11:30 PM JST",
  "timezone": "Asia/Tokyo",
  "latitude": 35.6762,
  "longitude": 139.6503
}
```

### POST /geocode

Geocode a location to coordinates.

**Request:**
```json
{
  "location": "London"
}
```

**Response:**
```json
{
  "status": "success",
  "location": "London",
  "latitude": 51.5074,
  "longitude": -0.1278,
  "display_name": "London, Greater London, England, United Kingdom"
}
```

### GET /health

Health check endpoint with external API status.

**Response:**
```json
{
  "status": "healthy",
  "service": "weather-mcp-server",
  "version": "1.0.0",
  "checks": {
    "open_meteo": "healthy",
    "nominatim": "healthy"
  }
}
```

## Local Development

### Run with Python

```bash
cd weather-mcp-server
pip install -r requirements.txt
python main.py
```

The server will start on `http://localhost:8080`.

### Run with Docker

```bash
cd weather-mcp-server
docker build -t weather-mcp-server .
docker run -p 8080:8080 weather-mcp-server
```

### Test the API

```bash
# Health check
curl http://localhost:8080/health

# Get weather
curl -X POST http://localhost:8080/weather \
  -H "Content-Type: application/json" \
  -d '{"location": "Amsterdam"}'

# Get time
curl -X POST http://localhost:8080/time \
  -H "Content-Type: application/json" \
  -d '{"location": "Tokyo"}'

# Geocode
curl -X POST http://localhost:8080/geocode \
  -H "Content-Type: application/json" \
  -d '{"location": "London"}'
```

## Deployment to EKS

### 1. Build and Push Docker Image

```bash
# Set your ECR registry
export ECR_REGISTRY=<your-account-id>.dkr.ecr.<region>.amazonaws.com

# Build image
docker build -t weather-mcp-server .

# Tag for ECR
docker tag weather-mcp-server:latest $ECR_REGISTRY/weather-mcp-server:latest

# Login to ECR
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin $ECR_REGISTRY

# Push to ECR
docker push $ECR_REGISTRY/weather-mcp-server:latest
```

### 2. Update Kubernetes Manifests

Edit `k8s/deployment.yaml` and replace `<ECR_REGISTRY>` with your actual ECR registry URL.

### 3. Deploy to EKS

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

# Verify deployment
kubectl get pods -l app=weather-mcp-server
kubectl get svc weather-mcp-server

# Check logs
kubectl logs -l app=weather-mcp-server --tail=50
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Server port | `8080` |
| `HOST` | Server host | `0.0.0.0` |
| `NOMINATIM_USER_AGENT` | User agent for Nominatim API | `SummitAssistant-weather-mcp` |
| `REQUEST_TIMEOUT` | Timeout for external API requests (seconds) | `10` |

## Integration with Weather Agent

Update the Weather Agent to use this MCP server instead of direct API calls:

```python
from strands import tool
import httpx

WEATHER_MCP_URL = "http://weather-mcp-server:8080"

@tool
async def current_weather(location: str) -> str:
    """Get current weather via Weather MCP Server."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{WEATHER_MCP_URL}/weather",
            json={"location": location}
        )
        data = response.json()
        
        if data["status"] == "success":
            return f"{data['weather_description']}, {data['temperature']}°C"
        return data.get("error", "Weather unavailable")

@tool
async def current_time(location: str) -> str:
    """Get current time via Weather MCP Server."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{WEATHER_MCP_URL}/time",
            json={"location": location}
        )
        data = response.json()
        
        if data["status"] == "success":
            return data["current_time"]
        return data.get("error", "Time unavailable")
```

## External APIs Used

### Open-Meteo API
- **URL:** https://api.open-meteo.com
- **Purpose:** Weather data
- **Rate Limit:** 10,000 requests/day (free tier)
- **No API key required**

### Nominatim (OpenStreetMap)
- **URL:** https://nominatim.openstreetmap.org
- **Purpose:** Geocoding
- **Rate Limit:** 1 request/second
- **Usage Policy:** Must provide user agent

## Error Handling

The server returns structured error responses:

```json
{
  "status": "error",
  "location": "InvalidLocation",
  "error": "Location not found"
}
```

Common errors:
- `Location not found` - Geocoding failed
- `Weather data currently unavailable` - Open-Meteo API error
- `Weather service timeout` - Request timeout
- `Time service error` - Timezone lookup failed

## Monitoring

### Metrics to Track

- Request count per endpoint
- Response times
- Error rates
- External API latency
- External API availability

### Logs

Structured JSON logs with:
- Timestamp
- Log level
- Component name
- Message

Example:
```json
{
  "timestamp": "2026-03-05T18:00:00+00:00",
  "level": "INFO",
  "component": "weather-mcp-server",
  "message": "Weather request for location: Amsterdam"
}
```

## Testing

### Unit Tests

```bash
pytest tests/
```

### Integration Tests

```bash
# Test with real APIs
pytest tests/ -m integration
```

### Load Testing

```bash
# Using Apache Bench
ab -n 1000 -c 10 -p weather_request.json -T application/json http://localhost:8080/weather
```

## Troubleshooting

### Issue: "Location not found"

**Cause:** Nominatim couldn't geocode the location

**Solution:** 
- Try more specific location names
- Include country name
- Use coordinates directly if available

### Issue: "Weather data currently unavailable"

**Cause:** Open-Meteo API error or timeout

**Solution:**
- Check Open-Meteo API status
- Verify network connectivity
- Check logs for specific error

### Issue: Health check failing

**Cause:** External API connectivity issues

**Solution:**
```bash
# Check pod logs
kubectl logs -l app=weather-mcp-server

# Test external APIs manually
curl "https://api.open-meteo.com/v1/forecast?latitude=0&longitude=0&current=temperature_2m"
```

## Performance

- **Response Time:** Typically 200-500ms
- **Throughput:** ~100 requests/second
- **Memory:** ~100MB per pod
- **CPU:** Minimal (<0.1 core under normal load)

## Security

- No authentication required (internal service)
- Network policies recommended for production
- No sensitive data stored
- External API calls use HTTPS

## License

MIT

## References

- [Open-Meteo API Documentation](https://open-meteo.com/en/docs)
- [Nominatim Usage Policy](https://operations.osmfoundation.org/policies/nominatim/)
- [Model Context Protocol](https://modelcontextprotocol.io)
