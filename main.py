"""
Agent Runtime API

FastAPI-based Agent Runtime API for TestingAgent2 - orchestrates AI agents for automated test generation.

This is the main application entry point that sets up the FastAPI app with proper routing
and middleware configuration.
"""

import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.controllers.task_controller import router as task_router
from app.controllers.auth_controller import router as auth_router
from app.controllers.session_controller import router as session_router
from app.utils.helpers import ensure_directory_exists

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown"""
    # Startup
    ensure_directory_exists(settings.session_root)
    logger.info(f"Agent Runtime API started. Sessions: {settings.session_root}")
    logger.info(f"OpenCode command: {settings.opencode_command}")
    logger.info(f"OpenCode available: {settings.opencode_available}")
    
    yield
    
    # Shutdown - cleanup background tasks and websocket connections
    from app.services.agent_service import agent_service
    from app.services.websocket_manager import websocket_manager
    
    logger.info("Agent Runtime API shutting down - cleaning up resources...")
    
    # First, shutdown all running OpenCode processes
    await agent_service.shutdown_all_processes()
    
    # Cancel any remaining background tasks
    if hasattr(agent_service, '_background_tasks'):
        for task in agent_service._background_tasks:
            if not task.done():
                task.cancel()
        # Wait for tasks to finish cancellation
        if agent_service._background_tasks:
            await asyncio.gather(*agent_service._background_tasks, return_exceptions=True)
    
    # Close any remaining websocket connections
    for connections in websocket_manager.connections.values():
        for ws in connections[:]:
            try:
                await ws.close()
            except Exception:
                pass
    
    logger.info("Agent Runtime API shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Agent Runtime API",
    description="FastAPI-based Agent Runtime API for TestingAgent2 - orchestrates AI agents for automated test generation",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(task_router)
app.include_router(auth_router)
app.include_router(session_router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Agent Runtime API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app", 
        host=settings.host, 
        port=settings.port,
        log_level=settings.log_level.lower()
    )
