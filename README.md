# Scale Inference for Agentic Apps on Amazon EKS Auto Mode

This project is for demo purposes and not for production use. The solution, AI-Powered Meeting Management System, covers how to Scale Inference for Agentic Apps on Amazon EKS Auto Mode.

## Overview

This project demonstrates a production-ready AI agent system built with the [Strands Agents](https://strandsagents.com) framework, deployed on Amazon EKS Auto Mode. It showcases modern cloud-native AI application architecture using AWS Bedrock (Claude Sonnet 4) and vLLM (Ministral 3 8B Instruct 2512) for all AI operations, with agent-to-agent communication, Google Calendar integration via MCP servers, and persistent storage using Amazon S3.


The system includes three main components:

- **SummitAssistant Agent**: AI-powered meeting management with calendar integration, note summarization, intelligent retrieval, and weather queries via agent-to-agent communication
- **Weather Agent**: Time and weather information service with AWS Bedrock integration
- **Chat UI**: Web-based interface for interacting with the agents

## Architecture

![Architecture Diagram](./architecture.png)

### System Overview

The system uses **AWS Bedrock (Claude Sonnet 4)** for all AI operations, eliminating the need for self-hosted LLM infrastructure. Both agents communicate via HTTP APIs, demonstrating agent-to-agent collaboration patterns.

**Key Features:**

- ✅ **AWS Bedrock (Claude Sonnet 4) Integration**: : Agent orchestration, reasoning, tool selection
- ✅ **Agent-to-Agent Communication**: SummitAssistant can query Weather Agent
- ✅ **GPU Infrastructure - vLLM (Ministral 3 8B Instruct 2512)**: Meeting note summarization only
- ✅ **Cost-Effective**: 60-75% cost reduction vs self-hosted LLMs
- ✅ **Auto-Scaling**: AWS handles all scaling automatically

### SummitAssistant Agent

**Capabilities:**

- Schedule meetings via Google Calendar (MCP Server)
- Summarize meeting notes using AWS Bedrock
- Retrieve past meetings from S3 storage
- Get weather and time information (via Weather Agent)
- Maintain conversation context across sessions

**Tools Available:**

- `schedule_meeting` → Google Calendar API
- `summarize_meeting` → AWS Bedrock (Claude Sonnet 4)
- `retrieve_meetings` → Amazon S3
- `ask_weather_agent` → Weather Agent (HTTP)
- `current_time` → System time

### Weather Agent

**Capabilities:**

- Current time for any location (timezone-aware)
- Current weather for any location (Open-Meteo API)
- Serves SummitAssistant and direct API calls

**Tools Available:**

- `current_time` → Geolocation + Timezone
- `current_weather` → Open-Meteo API

### Communication Flow

```text
User: "What's the weather in Amsterdam?"
  ↓
SummitAssistant (Bedrock) → Determines to use ask_weather_agent
  ↓
Weather Agent (Bedrock) → Determines to use current_weather
  ↓
Open-Meteo API → Returns weather data
  ↓
Weather Agent → Formats response
  ↓
SummitAssistant → Presents to user
```

## Project Structure

```bash
.
├── summitassistant-agent/              # SummitAssistant agent
│   ├── src/SummitAssistant/
│   │   ├── agent.py           # Main agent orchestration
│   │   ├── llm_client.py      # Custom vLLM client
│   │   ├── storage_manager.py # S3 integration
│   │   ├── calendar_manager.py# MCP client
│   │   └── main.py            # Entry point
│   ├── k8s/                   # Kubernetes manifests
│   ├── Dockerfile
│   └── requirements.txt
│
├── weather-agent/             # Weather agent
│   ├── summitassistant-agent.py       # Agent implementation
│   ├── k8s/                   # Kubernetes manifests
│   ├── Dockerfile
│   └── requirements.txt
│
├── chat-ui/                   # Web interface
│   ├── index.html
│   ├── app.js
│   ├── styles.css
│   ├── nginx.conf
│   ├── k8s/
│   └── Dockerfile
│
├── calendar-mcp-server/       # MCP server for Google Calendar
│   ├── main.py
│   ├── k8s/
│   ├── Dockerfile
│   └── requirements.txt
│
└── scripts/
    ├── build-and-push-ecr.sh  # Multi-image build script
    ├── initialize_mock_data.py# Demo data generator
    └── setup_s3_bucket.sh     # S3 bucket setup
```

## Features

### SummitAssistant Agent

- **Meeting Scheduling**: Schedule meetings via Google Calendar using MCP server integration
- **AI-Powered Summarization**: Generate intelligent summaries using AWS Bedrock (Claude Sonnet 4)
- **Smart Retrieval**: Search and retrieve past meetings by date range, attendee, or meeting ID
- **Weather & Time Queries**: Get weather and time information via Weather Agent (agent-to-agent communication)
- **Session Persistence**: Maintain conversation context across restarts using S3
- **Date/Time Awareness**: Uses `current_time` tool for accurate date calculations
- **Health Monitoring**: Kubernetes-ready with liveness and readiness probes

### Weather Agent

- **Current Time**: Get current time for any location with timezone support
- **Weather Information**: Real-time weather data from Open-Meteo API
- **AWS Bedrock**: Uses Claude Sonnet 4 for natural language understanding
- **Agent-to-Agent**: Can be called by other agents via HTTP API

### Chat UI

- **Modern Interface**: Clean, responsive web UI
- **Markdown Support**: Renders formatted responses with headers, lists, and emphasis
- **Real-time Interaction**: Async communication with agents
- **Secure Architecture**: Internal ClusterIP services, only UI exposed via LoadBalancer

## Prerequisites

- AWS Account with appropriate permissions
- AWS CLI configured
- kubectl installed and configured
- Docker installed
- Amazon EKS cluster with Auto Mode enabled
- Mountpoint for Amazon S3 CSI Driver
- GPU nodes for vLLM (optional but recommended)

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/berry2012/scale-inference-for-agents-on-eks-automode.git
cd scale-inference-for-agents-on-eks-automode
```

### 2. Set Up Environment Variables

```bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
export CLUSTER_NAME="aiml"
```

### 3. Build and Push Images

```bash
cd scripts
./build-and-push-ecr.sh
```

This script will:
- Create ECR repositories if they don't exist
- Build Docker images for all components
- Push images to ECR
- Provide deployment instructions

### 4. Set Up S3 Bucket

```bash
./setup_s3_bucket.sh
```

### 5. Configure AWS Bedrock and Amazon S3 Access

Ensure your EKS cluster has IAM permissions for AWS Bedrock and S3:

```bash
eksctl create podidentityassociation \
  --cluster $CLUSTER_NAME \
  --namespace default \
  --service-account-name model-storage-sa \
  --role-name model-storage-sa-role \
  --permission-policy-arns arn:aws:iam::aws:policy/AmazonS3FullAccess,arn:aws:iam::aws:policy/AmazonBedrockFullAccess \
  --region $AWS_REGION

```

### 6. Deploy to EKS

```bash
# Deploy SummitAssistant
kubectl apply -f summitassistant-agent/k8s/

# Deploy Weather Agent
kubectl apply -f weather-agent/k8s/

# Deploy Calendar MCP Server
kubectl apply -f calendar-mcp-server/k8s/

# Deploy Chat UI
kubectl apply -f chat-ui/k8s/
```

### 7. Initialize Mock Data (Optional)

```bash
kubectl exec -it deployment/SummitAssistant -- python -m SummitAssistant.main init-mock-data
```

### 8. Access the Application

```bash
# Get the LoadBalancer URL
kubectl get svc SummitAssistant-chat-ui -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
```

Open the URL in your browser to interact with the agents.

## Configuration

### SummitAssistant Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BEDROCK_MODEL` | AWS Bedrock model ID | `us.anthropic.claude-sonnet-4-20250514-v1:0` |
| `AWS_REGION` | AWS region for Bedrock | `us-east-1` |
| `S3_BUCKET_NAME` | S3 bucket for storage | `SummitAssistant-demo-bucket` |
| `S3_REGION` | AWS region for S3 | `us-east-2` |
| `MCP_SERVER_URL` | Calendar MCP server URL | `http://calendar-mcp-server:8080` |
| `WEATHER_AGENT_URL` | Weather Agent URL | `http://strands-weather-agent/agent` |
| `LOG_LEVEL` | Logging level | `INFO` |

### Weather Agent Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BEDROCK_MODEL` | AWS Bedrock model ID | `us.anthropic.claude-sonnet-4-20250514-v1:0` |
| `AWS_REGION` | AWS region for Bedrock | `us-east-1` |

## Usage Examples

### SummitAssistant

**Schedule a Meeting:**
```
Schedule a meeting with john@example.com tomorrow at 2pm for 1 hour titled "Sprint Planning"
```

**Summarize Meeting Notes:**
```
Please summarize the following meeting notes:
- Discussed Q1 goals
- Decided to migrate to microservices
- Action items: Create architecture diagram by Friday
```

**Retrieve Past Meetings:**
```
Show me all meetings from the past week with john@AnyCompany.com
```

**Check Current Date:**
```
What is today's date?
```

**Get Weather (via Weather Agent):**
```
What's the weather in Amsterdam?
```

**Combined Query:**
```
I need to schedule a meeting with someone in London. What's the weather there?
```

### Weather Agent

**Get Current Time:**
```
What time is it in Tokyo?
```

**Get Weather:**
```
What's the weather like in Seattle?
```

**Note:** Weather Agent can be called directly or via SummitAssistant (agent-to-agent communication).

## Development

### Local Development with Docker Compose

```bash
cd summitassistant-agent
docker-compose up
```

This starts:
- SummitAssistant agent
- LocalStack (S3 emulation)
- vLLM service (CPU mode)

### Running Tests

```bash
cd summitassistant-agent
pytest tests/
```

### Code Quality

```bash
# Format code
black src/

# Lint
ruff check src/

# Type checking
mypy src/
```

## Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl get pods

# View logs
kubectl logs deployment/SummitAssistant
kubectl logs deployment/strands-weather-agent

# Describe pod for events
kubectl describe pod <pod-name>
```

### AWS Bedrock Access Issues

Ensure the IAM role has proper permissions:
```bash
# Check service account
kubectl describe sa model-storage-sa

# Verify IAM role has Bedrock permissions
aws iam get-role-policy --role-name <role-name> --policy-name BedrockAccess
```

Required permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel"],
      "Resource": ["arn:aws:bedrock:*::foundation-model/anthropic.claude-*"]
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::SummitAssistant-demo-bucket",
        "arn:aws:s3:::SummitAssistant-demo-bucket/*"
      ]
    }
  ]
}
```

### Agent-to-Agent Communication Issues

```bash
# Test Weather Agent directly
kubectl port-forward svc/strands-weather-agent 8000:80
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the weather in Amsterdam?"}'

# Check SummitAssistant logs for Weather Agent calls
kubectl logs -l app=SummitAssistant | grep "Weather Agent"
```

## Documentation

- **[Bedrock Setup Guide](summitassistant-agent/BEDROCK_SETUP.md)** - Comprehensive AWS Bedrock configuration
- **[Agent-to-Agent Communication](AGENT_TO_AGENT_COMMUNICATION.md)** - How agents communicate
- **[Quick Reference](QUICK_REFERENCE.md)** - Quick commands and tips
- **[Weather Agent README](weather-agent/README.md)** - Weather Agent documentation

## Benefits of AWS Bedrock Architecture

- **Cost Savings**: 60-75% reduction vs self-hosted LLMs (no GPU costs)
- **No Infrastructure Management**: No vLLM or GPU nodes to manage
- **Better Performance**: Claude Sonnet 4 provides superior responses
- **Auto-Scaling**: AWS handles all scaling automatically
- **High Availability**: AWS-managed SLA and redundancy
- **Latest Models**: Access to newest Claude and Nova models

## Roadmap

- [x] Full AWS Bedrock integration
- [x] Agent-to-agent communication
- [ ] Add support for multiple calendar providers
- [ ] Implement conversation memory with vector search
- [ ] Add support for voice input/output
- [ ] Create mobile app interface
- [ ] Add multi-language support
- [ ] Implement advanced analytics dashboard

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [Strands Agents](https://strandsagents.com) - AI agent framework
- [AWS Bedrock](https://aws.amazon.com/bedrock/) - Managed AI service
- [Amazon EKS](https://aws.amazon.com/eks/) - Kubernetes service
- [Model Context Protocol](https://modelcontextprotocol.io) - MCP specification
- [Open-Meteo](https://open-meteo.com/) - Weather API

## Support

For questions or issues:

- Open an issue in this repository
- Contact the maintainers
- Check the [Strands Agents documentation](https://strandsagents.com/latest/documentation/)

## Project Status

Active development (prior to) for AWS London Summit 2026 - AWS Village.

---

Built with ❤️ for AWS London Summit 2026
