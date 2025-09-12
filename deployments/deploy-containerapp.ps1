#!/usr/bin/env pwsh
# Container Apps Deployment Script for Agent Runtime API
# This script rebuilds and redeploys the latest changes to Azure Container Apps Session Pool
#
# Usage Examples:
# .\deploy-containerapp.ps1                                    # Deploy with default timeouts
# .\deploy-containerapp.ps1 -CooldownPeriod 600               # 10 minute cooldown
# .\deploy-containerapp.ps1 -SessionTimeout 7200              # 2 hour session timeout
# .\deploy-containerapp.ps1 -IdleTimeout 3600                 # 1 hour idle timeout
# .\deploy-containerapp.ps1 -SkipBuild -SessionTimeout 1800   # Skip build, 30 min timeout

param(
    [switch]$SkipBuild,
    [switch]$Verbose,
    [string]$RegistryPassword = $env:ACR_PASSWORD,
    [int]$CooldownPeriod = 300,
    [int]$SessionTimeout = 3600,
    [int]$IdleTimeout = 1800
)

# Configuration - Updated for Container Apps
$SESSION_POOL_NAME = "playwrightmcp-sessionpool"
$RESOURCE_GROUP = "issacnitin-poc"
$ENVIRONMENT_NAME = "issacnitinenv"
$ACR_NAME = "issacnitinacr"
$ACR_SERVER = "issacnitinacr.azurecr.io"
$IMAGE_NAME = "agent-runtime"
$TIMESTAMP = Get-Date -Format "yyyyMMdd-HHmmss"
$IMAGE_TAG = "v$TIMESTAMP"
$LOCATION = "eastus"
$SUBSCRIPTION_ID = "acaab7ee-e0fb-43d9-bce9-0e403b60ce06"

Write-Host "🚀 Agent Runtime API - Container Apps Deployment Script" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "🏷️  Image Tag: $IMAGE_TAG" -ForegroundColor Blue
Write-Host "⏱️  Timeout Settings:" -ForegroundColor Blue
Write-Host "   Cooldown Period: $CooldownPeriod seconds" -ForegroundColor Gray
Write-Host "   Session Timeout: $SessionTimeout seconds" -ForegroundColor Gray
Write-Host "   Idle Timeout: $IdleTimeout seconds" -ForegroundColor Gray

# Function to check command success
function Test-LastCommand {
    param($Message)
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Error: $Message" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ $Message" -ForegroundColor Green
}

