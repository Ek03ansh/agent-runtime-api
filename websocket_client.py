#!/usr/bin/env python3
"""
WebSocket Client for Real-time Task Streaming
Usage: python websocket_client.py <task_id>
"""
import asyncio
import websockets
import json
import sys
from datetime import datetime

async def stream_task_logs(task_id):
    """Connect to WebSocket and stream task logs in real-time"""
    uri = f"ws://localhost:5001/tasks/{task_id}/stream"
    
    print(f"🔌 Connecting to WebSocket for task {task_id}...")
    print(f"📡 URI: {uri}")
    print("=" * 80)
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected! Streaming real-time logs...")
            print("Press Ctrl+C to disconnect\n")
            
            while True:
                try:
                    # Receive message from server
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    # Handle different event types
                    event_type = data.get("event_type", "unknown")
                    event_data = data.get("data", {})
                    
                    if event_type == "debug":
                        timestamp = event_data.get("timestamp", "")
                        level = event_data.get("level", "DEBUG")
                        message_text = event_data.get("message", "")
                        agent = event_data.get("agent", "")
                        
                        # Format timestamp
                        if timestamp:
                            try:
                                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                time_str = dt.strftime("%H:%M:%S")
                            except:
                                time_str = timestamp[:8] if len(timestamp) > 8 else timestamp
                        else:
                            time_str = datetime.now().strftime("%H:%M:%S")
                        
                        # Color coding for different levels
                        if level == "ERROR":
                            level_icon = "❌"
                        elif level == "INFO":
                            level_icon = "ℹ️"
                        else:
                            level_icon = "🔧"
                        
                        agent_info = f" [{agent}]" if agent else ""
                        print(f"[{time_str}] {level_icon} {message_text}{agent_info}")
                    
                    elif event_type == "status":
                        status = event_data.get("status", "unknown")
                        phase = event_data.get("phase", "")
                        timestamp = event_data.get("timestamp", "")
                        
                        if timestamp:
                            try:
                                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                time_str = dt.strftime("%H:%M:%S")
                            except:
                                time_str = timestamp[:8] if len(timestamp) > 8 else timestamp
                        else:
                            time_str = datetime.now().strftime("%H:%M:%S")
                        
                        status_icon = {
                            "running": "⚡",
                            "completed": "✅",
                            "failed": "❌",
                            "cancelled": "⏹️"
                        }.get(status.lower(), "📊")
                        
                        phase_info = f" | {phase}" if phase else ""
                        print(f"[{time_str}] {status_icon} Status: {status.upper()}{phase_info}")
                    
                    elif event_type == "complete":
                        success = event_data.get("success", False)
                        error = event_data.get("error", "")
                        timestamp = event_data.get("timestamp", "")
                        
                        if timestamp:
                            try:
                                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                time_str = dt.strftime("%H:%M:%S")
                            except:
                                time_str = timestamp[:8] if len(timestamp) > 8 else timestamp
                        else:
                            time_str = datetime.now().strftime("%H:%M:%S")
                        
                        if success:
                            print(f"[{time_str}] 🎉 Task completed successfully!")
                        else:
                            print(f"[{time_str}] 💥 Task failed!")
                            if error:
                                print(f"[{time_str}] ❌ Error: {error}")
                        
                        print("\n" + "=" * 80)
                        print("🏁 Task execution finished. WebSocket will remain open for any final messages...")
                    
                    else:
                        print(f"📥 Unknown event: {event_type} - {event_data}")
                
                except websockets.exceptions.ConnectionClosed:
                    print("\n🔌 WebSocket connection closed by server")
                    break
                except json.JSONDecodeError as e:
                    print(f"❌ Failed to parse JSON: {e}")
                except Exception as e:
                    print(f"❌ Error receiving message: {e}")
                    break
    
    except websockets.exceptions.InvalidURI:
        print(f"❌ Invalid WebSocket URI: {uri}")
        return False
    except ConnectionRefusedError:
        print(f"❌ Connection refused. Is the server running on localhost:5001?")
        return False
    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")
        return False

async def main():
    if len(sys.argv) != 2:
        print("Usage: python websocket_client.py <task_id>")
        print("Example: python websocket_client.py abc123-def456-789")
        return
    
    task_id = sys.argv[1]
    
    try:
        await stream_task_logs(task_id)
    except KeyboardInterrupt:
        print("\n⏹️ Disconnected by user (Ctrl+C)")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    # Install websockets if not available: pip install websockets
    try:
        asyncio.run(main())
    except ImportError:
        print("❌ websockets library not installed.")
        print("Install it with: pip install websockets")
