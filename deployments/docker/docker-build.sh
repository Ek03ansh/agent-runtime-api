#!/bin/bash

# Docker build script for Agent Runtime API (Linux deployment)

set -e  # Exit on any error

ACTION="${1:-build}"
TAG="${2:-agent-runtime-api:latest}"
NO_CACHE="${3:-false}"

echo "🚀 Agent Runtime API Docker Management"

build_image() {
    echo "📦 Building Docker image..."
    
    BUILD_ARGS="--build -t $TAG"
    
    if [ "$NO_CACHE" = "true" ]; then
        BUILD_ARGS="$BUILD_ARGS --no-cache"
        echo "   Using --no-cache flag"
    fi
    
    echo "   Command: docker $BUILD_ARGS ."
    docker build $BUILD_ARGS .
    
    if [ $? -eq 0 ]; then
        echo "✅ Build completed successfully!"
        echo ""
        echo "📊 Image Information:"
        docker images $TAG --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
    else
        echo "❌ Build failed!"
        exit 1
    fi
}

start_container() {
    echo "🚀 Starting container with docker-compose..."
    docker-compose up -d
    
    if [ $? -eq 0 ]; then
        echo "✅ Container started successfully!"
        echo "🌐 API available at: http://localhost:5001"
        echo "📋 Health check: http://localhost:5001/health"
        echo ""
        echo "📊 Running Containers:"
        docker-compose ps
    else
        echo "❌ Failed to start container!"
        exit 1
    fi
}

stop_container() {
    echo "🛑 Stopping container..."
    docker-compose down
    echo "✅ Container stopped!"
}

show_logs() {
    echo "📝 Container logs:"
    docker-compose logs -f
}

show_status() {
    echo "📊 Docker Status:"
    echo ""
    echo "🐳 Running Containers:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    echo "📦 Images:"
    docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
}

clean_resources() {
    echo "🧹 Cleaning up Docker resources..."
    docker-compose down -v
    docker system prune -f
    echo "✅ Cleanup completed!"
}

case $ACTION in
    "build")
        build_image
        ;;
    "start")
        start_container
        ;;
    "stop")
        stop_container
        ;;
    "restart")
        stop_container
        start_container
        ;;
    "logs")
        show_logs
        ;;
    "status")
        show_status
        ;;
    "clean")
        clean_resources
        ;;
    "rebuild")
        stop_container
        build_image
        start_container
        ;;
    *)
        echo "Usage: $0 {build|start|stop|restart|logs|status|clean|rebuild} [tag] [no-cache]"
        echo ""
        echo "Commands:"
        echo "  build    - Build the Docker image"
        echo "  start    - Start the container with docker-compose"
        echo "  stop     - Stop the container"
        echo "  restart  - Stop and start the container"
        echo "  logs     - Show container logs"
        echo "  status   - Show Docker status"
        echo "  clean    - Clean up Docker resources"
        echo "  rebuild  - Stop, rebuild, and start"
        echo ""
        echo "Examples:"
        echo "  $0 build                    # Build with default tag"
        echo "  $0 build custom:tag         # Build with custom tag"
        echo "  $0 build custom:tag true    # Build with no-cache"
        exit 1
        ;;
esac
