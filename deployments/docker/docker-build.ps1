#!/usr/bin/env pwsh

# Docker build script for Agent Runtime API

param(
    [string]$Action = "build",
    [string]$Tag = "agent-runtime-api:latest",
    [switch]$NoCache,
    [switch]$Verbose
)

Write-Host "🚀 Agent Runtime API Docker Management" -ForegroundColor Cyan

function Build-Image {
    Write-Host "📦 Building Docker image..." -ForegroundColor Yellow
    
    $buildArgs = @("build", "-t", $Tag)
    
    if ($NoCache) {
        $buildArgs += "--no-cache"
        Write-Host "   Using --no-cache flag" -ForegroundColor Gray
    }
    
    if ($Verbose) {
        $buildArgs += "--progress=plain"
    }
    
    $buildArgs += "."
    
    Write-Host "   Command: docker $($buildArgs -join ' ')" -ForegroundColor Gray
    docker @buildArgs
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Build completed successfully!" -ForegroundColor Green
        
        # Show image info
        Write-Host "`n📊 Image Information:" -ForegroundColor Cyan
        docker images $Tag --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
    } else {
        Write-Host "❌ Build failed!" -ForegroundColor Red
        exit 1
    }
}

function Start-Container {
    Write-Host "🚀 Starting container with docker-compose..." -ForegroundColor Yellow
    docker-compose up -d
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Container started successfully!" -ForegroundColor Green
        Write-Host "🌐 API available at: http://localhost:5001" -ForegroundColor Cyan
        Write-Host "📋 Health check: http://localhost:5001/health" -ForegroundColor Cyan
        
        # Show running containers
        Write-Host "`n📊 Running Containers:" -ForegroundColor Cyan
        docker-compose ps
    } else {
        Write-Host "❌ Failed to start container!" -ForegroundColor Red
        exit 1
    }
}

function Stop-Container {
    Write-Host "🛑 Stopping containers..." -ForegroundColor Yellow
    docker-compose down
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Containers stopped successfully!" -ForegroundColor Green
    } else {
        Write-Host "❌ Failed to stop containers!" -ForegroundColor Red
        exit 1
    }
}

function Show-Logs {
    Write-Host "📋 Showing container logs..." -ForegroundColor Yellow
    docker-compose logs -f
}

function Clean-Up {
    Write-Host "🧹 Cleaning up Docker resources..." -ForegroundColor Yellow
    
    # Stop and remove containers
    docker-compose down
    
    # Remove image
    docker rmi $Tag -f
    
    # Prune unused resources
    docker system prune -f
    
    Write-Host "✅ Cleanup completed!" -ForegroundColor Green
}

function Show-Status {
    Write-Host "📊 Docker Status:" -ForegroundColor Cyan
    
    Write-Host "`nImages:" -ForegroundColor Yellow
    docker images | grep -E "(agent-runtime|REPOSITORY)"
    
    Write-Host "`nContainers:" -ForegroundColor Yellow
    docker-compose ps
    
    Write-Host "`nVolumes:" -ForegroundColor Yellow
    docker volume ls | grep -E "(agent-|DRIVER)"
}

# Main execution
switch ($Action.ToLower()) {
    "build" { Build-Image }
    "start" { Start-Container }
    "stop" { Stop-Container }
    "restart" { 
        Stop-Container
        Start-Container
    }
    "logs" { Show-Logs }
    "clean" { Clean-Up }
    "status" { Show-Status }
    "rebuild" {
        Stop-Container
        Build-Image
        Start-Container
    }
    default {
        Write-Host "❓ Usage: ./docker-build.ps1 [ACTION]" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Available actions:" -ForegroundColor Cyan
        Write-Host "  build    - Build the Docker image" -ForegroundColor White
        Write-Host "  start    - Start the container with docker-compose" -ForegroundColor White
        Write-Host "  stop     - Stop the container" -ForegroundColor White
        Write-Host "  restart  - Stop and start the container" -ForegroundColor White
        Write-Host "  logs     - Show container logs" -ForegroundColor White
        Write-Host "  status   - Show Docker status" -ForegroundColor White
        Write-Host "  clean    - Clean up Docker resources" -ForegroundColor White
        Write-Host "  rebuild  - Stop, rebuild, and start" -ForegroundColor White
        Write-Host ""
        Write-Host "Flags:" -ForegroundColor Cyan
        Write-Host "  -NoCache   - Build without cache" -ForegroundColor White
        Write-Host "  -Verbose   - Verbose build output" -ForegroundColor White
        Write-Host "  -Tag       - Custom tag (default: agent-runtime-api:latest)" -ForegroundColor White
    }
}
