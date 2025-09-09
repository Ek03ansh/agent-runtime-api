#!/bin/bash

# Deployment Refresh Script for Agent Runtime API (Linux deployment)
# This script rebuilds and redeploys the latest changes to Azure Web App

set -e  # Exit on any error

SKIP_BUILD="${1:-false}"
VERBOSE="${2:-false}"

# Configuration
APP_NAME="agent-runtime-pw-app"
RESOURCE_GROUP="rg-agent-runtime-playwright"
ACR_NAME="agentruntime"
IMAGE_NAME="agent-runtime-server"
IMAGE_TAG="latest"

echo "🚀 Agent Runtime API - Deployment Refresh Script"
echo "================================================="

# Function to check command success
check_command() {
    if [ $? -ne 0 ]; then
        echo "❌ Error: $1"
        exit 1
    fi
    echo "✅ $1"
}

# Step 1: Build Docker Image (unless skipped)
if [ "$SKIP_BUILD" != "true" ]; then
    echo ""
    echo "📦 Step 1: Building Docker image..."
    docker build -f deployments/docker/Dockerfile -t "${IMAGE_NAME}:${IMAGE_TAG}" .
    check_command "Docker image built successfully"
else
    echo ""
    echo "⏭️  Step 1: Skipping Docker build"
fi

# Step 2: Tag for Azure Container Registry
echo ""
echo "🏷️  Step 2: Tagging image for Azure Container Registry..."
docker tag "${IMAGE_NAME}:${IMAGE_TAG}" "${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}"
check_command "Image tagged for ACR"

# Step 3: Login to Azure Container Registry
echo ""
echo "🔐 Step 3: Logging into Azure Container Registry..."
az acr login --name $ACR_NAME
check_command "Logged into ACR"

# Step 4: Push to Azure Container Registry
echo ""
echo "⬆️  Step 4: Pushing image to Azure Container Registry..."
docker push "${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}"
check_command "Image pushed to ACR"

# Step 5: Update Web App Container
echo ""
echo "🔄 Step 5: Updating Web App container..."
az webapp config container set \
    --name $APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --container-image-name "${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}" \
    --container-registry-url "https://${ACR_NAME}.azurecr.io"
check_command "Web App container updated"

# Step 6: Restart Web App
echo ""
echo "♻️  Step 6: Restarting Web App..."
az webapp restart --name $APP_NAME --resource-group $RESOURCE_GROUP
check_command "Web App restarted"

# Step 7: Wait for deployment and test
echo ""
echo "⏳ Step 7: Waiting for deployment to complete..."
sleep 30

echo ""
echo "🧪 Step 8: Testing deployment..."
HEALTH_URL="https://${APP_NAME}.azurewebsites.net/health"

# Test health endpoint
if curl -f -s --max-time 30 "$HEALTH_URL" > /dev/null; then
    echo "✅ Health check passed! App is running at: https://${APP_NAME}.azurewebsites.net"
    echo "📚 API Documentation: https://${APP_NAME}.azurewebsites.net/docs"
else
    echo "⚠️  Health check failed - checking logs..."
    
    echo ""
    echo "📋 Recent logs:"
    az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP --timeout 30 || true
fi

echo ""
echo "🎉 Deployment refresh completed!"
echo ""
echo "🔗 Useful links:"
echo "   • App URL: https://${APP_NAME}.azurewebsites.net"
echo "   • Health: https://${APP_NAME}.azurewebsites.net/health"
echo "   • Docs: https://${APP_NAME}.azurewebsites.net/docs"
echo "   • Logs: az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP"
