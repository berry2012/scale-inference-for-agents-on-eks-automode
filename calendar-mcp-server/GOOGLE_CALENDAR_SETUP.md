# Google Calendar Integration Setup Guide

This guide walks you through setting up real Google Calendar integration for the SummitAssistant MCP server.

## Prerequisites

- Google Cloud Project
- Google Calendar API enabled
- Service Account or OAuth 2.0 credentials
- Python 3.11+

## Step 1: Google Cloud Setup

### 1.1 Create Google Cloud Project

```bash
# Install gcloud CLI if not already installed
# Visit: https://cloud.google.com/sdk/docs/install

# Create new project
gcloud projects create SummitAssistant-calendar --name="SummitAssistant Calendar"

# Set as active project
gcloud config set project SummitAssistant-calendar

# Enable billing (required for API access)
# Visit: https://console.cloud.google.com/billing
```

### 1.2 Enable Google Calendar API

```bash
# Enable Calendar API
gcloud services enable calendar-json.googleapis.com

# Or via console:
# https://console.cloud.google.com/apis/library/calendar-json.googleapis.com
```

## Step 2: Choose Authentication Method

You have two options:

### Option A: Service Account (Recommended for Server-to-Server)

Best for: Automated scheduling without user interaction

**Pros:**
- No user consent required
- Works for server-to-server communication
- Simpler deployment

**Cons:**
- Requires domain-wide delegation for accessing user calendars
- Or creates events in service account's calendar

### Option B: OAuth 2.0 (For User-Specific Calendars)

Best for: Scheduling in specific user's calendars

**Pros:**
- Access to user's personal calendar
- Standard OAuth flow

**Cons:**
- Requires user consent
- Token refresh management
- More complex setup

## Step 3: Service Account Setup (Recommended)

### 3.1 Create Service Account

```bash
# Create service account
gcloud iam service-accounts create calendar-mcp-server \
    --display-name="Calendar MCP Server" \
    --description="Service account for SummitAssistant calendar integration"

# Get service account email
export SA_EMAIL=$(gcloud iam service-accounts list \
    --filter="displayName:Calendar MCP Server" \
    --format="value(email)")

echo "Service Account Email: $SA_EMAIL"
```

### 3.2 Create and Download Credentials

```bash
# Create key
gcloud iam service-accounts keys create ~/calendar-sa-key.json \
    --iam-account=$SA_EMAIL

# Store in Kubernetes secret
kubectl create secret generic calendar-credentials \
    --from-file=credentials.json=~/calendar-sa-key.json \
    --namespace=default

# Clean up local file
rm ~/calendar-sa-key.json
```

### 3.3 Grant Calendar Access

**Option 1: Use Service Account's Calendar**

The service account has its own calendar. Share it with users:

```python
# Calendar ID will be: {SA_EMAIL}
# Example: calendar-mcp-server@SummitAssistant-calendar.iam.gserviceaccount.com
```

**Option 2: Domain-Wide Delegation (G Suite/Workspace Only)**

If you have Google Workspace, enable domain-wide delegation:

1. Go to Google Admin Console
2. Security → API Controls → Domain-wide Delegation
3. Add service account client ID
4. Grant scope: `https://www.googleapis.com/auth/calendar`

## Step 4: OAuth 2.0 Setup (Alternative)

### 4.1 Create OAuth Credentials

```bash
# Via console (easier):
# 1. Go to: https://console.cloud.google.com/apis/credentials
# 2. Create OAuth 2.0 Client ID
# 3. Application type: Web application
# 4. Authorized redirect URIs: https://SummitAssistant.eoalola.people.aws.dev/oauth2/callback
# 5. Download credentials JSON
```

### 4.2 Store OAuth Credentials

```bash
# Store OAuth credentials
kubectl create secret generic calendar-oauth \
    --from-file=client_secret.json=~/client_secret.json \
    --namespace=default
```

## Step 5: Update MCP Server Code

Replace `calendar-mcp-server/main.py` with the real implementation (see `main_google_calendar.py`).

### 5.1 Install Dependencies

Update `requirements.txt`:

