import asyncio
import json
from datetime import datetime
from typing import Dict, List, Set
from fastapi import WebSocket
from app.models import DebugMessage, StreamEvent


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
        
        print(f"DEBUG: WebSocket connected for task {task_id}. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket, task_id: str):
        """Remove a WebSocket connection"""
        if task_id in self.connections:
            if websocket in self.connections[task_id]:
                self.connections[task_id].remove(websocket)
            
            # Clean up empty task connection lists
            if not self.connections[task_id]:
                del self.connections[task_id]
        
        self.active_connections.discard(websocket)
        print(f"DEBUG: WebSocket disconnected for task {task_id}. Total connections: {len(self.active_connections)}")
    
    async def send_debug_message(self, task_id: str, level: str, message: str, agent: str = None):
        """Send a debug message to all clients connected to a specific task"""
        if task_id not in self.connections:
            return
        
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
        
        # Send to all connected clients for this task
        disconnected = []
        for websocket in self.connections[task_id]:
            try:
                await websocket.send_text(json.dumps(event.dict(), default=str))
            except Exception:
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(ws, task_id)
    
    async def send_status_update(self, task_id: str, status: str, phase: str = None):
        """Send a status update to all clients connected to a specific task"""
        if task_id not in self.connections:
            return
        
        event = StreamEvent(
            event_type="status",
            data={
                "task_id": task_id,
                "status": status,
                "phase": phase,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        disconnected = []
        for websocket in self.connections[task_id]:
            try:
                await websocket.send_text(json.dumps(event.dict(), default=str))
            except Exception:
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(ws, task_id)
    
    async def send_completion(self, task_id: str, success: bool, error: str = None):
        """Send task completion notification"""
        if task_id not in self.connections:
            return
        
        event = StreamEvent(
            event_type="complete",
            data={
                "task_id": task_id,
                "success": success,
                "error": error,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        disconnected = []
        for websocket in self.connections[task_id]:
            try:
                await websocket.send_text(json.dumps(event.dict(), default=str))
            except Exception:
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(ws, task_id)
    
    def get_connection_count(self, task_id: str = None) -> int:
        """Get number of active connections for a task or total"""
        if task_id:
            return len(self.connections.get(task_id, []))
        return len(self.active_connections)


# Global WebSocket manager instance
websocket_manager = WebSocketManager()
