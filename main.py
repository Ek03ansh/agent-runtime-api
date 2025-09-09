"""
Agent Runtime API

FastAPI-based Agent Runtime API for TestingAgent2 - orchestrates AI agents for automated test generation.

This is the main application entry point that sets up the FastAPI app with proper routing
and middleware configuration.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.controllers.task_controller import router as task_router
from app.controllers.auth_controller import router as auth_router
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
    
    # Shutdown
    logger.info("Agent Runtime API shutting down")


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
