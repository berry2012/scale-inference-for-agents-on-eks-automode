# Weather Agent

AI-powered weather and time information agent using AWS Bedrock (Claude Sonnet 4).

## Overview

Weather Agent is a specialized AI agent that provides:
- Current weather information for any location
- Current time for any location (with timezone support)
- Integration with SummitAssistant for agent-to-agent communication

## Features

- **Weather Information**: Real-time weather data from Open-Meteo API
- **Time Information**: Accurate time with timezone support using geopy and timezonefinder
- **AWS Bedrock**: Uses Claude Sonnet 4 for natural language understanding
- **FastAPI**: RESTful API for easy integration
- **Agent-to-Agent**: Can be called by other Strands agents

## Architecture

```
User Query → SummitAssistant → Weather Agent → Open-Meteo API
                                    ↓
                              AWS Bedrock
                            (Claude Sonnet 4)
```

## Prerequisites

- AWS account with Bedrock access
- Claude Sonnet 4 model enabled
- Kubernetes cluster (for deployment)
- IAM role with Bedrock permissions

## Quick Start

### Local Development

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure AWS credentials**:
   ```bash
   export AWS_ACCESS_KEY_ID=your-key
   export AWS_SECRET_ACCESS_KEY=your-secret
   export AWS_REGION=us-east-1
   ```

3. **Run the agent**:
   ```bash
   python -m uvicorn app:app --host 0.0.0.0 --port 8000
   ```

4. **Test the agent**:
   ```bash
   curl -X POST http://localhost:8000/agent \
     -H "Content-Type: application/json" \
     -d '{"query": "What is the weather in Amsterdam?"}'
   ```

### Docker

1. **Build image**:
   ```bash
   docker build -t weather-agent:latest .
   ```

2. **Run container**:
   ```bash
   docker run -p 8000:8000 \
     -e AWS_ACCESS_KEY_ID=your-key \
     -e AWS_SECRET_ACCESS_KEY=your-secret \
     -e AWS_REGION=us-east-1 \
     weather-agent:latest
   ```

### Kubernetes

1. **Build and push image**:
   ```bash
   docker build -t <registry>/weather-agent:latest .
   docker push <registry>/weather-agent:latest
   ```

2. **Deploy to cluster**:
   ```bash
   kubectl apply -f k8s/weather-agents.yaml
   ```

3. **Verify deployment**:
   ```bash
   kubectl get pods -l app=strands-weather-agent
   kubectl logs -l app=strands-weather-agent
   ```

## API Endpoints

### POST /agent

Query the weather agent with natural language.

**Request:**
```json
{
  "query": "What is the weather in Amsterdam?"
}
```

**Response:**
```json
{
  "status": "success",
  "response": "The weather in Amsterdam is Partly cloudy, 12°C"
}
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy"
}
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BEDROCK_MODEL` | AWS Bedrock model ID | `us.anthropic.claude-sonnet-4-20250514-v1:0` |
| `AWS_REGION` | AWS region for Bedrock | `us-east-1` |

## Tools Available

### 1. current_time

Get the current time for any location with timezone support.

**Example:**
```
Query: "What time is it in Tokyo?"
Response: "2024-03-15 11:30 PM JST"
```

### 2. current_weather

Get current weather information for any location.

**Example:**
```
Query: "What's the weather in London?"
Response: "Light rain, 8°C"
```

## Integration with SummitAssistant

Weather Agent can be called by SummitAssistant for weather-related queries:

```python
# In SummitAssistant
@tool(name="ask_weather_agent")
async def weather_agent_tool(query: str):
    response = await call_weather_agent(query)
    return response
```

See `AGENT_TO_AGENT_COMMUNICATION.md` for detailed integration guide.

## Weather Codes

The agent uses Open-Meteo weather codes:

| Code | Description |
|------|-------------|
| 0 | Clear sky |
| 1 | Mainly clear |
| 2 | Partly cloudy |
| 3 | Overcast |
| 45 | Fog |
| 51-55 | Drizzle (light to dense) |
| 61-65 | Rain (light to heavy) |
| 71-75 | Snow (light to heavy) |
| 95 | Thunderstorm |

## Error Handling

The agent handles various error scenarios:

- **Location not found**: Returns "Location not found"
- **Weather API unavailable**: Returns "Weather data currently unavailable"
- **Timeout**: Returns "Weather service is currently unavailable"
- **Network errors**: Graceful degradation with error messages

## Troubleshooting

### Issue: "AccessDeniedException" from Bedrock

**Solution**: Verify IAM permissions include `bedrock:InvokeModel`

```bash
# Check service account
kubectl describe pod -l app=strands-weather-agent | grep "service-account"
```

### Issue: Weather data unavailable

**Solution**: Check Open-Meteo API status and network connectivity

```bash
# Test API directly
curl "https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&current=temperature_2m"
```

### Issue: Location not found

**Solution**: Try different location formats (city name, city + country, coordinates)

## Development

### Project Structure

```
weather-agent/
├── summitassistant-agent.py    # Main application
├── requirements.txt    # Python dependencies
├── Dockerfile         # Container image
├── k8s/
│   └── weather-agents.yaml  # Kubernetes deployment
└── README.md          # This file
```

### Adding New Tools

To add a new tool to the Weather Agent:

```python
@tool
def new_tool(param: str) -> str:
    """Tool description."""
    # Implementation
    return result

# Add to agent
agent = Agent(
    model=BEDROCK_MODEL,
    tools=[current_time, current_weather, new_tool]
)
```

## Testing

### Manual Testing

```bash
# Weather query
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the weather in Paris?"}'

# Time query
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"query": "What time is it in New York?"}'

# Combined query
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"query": "Tell me the weather and time in Berlin"}'
```

### Health Check

```bash
curl http://localhost:8000/health
```

## Performance

- **Response Time**: Typically 1-3 seconds
- **Bedrock Latency**: ~500ms-1s
- **Open-Meteo API**: ~200-500ms
- **Geolocation**: ~100-300ms

## Cost Optimization

### Bedrock Usage
- ~1 API call per query
- Claude Sonnet 4: $0.003 per 1K input tokens
- Typical query: ~100-200 tokens

### Recommendations
- Cache weather responses (5-minute TTL)
- Use Nova Lite for simple queries
- Implement request batching

## Security

1. **IAM Permissions**: Use IRSA for Bedrock access
2. **Network Policies**: Restrict pod-to-pod communication
3. **Rate Limiting**: Prevent API abuse
4. **Input Validation**: Sanitize location queries

## Monitoring

### Logs

```bash
# View logs
kubectl logs -l app=strands-weather-agent --tail=50

# Follow logs
kubectl logs -l app=strands-weather-agent -f
```

### Metrics

Monitor:
- Request count
- Response time
- Error rate
- Bedrock API latency
- Open-Meteo API availability

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

MIT License

## Support

For issues and questions:
- Check logs: `kubectl logs -l app=strands-weather-agent`
- Review `AGENT_TO_AGENT_COMMUNICATION.md`
- Check AWS Bedrock documentation

## References

- Strands Agents: https://docs.strands.ai/
- AWS Bedrock: https://docs.aws.amazon.com/bedrock/
- Open-Meteo API: https://open-meteo.com/
- FastAPI: https://fastapi.tiangolo.com/
