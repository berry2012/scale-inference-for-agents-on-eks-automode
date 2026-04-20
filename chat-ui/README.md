# SummitAssistant Chat UI

A modern, responsive chat interface for interacting with the SummitAssistant agent.

## Features

- 💬 Real-time chat interface
- 🎨 Modern, clean design
- 📱 Fully responsive (mobile-friendly)
- ⚡ Fast and lightweight
- 🔄 Auto-scrolling messages
- ⌨️ Keyboard shortcuts (Enter to send, Shift+Enter for new line)
- 🚀 Quick action buttons
- 📊 Connection status indicator
- ✨ Typing indicator
- 🎯 Character counter

## Quick Start

### Local Development

1. **Open in Browser**
   ```bash
   # Simply open index.html in your browser
   open index.html
   ```

2. **Or use a local server**
   ```bash
   # Python
   python -m http.server 8000
   
   # Node.js
   npx http-server
   
   # PHP
   php -S localhost:8000
   ```

3. **Access the UI**
   - Open http://localhost:8000 in your browser

### Docker

```bash
# Build image
docker build -t SummitAssistant-chat-ui .

# Run container
docker run -p 8080:80 SummitAssistant-chat-ui

# Access at http://localhost:8080
```

## Deployment to EKS

### 1. Build and Push Docker Image

```bash
# Set your ECR registry
export ECR_REGISTRY=<your-account-id>.dkr.ecr.<region>.amazonaws.com

# Build image
docker build -t SummitAssistant-chat-ui .

# Tag for ECR
docker tag SummitAssistant-chat-ui:latest $ECR_REGISTRY/SummitAssistant-chat-ui:latest

# Login to ECR
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin $ECR_REGISTRY

# Push to ECR
docker push $ECR_REGISTRY/SummitAssistant-chat-ui:latest
```

### 2. Update Kubernetes Manifests

Edit `k8s/deployment.yaml` and replace `<ECR_REGISTRY>` with your actual ECR registry URL.

### 3. Deploy to EKS

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

# Get the LoadBalancer URL
kubectl get svc SummitAssistant-chat-ui

# Wait for LoadBalancer to be provisioned
kubectl get svc SummitAssistant-chat-ui -w
```

### 4. Access the UI

Once the LoadBalancer is ready, you'll see an EXTERNAL-IP. Access the chat UI at:
```
http://<EXTERNAL-IP>
```

## Configuration

### API Endpoint

The chat UI automatically detects the API endpoint:
- **Local development**: `http://localhost:8080`
- **Production**: Uses the same hostname as the UI

To customize the API endpoint, edit `app.js`:

```javascript
getApiUrl() {
    return 'http://your-api-endpoint:8080';
}
```

## Architecture

```
┌─────────────────┐
│   Chat UI       │
│  (Static HTML)  │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐
│  SummitAssistant  │
│     Agent       │
└─────────────────┘
```

## File Structure

```
chat-ui/
├── index.html          # Main HTML file
├── styles.css          # Styling
├── app.js             # JavaScript logic
├── Dockerfile         # Docker image
├── nginx.conf         # Nginx configuration
├── k8s/
│   ├── deployment.yaml # Kubernetes deployment
│   └── service.yaml    # Kubernetes service (LoadBalancer)
└── README.md          # This file
```

## Features in Detail

### Quick Actions

Pre-defined message templates for common tasks:
- 📅 Schedule Meeting
- 📝 Summarize Notes
- 🔍 Search Meetings

### Keyboard Shortcuts

- `Enter`: Send message
- `Shift + Enter`: New line
- Auto-resize textarea as you type

### Status Indicator

Shows connection status:
- 🟢 Green: Connected
- 🔴 Red: Disconnected
- 🟡 Yellow: Connecting

### Message Formatting

Supports basic markdown-like formatting:
- `**bold**` → **bold**
- `*italic*` → *italic*
- `- bullet` → • bullet
- Line breaks preserved

## Customization

### Colors

Edit CSS variables in `styles.css`:

```css
:root {
    --primary-color: #0066cc;
    --background: #f8f9fa;
    --surface: #ffffff;
    /* ... more variables */
}
```

### Branding

Update the logo and title in `index.html`:

```html
<div class="logo">
    <svg class="logo-icon"><!-- Your logo SVG --></svg>
    <h1>Your Brand Name</h1>
</div>
```

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers (iOS Safari, Chrome Mobile)

## Performance

- Lightweight: ~50KB total (HTML + CSS + JS)
- No external dependencies
- Optimized for fast loading
- Gzip compression enabled

## Security

- XSS protection headers
- Content Security Policy
- No inline scripts
- Input sanitization

## Troubleshooting

### Can't connect to agent

1. Check if the SummitAssistant agent is running
2. Verify the API endpoint in `app.js`
3. Check browser console for errors
4. Ensure CORS is configured on the agent

### UI not loading

1. Check nginx logs: `kubectl logs -l app=SummitAssistant-chat-ui`
2. Verify the LoadBalancer is provisioned
3. Check security groups allow port 80

### Messages not sending

1. Open browser DevTools (F12)
2. Check Network tab for failed requests
3. Verify API endpoint is correct
4. Check agent logs for errors

## Development

### Adding New Features

1. Edit `app.js` for functionality
2. Edit `styles.css` for styling
3. Edit `index.html` for structure
4. Test locally before deploying

### Testing

```bash
# Test locally
open index.html

# Test with Docker
docker build -t test-ui .
docker run -p 8080:80 test-ui
```

## Production Considerations

### HTTPS

For production, use HTTPS:

1. **Option 1: AWS ALB with ACM**
   - Create ACM certificate
   - Configure ALB with HTTPS listener
   - Update service to use ALB

2. **Option 2: Ingress with cert-manager**
   ```yaml
   apiVersion: networking.k8s.io/v1
   kind: Ingress
   metadata:
     name: chat-ui-ingress
     annotations:
       cert-manager.io/cluster-issuer: letsencrypt-prod
   spec:
     tls:
     - hosts:
       - chat.yourdomain.com
       secretName: chat-ui-tls
     rules:
     - host: chat.yourdomain.com
       http:
         paths:
         - path: /
           pathType: Prefix
           backend:
             service:
               name: SummitAssistant-chat-ui
               port:
                 number: 80
   ```

### Custom Domain

1. Create Route53 hosted zone
2. Add A record pointing to LoadBalancer
3. Update CORS settings on agent

### Monitoring

Add monitoring with CloudWatch:

```yaml
# Add to deployment.yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "80"
  prometheus.io/path: "/metrics"
```

## License

MIT
