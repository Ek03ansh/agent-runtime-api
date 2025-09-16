#!/usr/bin/env python3
"""WebSocket Logger - Real-time Task Monitoring"""
import asyncio
import websockets
import json
import sys
from datetime import datetime
from shared_config import *

async def handle_message(data):
    """Process and display WebSocket messages"""
    event_type = data.get("event_type", "unknown")
    event_data = data.get("data", {})
    
    # Format timestamp
    timestamp = event_data.get("timestamp", "")
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            time_str = dt.strftime("%H:%M:%S")
        except:
            time_str = timestamp[:8] if len(timestamp) > 8 else timestamp
    else:
        time_str = datetime.now().strftime("%H:%M:%S")
    
    # Handle different event types
    if event_type == "debug":
        level = event_data.get("level", "DEBUG")
        message = event_data.get("message", "")
        agent = event_data.get("agent", "")
        
        level_icons = {"ERROR": "❌", "INFO": "ℹ️", "WARNING": "⚠️"}
        icon = level_icons.get(level, "🔧")
        agent_info = f" [{agent}]" if agent else ""
        
        print(f"[{time_str}] {icon} {message}{agent_info}")
    
    elif event_type == "status":
        status = event_data.get("status", "unknown")
        phase = event_data.get("phase", "")
        
        status_icons = {
            "running": "⚡", "completed": "✅", "failed": "❌", 
            "cancelled": "⏹️", "pending": "⏳"
        }
        icon = status_icons.get(status.lower(), "📊")
        phase_info = f" | {phase}" if phase else ""
        
        print(f"[{time_str}] {icon} Status: {status.upper()}{phase_info}")
    
    elif event_type == "phase":
        phase = event_data.get("phase", "unknown")
        phase_icons = {
            "planning": "📋", "generating_tests": "⚡", 
            "fixing_tests": "🔧", "completed": "✅"
        }
        icon = phase_icons.get(phase.lower(), "📊")
        
        print(f"[{time_str}] {icon} Phase: {phase.upper()}")
    
    elif event_type == "complete":
        success = event_data.get("success", False)
        error = event_data.get("error", "")
        
        if success:
            print(f"[{time_str}] 🎉 Task completed successfully!")
        else:
            print(f"[{time_str}] 💥 Task failed!")
            if error:
                print(f"[{time_str}] ❌ Error: {error}")
        
        print("\n" + "=" * 60)
        print("🏁 Task finished. WebSocket remains open for final messages...")
    
    elif event_type == "log":
        level = event_data.get("level", "INFO")
        message = event_data.get("message", "")
        
        level_icons = {"ERROR": "❌", "WARNING": "⚠️", "INFO": "ℹ️", "DEBUG": "🔧"}
        icon = level_icons.get(level.upper(), "📝")
        
        print(f"[{time_str}] {icon} {message}")
    
    else:
        print(f"[{time_str}] 📥 {event_type}: {event_data}")

async def stream_logs(task_id, env, config, bearer_token=None):
    """Connect and stream real-time logs"""
    base_url = config['url']
    
    # Convert to WebSocket URL
    ws_url = base_url.replace('https://', 'wss://').replace('http://', 'ws://')
    uri = f"{ws_url}/tasks/{task_id}/stream"
    
    # Add identifier for Container Apps
    if env == 'containerapp':
        uri += f"?identifier={get_identifier(env)}"
    
    print(f"🔌 Connecting to {env.upper()} WebSocket...")
    print(f"📡 URI: {uri}")
    if env == 'containerapp':
        print(f"🆔 Identifier: {get_identifier(env)}")
    print("=" * 60)
    
    # Prepare headers
    headers = {}
    if config['auth_type'] == 'bearer' and bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    
    try:
        # Connect to WebSocket
        connect_kwargs = {"additional_headers": headers} if headers else {}
        
        async with websockets.connect(uri, **connect_kwargs) as websocket:
            print("✅ Connected! Streaming real-time logs...")
            print("Press Ctrl+C to disconnect\n")
            
            while True:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)
                    await handle_message(data)
                    
                except websockets.exceptions.ConnectionClosed:
                    print("\n🔌 WebSocket connection closed by server")
                    break
                except json.JSONDecodeError as e:
                    print(f"❌ Failed to parse JSON: {e}")
                    print(f"Raw message: {message}")
                except Exception as e:
                    print(f"❌ Error processing message: {e}")
                    break
                    
    except websockets.exceptions.InvalidURI:
        print(f"❌ Invalid WebSocket URI: {uri}")
    except websockets.exceptions.InvalidHandshake as e:
        print(f"❌ WebSocket handshake failed: {e}")
        if config['auth_type'] == 'bearer':
            print("This might be due to authentication issues.")
    except ConnectionRefusedError:
        print(f"❌ Connection refused. Is the server running?")
    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")

def show_help():
    """Show usage help"""
    print("""
WebSocket Logger - Real-time Task Monitoring

Usage:
  python websocket_logger.py <task_id> --env <environment> [options]

Environments:
  --env local         Local development 
  --env appservice    Azure App Service
  --env containerapp  Azure Container Apps (requires --identifier)

Options:
  --identifier <id>   Container Apps session identifier (REQUIRED for containerapp)

Examples:
  python websocket_logger.py abc123 --env local
  python websocket_logger.py abc123 --env appservice  
  python websocket_logger.py abc123 --env containerapp --identifier <session-id>

Event Types:
  🔧 debug     - Agent debug messages
  📊 status    - Task status changes  
  📋 phase     - Phase transitions
  🎉 complete  - Task completion
  📝 log       - Generic log messages
    """)

async def main():
    if len(sys.argv) < 2:
        show_help()
        return
    
    if sys.argv[1].lower() in ['help', '--help', '-h']:
        show_help()
        return
    
    task_id = sys.argv[1]
    
    # Get configuration
    env, config = get_environment()
    bearer_token = None
    
    if config['auth_type'] == 'bearer':
        print("🔑 Getting bearer token...")
        bearer_token = get_bearer_token()
        if not bearer_token:
            print("❌ Could not obtain bearer token. Please run: az login")
            return
        print("✅ Bearer token obtained")
    
    try:
        await stream_logs(task_id, env, config, bearer_token)
    except KeyboardInterrupt:
        print("\n⏹️ Disconnected by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    try:
        import websockets
        asyncio.run(main())
    except ImportError:
        print("❌ websockets library not installed.")
        print("Install it with: pip install websockets")