```txt
fastapi>=0.109.0
uvicorn>=0.27.0
pydantic>=2.6.0
google-auth>=2.27.0
google-auth-oauthlib>=1.2.0
google-auth-httplib2>=0.2.0
google-api-python-client>=2.116.0
```

### 5.2 Update Kubernetes Deployment

Update `k8s/deployment.yaml` to mount credentials:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: calendar-mcp-server
spec:
  template:
    spec:
      containers:
      - name: mcp-server
        image: <your-registry>/calendar-mcp-server:latest
        env:
        - name: GOOGLE_APPLICATION_CREDENTIALS
          value: /secrets/credentials.json
        - name: CALENDAR_ID
          value: "primary"  # or specific calendar ID
        volumeMounts:
        - name: credentials
          mountPath: /secrets
          readOnly: true
      volumes:
      - name: credentials
        secret:
          secretName: calendar-credentials
```

## Step 6: Test the Integration

### 6.1 Local Testing

```bash
# Set credentials
export GOOGLE_APPLICATION_CREDENTIALS=~/calendar-sa-key.json

# Run server
cd calendar-mcp-server
python main_google_calendar.py

# Test endpoint
curl -X POST http://localhost:8080/schedule \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-03-10",
    "time": "14:00",
    "duration_minutes": 60,
    "attendees": ["test@example.com"],
    "title": "Test Meeting",
    "description": "Testing Google Calendar integration"
  }'
```

### 6.2 Verify in Google Calendar

1. Go to https://calendar.google.com
2. Check the service account's calendar or your calendar
3. Verify the event was created

## Step 7: Deploy to EKS

```bash
# Build and push image
cd calendar-mcp-server
docker build -t <your-registry>/calendar-mcp-server:latest .
docker push <your-registry>/calendar-mcp-server:latest

# Apply updated manifests
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

# Verify deployment
kubectl get pods -l app=calendar-mcp-server
kubectl logs -l app=calendar-mcp-server
```

## Troubleshooting

### Error: "Calendar API has not been used"

```bash
# Enable the API
gcloud services enable calendar-json.googleapis.com
```

### Error: "Insufficient Permission"

```bash
# Check service account has Calendar API access
# Verify credentials are mounted correctly
kubectl exec -it deployment/calendar-mcp-server -- ls -la /secrets/
```

### Error: "Invalid credentials"

```bash
# Recreate secret
kubectl delete secret calendar-credentials
kubectl create secret generic calendar-credentials \
    --from-file=credentials.json=~/calendar-sa-key.json
```

### Events not appearing in user calendars

- If using service account: Share the service account's calendar with users
- If using OAuth: Ensure proper scopes are granted
- Check calendar ID is correct

## Security Best Practices

1. **Rotate credentials regularly**
   ```bash
   # Create new key
   gcloud iam service-accounts keys create new-key.json --iam-account=$SA_EMAIL
   
   # Update secret
   kubectl create secret generic calendar-credentials \
       --from-file=credentials.json=new-key.json \
       --dry-run=client -o yaml | kubectl apply -f -
   
   # Delete old key
   gcloud iam service-accounts keys delete OLD_KEY_ID --iam-account=$SA_EMAIL
   ```

2. **Use least privilege**
   - Only grant Calendar API access
   - Limit to specific calendars if possible

3. **Monitor API usage**
   ```bash
   # View API usage
   gcloud logging read "resource.type=api" --limit 50
   ```

4. **Set up alerts**
   - Monitor for authentication failures
   - Track API quota usage

## Cost Considerations

- Google Calendar API: Free tier includes 1,000,000 queries/day
- Typical usage: ~10-100 requests/day for demo
- No additional costs for basic usage

## Next Steps

1. Test with real calendar events
2. Add error handling for API failures
3. Implement event updates and deletions
4. Add calendar availability checking
5. Support recurring meetings

## References

- [Google Calendar API Documentation](https://developers.google.com/calendar/api/guides/overview)
- [Service Account Authentication](https://cloud.google.com/iam/docs/service-accounts)
- [OAuth 2.0 for Web Apps](https://developers.google.com/identity/protocols/oauth2/web-server)
- [Python Quickstart](https://developers.google.com/calendar/api/quickstart/python)
