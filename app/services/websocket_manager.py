import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Set
from fastapi import WebSocket
from app.models import DebugMessage, StreamEvent

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections for real-time task streaming"""
    
    def __init__(self):
        # Dictionary mapping task_id to list of connected WebSocket clients
        self.connections: Dict[str, List[WebSocket]] = {}
        # Set of all active connections for cleanup
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket, task_id: str):
        """Accept a new WebSocket connection for a specific task"""
        await websocket.accept()
        
        if task_id not in self.connections:
            self.connections[task_id] = []
        
        self.connections[task_id].append(websocket)
        self.active_connections.add(websocket)
        
        logger.debug(f"WebSocket connected for task {task_id}. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket, task_id: str):
        """Remove a WebSocket connection"""
        if task_id in self.connections:
            if websocket in self.connections[task_id]:
                self.connections[task_id].remove(websocket)
            
            # Clean up empty task connection lists
            if not self.connections[task_id]:
                del self.connections[task_id]
        
        self.active_connections.discard(websocket)
        logger.debug(f"WebSocket disconnected for task {task_id}. Total connections: {len(self.active_connections)}")
    
    async def _send_to_clients(self, task_id: str, message: str):
        """Send message to all clients for a task, handling disconnections"""
        if task_id not in self.connections:
            return
        
        disconnected = []
        for websocket in self.connections[task_id]:
            try:
                await websocket.send_text(message)
            except Exception:
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(ws, task_id)
    
    async def cleanup_stale_connections(self):
        """Clean up stale WebSocket connections periodically"""
        stale_connections = []
        
        for task_id, connections in self.connections.items():
            for websocket in connections[:]:  # Create a copy to iterate
                try:
                    # Try to ping the connection
                    await websocket.ping()
                except Exception:
                    stale_connections.append((websocket, task_id))
        
        # Remove stale connections
        for websocket, task_id in stale_connections:
            self.disconnect(websocket, task_id)
            
        if stale_connections:
            logger.info(f"Cleaned up {len(stale_connections)} stale WebSocket connections")

    async def send_debug_message(self, task_id: str, level: str, message: str, agent: str = None):
        """Send a debug message to all clients connected to a specific task"""
        debug_msg = DebugMessage(
            timestamp=datetime.now(),
            level=level,
            message=message,
            task_id=task_id,
            agent=agent
        )
        
        event = StreamEvent(
            event_type="debug",
            data=debug_msg.dict()
        )
        
        await self._send_to_clients(task_id, json.dumps(event.dict(), default=str))
    
    async def send_status_update(self, task_id: str, status: str, phase: str = None):
        """Send a status update to all clients connected to a specific task"""
        event = StreamEvent(
            event_type="status",
            data={
                "task_id": task_id,
                "status": status,
                "phase": phase,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        await self._send_to_clients(task_id, json.dumps(event.dict(), default=str))
    
    async def send_completion(self, task_id: str, success: bool, error: str = None):
        """Send task completion notification"""
        event = StreamEvent(
            event_type="complete",
            data={
                "task_id": task_id,
                "success": success,
                "error": error,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        await self._send_to_clients(task_id, json.dumps(event.dict(), default=str))
    
    def get_connection_count(self, task_id: str = None) -> int:
        """Get number of active connections for a task or total"""
        if task_id:
            return len(self.connections.get(task_id, []))
        return len(self.active_connections)


# Global WebSocket manager instance
websocket_manager = WebSocketManager()
