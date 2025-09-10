#!/usr/bin/env pwsh
# Deployment Refresh Script for Agent Runtime API
# This script rebuilds and redeploys the latest changes to Azure Web App

param(
    [switch]$SkipBuild,
    [switch]$Verbose
)

# Configuration
$APP_NAME = "agent-runtime-pw-app"
$RESOURCE_GROUP = "rg-agent-runtime-playwright"
$ACR_NAME = "agentruntime"
$IMAGE_NAME = "agent-runtime-server"
$IMAGE_TAG = "latest"
$SUBSCRIPTION_ID = "9fd9eff4-f386-452e-9893-06417ff6e808"

Write-Host "🚀 Agent Runtime API - Deployment Refresh Script" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# Function to check command success
function Test-LastCommand {
    param($Message)
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Error: $Message" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ $Message" -ForegroundColor Green
}

# Step 1: Build Docker Image (unless skipped)
if (-not $SkipBuild) {
    Write-Host "`n📦 Step 1: Building Docker image..." -ForegroundColor Yellow
    docker build -f docker/Dockerfile -t "${IMAGE_NAME}:${IMAGE_TAG}" ..
    Test-LastCommand "Docker image built successfully"
} else {
    Write-Host "`n⏭️  Step 1: Skipping Docker build" -ForegroundColor Yellow
}

# Step 2: Tag for Azure Container Registry
Write-Host "`n🏷️  Step 2: Tagging image for Azure Container Registry..." -ForegroundColor Yellow
docker tag "${IMAGE_NAME}:${IMAGE_TAG}" "${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}"
Test-LastCommand "Image tagged for ACR"

# Step 3: Login to Azure Container Registry
Write-Host "`n🔐 Step 3: Logging into Azure Container Registry..." -ForegroundColor Yellow
az acr login --name $ACR_NAME --subscription $SUBSCRIPTION_ID
Test-LastCommand "Logged into ACR"

# Step 4: Push to Azure Container Registry
Write-Host "`n⬆️  Step 4: Pushing image to Azure Container Registry..." -ForegroundColor Yellow
docker push "${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}"
Test-LastCommand "Image pushed to ACR"

# Step 5: Update Web App Container
Write-Host "`n🔄 Step 5: Updating Web App container..." -ForegroundColor Yellow
az webapp config container set `
    --name $APP_NAME `
    --resource-group $RESOURCE_GROUP `
    --subscription $SUBSCRIPTION_ID `
    --container-image-name "${ACR_NAME}.azurecr.io/${IMAGE_NAME}:${IMAGE_TAG}" `
    --container-registry-url "https://${ACR_NAME}.azurecr.io"
Test-LastCommand "Web App container updated"

# Step 6: Restart Web App
Write-Host "`n♻️  Step 6: Restarting Web App..." -ForegroundColor Yellow
az webapp restart --name $APP_NAME --resource-group $RESOURCE_GROUP --subscription $SUBSCRIPTION_ID
Test-LastCommand "Web App restarted"

# Step 7: Wait for deployment and test
Write-Host "`n⏳ Step 7: Waiting for deployment to complete..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

Write-Host "`n🧪 Step 8: Testing deployment..." -ForegroundColor Yellow
$healthUrl = "https://${APP_NAME}.azurewebsites.net/health"
$response = try { 
    Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 30
    $_.StatusCode
} catch { 
    $_.Exception.Response.StatusCode.value__ 
}

if ($response -eq 200) {
    Write-Host "✅ Health check passed! App is running at: https://${APP_NAME}.azurewebsites.net" -ForegroundColor Green
    Write-Host "📚 API Documentation: https://${APP_NAME}.azurewebsites.net/docs" -ForegroundColor Green
} else {
    Write-Host "⚠️  Health check returned status: $response" -ForegroundColor Yellow
    Write-Host "🔍 Check logs with: az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP --subscription $SUBSCRIPTION_ID" -ForegroundColor Yellow
}

Write-Host "`n🎉 Deployment refresh completed!" -ForegroundColor Cyan

# Optional: Show recent logs
if ($Verbose) {
    Write-Host "`n📋 Recent logs:" -ForegroundColor Yellow
    az webapp log show --name $APP_NAME --resource-group $RESOURCE_GROUP --subscription $SUBSCRIPTION_ID
}