# Step 0: Get registry password if not provided
if (-not $RegistryPassword) {
    Write-Host "`n🔑 Step 0: Retrieving ACR password..." -ForegroundColor Yellow
    try {
        $RegistryPassword = az acr credential show --name $ACR_NAME --subscription $SUBSCRIPTION_ID --query "passwords[0].value" --output tsv
        if ($RegistryPassword) {
            Write-Host "✅ ACR password retrieved successfully" -ForegroundColor Green
        } else {
            Write-Host "❌ Failed to retrieve ACR password" -ForegroundColor Red
            exit 1
        }
    } catch {
        Write-Host "❌ Error retrieving ACR password: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "💡 Make sure you're logged into Azure CLI and have access to the ACR" -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host "`n🔑 Using provided registry password" -ForegroundColor Yellow
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
docker tag "${IMAGE_NAME}:latest" "${ACR_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}"
docker tag "${IMAGE_NAME}:latest" "${ACR_SERVER}/${IMAGE_NAME}:latest"
Test-LastCommand "Image tagged for ACR with timestamp and latest"

# Step 3: Login to Azure Container Registry
Write-Host "`n🔐 Step 3: Logging into Azure Container Registry..." -ForegroundColor Yellow
az acr login --name $ACR_NAME --subscription $SUBSCRIPTION_ID
Test-LastCommand "Logged into ACR"

# Step 4: Push to Azure Container Registry
Write-Host "`n⬆️  Step 4: Pushing image to Azure Container Registry..." -ForegroundColor Yellow
docker push "${ACR_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}"
docker push "${ACR_SERVER}/${IMAGE_NAME}:latest"
Test-LastCommand "Images pushed to ACR (timestamped and latest)"

# Step 5: Check if session pool exists
Write-Host "`n🔍 Step 5: Checking if Container Apps session pool exists..." -ForegroundColor Yellow
$sessionPoolExists = az containerapp sessionpool show --name $SESSION_POOL_NAME --resource-group $RESOURCE_GROUP --subscription $SUBSCRIPTION_ID 2>$null
if ($sessionPoolExists) {
    Write-Host "📋 Session pool exists. Updating..." -ForegroundColor Yellow
    
    # Update existing session pool (only image and registry settings)
    az containerapp sessionpool update `
        --name $SESSION_POOL_NAME `
        --resource-group $RESOURCE_GROUP `
        --subscription $SUBSCRIPTION_ID `
        --image "${ACR_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}" `
        --registry-server $ACR_SERVER `
        --registry-username $ACR_NAME `
        --registry-password $RegistryPassword `
        --target-port 5001 `
        --cooldown-period $CooldownPeriod
    Test-LastCommand "Session pool updated successfully"
} else {
    Write-Host "🆕 Session pool doesn't exist. Creating..." -ForegroundColor Yellow
    
    # Create new session pool
    az containerapp sessionpool create `
        --name $SESSION_POOL_NAME `
        --resource-group $RESOURCE_GROUP `
        --subscription $SUBSCRIPTION_ID `
        --environment $ENVIRONMENT_NAME `
        --registry-server $ACR_SERVER `
        --registry-username $ACR_NAME `
        --registry-password $RegistryPassword `
        --container-type CustomContainer `
        --image "${ACR_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}" `
        --cpu 2 `
        --memory 4Gi `
        --target-port 5001 `
        --cooldown-period $CooldownPeriod `
        --session-timeout $SessionTimeout `
        --idle-timeout $IdleTimeout `
        --network-status EgressEnabled `
        --max-sessions 100 `
        --ready-sessions 5 `
        --location $LOCATION
    Test-LastCommand "Session pool created successfully"
}

# Step 6: Wait for deployment
Write-Host "`n⏳ Step 6: Waiting for deployment to complete..." -ForegroundColor Yellow
Start-Sleep -Seconds 45

# Step 7: Get session pool details
Write-Host "`n📋 Step 7: Getting session pool details..." -ForegroundColor Yellow
$sessionPoolInfo = az containerapp sessionpool show --name $SESSION_POOL_NAME --resource-group $RESOURCE_GROUP --subscription $SUBSCRIPTION_ID --output json | ConvertFrom-Json

if ($sessionPoolInfo) {
    Write-Host "✅ Session pool deployment completed!" -ForegroundColor Green
    Write-Host "📊 Session Pool Details:" -ForegroundColor Green
    Write-Host "   Name: $($sessionPoolInfo.name)" -ForegroundColor Gray
    Write-Host "   Resource Group: $($sessionPoolInfo.resourceGroup)" -ForegroundColor Gray
    Write-Host "   Location: $($sessionPoolInfo.location)" -ForegroundColor Gray
    Write-Host "   Provisioning State: $($sessionPoolInfo.properties.provisioningState)" -ForegroundColor Gray
    if ($sessionPoolInfo.properties.customContainerTemplate.containers) {
        Write-Host "   Image: $($sessionPoolInfo.properties.customContainerTemplate.containers[0].image)" -ForegroundColor Gray
        Write-Host "   CPU: $($sessionPoolInfo.properties.customContainerTemplate.containers[0].resources.cpu)" -ForegroundColor Gray  
        Write-Host "   Memory: $($sessionPoolInfo.properties.customContainerTemplate.containers[0].resources.memory)" -ForegroundColor Gray
    }
    Write-Host "   Cooldown Period: $($sessionPoolInfo.properties.dynamicPoolConfiguration.cooldownPeriodInSeconds)s" -ForegroundColor Gray
    Write-Host "   Session Timeout: $($sessionPoolInfo.properties.sessionNetworkConfiguration.sessionTimeout)s" -ForegroundColor Gray
    
    # Show session pool status
    Write-Host "`n📈 Session Pool Status:" -ForegroundColor Green
    if ($sessionPoolInfo.properties.poolManagementEndpoint) {
        Write-Host "   Pool Management Endpoint: $($sessionPoolInfo.properties.poolManagementEndpoint)" -ForegroundColor Gray
    }
    if ($sessionPoolInfo.properties.sessionNetworkConfiguration) {
        Write-Host "   Network Status: $($sessionPoolInfo.properties.sessionNetworkConfiguration.status)" -ForegroundColor Gray
    }
} else {
    Write-Host "⚠️  Could not retrieve session pool information" -ForegroundColor Yellow
}

# Step 8: Test the deployment (if management endpoint is available)
Write-Host "`n🧪 Step 8: Testing deployment..." -ForegroundColor Yellow
if ($sessionPoolInfo.properties.poolManagementEndpoint) {
    $healthUrl = "$($sessionPoolInfo.properties.poolManagementEndpoint)/health"
    try {
        $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 30
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ Health check passed!" -ForegroundColor Green
        } else {
            Write-Host "⚠️  Health check returned status: $($response.StatusCode)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "⚠️  Could not perform health check: $($_.Exception.Message)" -ForegroundColor Yellow
    }
} else {
    Write-Host "ℹ️  No public endpoint available for health check" -ForegroundColor Blue
}

Write-Host "`n🎉 Container Apps deployment completed!" -ForegroundColor Cyan

# Optional: Show recent logs
if ($Verbose) {
    Write-Host "`n📋 Recent logs:" -ForegroundColor Yellow
    Write-Host "To view logs, use:" -ForegroundColor Gray
    Write-Host "az containerapp sessionpool logs show --name $SESSION_POOL_NAME --resource-group $RESOURCE_GROUP --subscription $SUBSCRIPTION_ID" -ForegroundColor Gray
}

Write-Host "`n🔧 Useful Commands:" -ForegroundColor Cyan
Write-Host "View session pool: az containerapp sessionpool show --name $SESSION_POOL_NAME --resource-group $RESOURCE_GROUP --subscription $SUBSCRIPTION_ID" -ForegroundColor Gray
Write-Host "List sessions: az containerapp session list --name $SESSION_POOL_NAME --resource-group $RESOURCE_GROUP --subscription $SUBSCRIPTION_ID" -ForegroundColor Gray
Write-Host "View logs: az containerapp sessionpool logs show --name $SESSION_POOL_NAME --resource-group $RESOURCE_GROUP --subscription $SUBSCRIPTION_ID" -ForegroundColor Gray
