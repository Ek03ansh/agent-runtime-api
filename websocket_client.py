#!/usr/bin/env python3
"""
WebSocket Client for Real-time Task Streaming
Usage: python websocket_client.py <task_id> [--endpoint <local|deployed|url>]
"""
import asyncio
import websockets
import json
import sys
import os
from datetime import datetime

# Configuration for different environments
ENDPOINTS = {
    'local': 'http://localhost:5001',
    'deployed': 'https://agent-runtime-pw-app.azurewebsites.net'
}

def get_base_url():
    """Determine the base URL to use (local or deployed)"""
    
    # Check for environment variable first
    if 'AGENT_API_URL' in os.environ:
        return os.environ['AGENT_API_URL']
    
    # Check for command line argument
    if '--endpoint' in sys.argv:
        idx = sys.argv.index('--endpoint')
        if idx + 1 < len(sys.argv):
            endpoint_arg = sys.argv[idx + 1]
            if endpoint_arg in ENDPOINTS:
                return ENDPOINTS[endpoint_arg]
            elif endpoint_arg.startswith('http'):
                return endpoint_arg
    
    # Default to local for websocket client (unlike test client which auto-detects)
    return ENDPOINTS['local']

async def stream_task_logs(task_id):
    """Connect to WebSocket and stream task logs in real-time"""
    base_url = get_base_url()
    
    # Convert HTTP(S) URL to WebSocket URL
    if base_url.startswith('https://'):
        ws_url = base_url.replace('https://', 'wss://')
    else:
        ws_url = base_url.replace('http://', 'ws://')
    
    uri = f"{ws_url}/tasks/{task_id}/stream"
    
    print(f"🔌 Connecting to WebSocket for task {task_id}...")
    print(f"🌐 Base URL: {base_url}")
    print(f"📡 WebSocket URI: {uri}")
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
        print(f"❌ Connection refused. Is the server running at {base_url}?")
        return False
    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")
        return False

async def main():
    if len(sys.argv) < 2:
        print("Usage: python websocket_client.py <task_id> [--endpoint <local|deployed|url>]")
        print("Examples:")
        print("  python websocket_client.py abc123-def456-789")
        print("  python websocket_client.py abc123-def456-789 --endpoint deployed")
        print("  python websocket_client.py abc123-def456-789 --endpoint local")
        print("  python websocket_client.py abc123-def456-789 --endpoint https://my-app.azurewebsites.net")
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
