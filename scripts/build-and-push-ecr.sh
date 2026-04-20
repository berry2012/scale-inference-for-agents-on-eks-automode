#!/bin/bash
# summitassistant Multi-Image ECR Build and Push Script
# Builds and pushes all container images to ECR with automatic repo creation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REGION="${AWS_REGION:-us-east-2}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
PLATFORM="linux/amd64"

# Define all images to build (bash 3 compatible)
IMAGE_NAMES=("summitassistant" "calendar-mcp-server" "summitassistant-chat-ui" "weather-agent" "weather-mcp-server")
IMAGE_CONTEXTS=("summitassistant-agent" "calendar-mcp-server" "chat-ui" "weather-agent" "weather-mcp-server")

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  summitassistant Multi-Image ECR Build and Push Script     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Configuration:${NC}"
echo "  Region:   $REGION"
echo "  Tag:      $IMAGE_TAG"
echo "  Platform: $PLATFORM"
echo "  Images:   ${IMAGE_NAMES[*]}"
echo ""

# Get AWS account ID
echo -e "${YELLOW}Getting AWS account ID...${NC}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
if [ -z "$ACCOUNT_ID" ]; then
    echo -e "${RED}✗ Failed to get AWS account ID. Check your AWS credentials.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Account ID: $ACCOUNT_ID${NC}"
echo ""

# ECR registry base URL
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# Function to create ECR repository if it doesn't exist
create_ecr_repo_if_needed() {
    local repo_name=$1
    
    echo -e "${YELLOW}Checking ECR repository: $repo_name${NC}"
    
    if aws ecr describe-repositories --repository-names "$repo_name" --region "$REGION" >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Repository '$repo_name' already exists${NC}"
    else
        echo -e "${YELLOW}Creating ECR repository '$repo_name'...${NC}"
        aws ecr create-repository \
            --repository-name "$repo_name" \
            --region "$REGION" \
            --image-scanning-configuration scanOnPush=true \
            --encryption-configuration encryptionType=AES256 \
            >/dev/null
        echo -e "${GREEN}✓ Repository '$repo_name' created successfully${NC}"
    fi
}

# Function to build and push an image
build_and_push_image() {
    local image_name=$1
    local build_context=$2
    local ecr_uri="${ECR_REGISTRY}/${image_name}"
    
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Building and pushing: $image_name${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    # Create repository if needed
    create_ecr_repo_if_needed "$image_name"
    
    # Build the image
    echo -e "${YELLOW}Building Docker image...${NC}"
    echo "  Context:  $build_context"
    echo "  Platform: $PLATFORM"
    
    if docker build \
        --platform "$PLATFORM" \
        -t "$image_name:$IMAGE_TAG" \
        -f "$build_context/Dockerfile" \
        "$build_context"; then
        echo -e "${GREEN}✓ Image built successfully${NC}"
    else
        echo -e "${RED}✗ Failed to build image${NC}"
        return 1
    fi
    
    # Tag for ECR
    echo -e "${YELLOW}Tagging image for ECR...${NC}"
    docker tag "$image_name:$IMAGE_TAG" "$ecr_uri:$IMAGE_TAG"
    echo -e "${GREEN}✓ Tagged as $ecr_uri:$IMAGE_TAG${NC}"
    
    # Push to ECR
    echo -e "${YELLOW}Pushing image to ECR...${NC}"
    if docker push "$ecr_uri:$IMAGE_TAG"; then
        echo -e "${GREEN}✓ Image pushed successfully${NC}"
        echo -e "${GREEN}✓ Image URI: $ecr_uri:$IMAGE_TAG${NC}"
    else
        echo -e "${RED}✗ Failed to push image${NC}"
        return 1
    fi
}

# Change to project root directory (script should be run from root or scripts/)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ "$SCRIPT_DIR" == */scripts ]]; then
    # Script is in scripts/ folder, go up one level
    cd "$(dirname "$0")/.."
else
    # Script is already at root level
    cd "$(dirname "$0")"
fi
PROJECT_ROOT=$(pwd)

# Authenticate Docker to ECR
echo -e "${YELLOW}Authenticating Docker to ECR...${NC}"
if aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY" >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Docker authenticated to ECR${NC}"
else
    echo -e "${RED}✗ Failed to authenticate Docker to ECR${NC}"
    exit 1
fi

# Track success/failure
SUCCESSFUL_IMAGES=()
FAILED_IMAGES=()

# Build and push each image
for i in "${!IMAGE_NAMES[@]}"; do
    image_name="${IMAGE_NAMES[$i]}"
    build_context="${IMAGE_CONTEXTS[$i]}"
    
    if build_and_push_image "$image_name" "$build_context"; then
        SUCCESSFUL_IMAGES+=("$image_name")
    else
        FAILED_IMAGES+=("$image_name")
    fi
done

# Summary
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    Build Summary                           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ ${#SUCCESSFUL_IMAGES[@]} -gt 0 ]; then
    echo -e "${GREEN}✓ Successfully built and pushed (${#SUCCESSFUL_IMAGES[@]}):${NC}"
    for img in "${SUCCESSFUL_IMAGES[@]}"; do
        echo -e "  ${GREEN}✓${NC} $img"
        echo "    ${ECR_REGISTRY}/${img}:${IMAGE_TAG}"
    done
    echo ""
fi

if [ ${#FAILED_IMAGES[@]} -gt 0 ]; then
    echo -e "${RED}✗ Failed to build/push (${#FAILED_IMAGES[@]}):${NC}"
    for img in "${FAILED_IMAGES[@]}"; do
        echo -e "  ${RED}✗${NC} $img"
    done
    echo ""
    exit 1
fi

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          All images built and pushed successfully!         ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Update Kubernetes manifests helper
echo -e "${YELLOW}Next steps:${NC}"
echo ""
echo "1. Update Kubernetes manifests with the new image URIs:"
echo ""
echo "   export ECR_REGISTRY=$ECR_REGISTRY"
echo "   sed -i \"s|<ECR_REGISTRY>|\$ECR_REGISTRY|g\" summitassistant-agent/k8s/deployment.yaml"
echo "   sed -i \"s|<ECR_REGISTRY>|\$ECR_REGISTRY|g\" calendar-mcp-server/k8s/deployment.yaml"
echo "   sed -i \"s|<ECR_REGISTRY>|\$ECR_REGISTRY|g\" chat-ui/k8s/deployment.yaml"
echo "   sed -i \"s|<ECR_REGISTRY>|\$ECR_REGISTRY|g\" weather-agent/k8s/weather-agents.yaml"
echo "   sed -i \"s|<ECR_REGISTRY>|\$ECR_REGISTRY|g\" weather-mcp-server/k8s/deployment.yaml"
echo ""
echo "2. Deploy to Kubernetes:"
echo ""
echo "   kubectl apply -f summitassistant-agent/k8s/"
echo "   kubectl apply -f calendar-mcp-server/k8s/"
echo "   kubectl apply -f chat-ui/k8s/"
echo "   kubectl apply -f weather-agent/k8s/"
echo "   kubectl apply -f weather-mcp-server/k8s/"
echo ""
echo -e "${GREEN}Happy deploying! 🚀${NC}"
