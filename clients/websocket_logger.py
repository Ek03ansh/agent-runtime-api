#!/usr/bin/env python3
"""
Universal WebSocket Logger
Supports local, App Service, and Container Apps deployments with automatic authentication
Usage: python websocket_logger.py <task_id> --env <local|appservice|containerapp>
"""
import asyncio
import websockets
import json
import sys
import os
import subprocess
from datetime import datetime

# Deployment configurations
DEPLOYMENTS = {
    'local': {
        'url': 'http://localhost:5001',
        'auth_type': 'none',
        'description': 'Local development server'
    },
    'appservice': {
        'url': 'https://agent-runtime-pw-app.azurewebsites.net',
        'auth_type': 'none', 
        'description': 'Azure App Service deployment'
    },
    'containerapp': {
        'url': 'https://playwrightmcp-sessionpool.kindplant-1df81c5d.eastus.azurecontainerapps.io',
        'auth_type': 'bearer',
        'description': 'Azure Container Apps deployment'
    }
}

def get_bearer_token():
    """Get bearer token from Azure CLI for Container Apps"""
    try:
        result = subprocess.run([
            'az', 'account', 'get-access-token', 
            '--resource', 'https://dynamicsessions.io'
        ], capture_output=True, text=True, check=True, shell=True)
        
        token_data = json.loads(result.stdout)
        return token_data.get('accessToken')
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to get access token: {e}")
        print("Make sure you're logged into Azure CLI with: az login")
        return None
    except json.JSONDecodeError:
        print("❌ Failed to parse token response")
        return None
    except Exception as e:
        print(f"❌ Error getting token: {e}")
        return None

def get_deployment_config():
    """Get deployment configuration from command line or environment"""
    # Check command line argument
    if '--env' in sys.argv:
        idx = sys.argv.index('--env')
        if idx + 1 < len(sys.argv):
            env = sys.argv[idx + 1].lower()
            if env in DEPLOYMENTS:
                return env, DEPLOYMENTS[env]
            else:
                print(f"❌ Unknown environment: {env}")
                print(f"Available: {', '.join(DEPLOYMENTS.keys())}")
                sys.exit(1)
    
    # Check environment variable
    if 'DEPLOYMENT_ENV' in os.environ:
        env = os.environ['DEPLOYMENT_ENV'].lower()
        if env in DEPLOYMENTS:
            return env, DEPLOYMENTS[env]
    
    # Default to local with warning
    print("⚠️ No environment specified, defaulting to local")
    print("Use --env <local|appservice|containerapp> to specify")
    return 'local', DEPLOYMENTS['local']

def get_identifier():
    """Get identifier for Container Apps"""
    if '--identifier' in sys.argv:
        idx = sys.argv.index('--identifier')
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return "ea26c5e0-0286-4da0-8d6f-925c71bd822c"

def get_websocket_headers(config, bearer_token=None):
    """Get appropriate headers for WebSocket connection"""
    headers = {}
    
    if config['auth_type'] == 'bearer' and bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    
    return headers

async def stream_task_logs(task_id, env, config, bearer_token=None):
    """Connect to WebSocket and stream task logs in real-time"""
    base_url = config['url']
    
    # Convert HTTP(S) URL to WebSocket URL
    if base_url.startswith('https://'):
        ws_url = base_url.replace('https://', 'wss://')
    else:
        ws_url = base_url.replace('http://', 'ws://')
    
    # Build WebSocket URI
    uri = f"{ws_url}/tasks/{task_id}/stream"
    
    # Always add identifier for Container Apps
    if env == 'containerapp':
        identifier = get_identifier()
        uri += f"?identifier={identifier}"
    
    print(f"🔌 Connecting to {env.upper()} WebSocket for task {task_id}...")
    print(f"🌐 Environment: {config['description']}")
    print(f"📡 WebSocket URI: {uri}")
    
    if config['auth_type'] == 'bearer':
        print(f"🔑 Using bearer token authentication")
        print(f"🆔 Identifier: {get_identifier()}")
    
    print("=" * 80)
    
    # Prepare headers
    headers = get_websocket_headers(config, bearer_token)
    
    try:
        # Connect with or without headers based on auth type
        if headers:
            async with websockets.connect(uri, additional_headers=headers) as websocket:
                await handle_websocket_connection(websocket)
        else:
            async with websockets.connect(uri) as websocket:
                await handle_websocket_connection(websocket)
                
    except websockets.exceptions.InvalidURI:

        print(f"❌ Invalid WebSocket URI: {uri}")
        return False
    except websockets.exceptions.InvalidHandshake as e:
        print(f"❌ WebSocket handshake failed: {e}")
        if config['auth_type'] == 'bearer':
            print("This might be due to authentication issues. Check your bearer token.")
        return False
    except ConnectionRefusedError:
        print(f"❌ Connection refused. Is the server running at {base_url}?")
        return False
    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")
        return False

async def handle_websocket_connection(websocket):
    """Handle the websocket connection and message processing"""
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
                elif level == "WARNING":
                    level_icon = "⚠️"
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
                    "cancelled": "⏹️",
                    "pending": "⏳"
                }.get(status.lower(), "📊")
                
                phase_info = f" | {phase}" if phase else ""
                print(f"[{time_str}] {status_icon} Status: {status.upper()}{phase_info}")
            
            elif event_type == "phase":
                phase = event_data.get("phase", "unknown")
                timestamp = event_data.get("timestamp", "")
                
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        time_str = dt.strftime("%H:%M:%S")
                    except:
                        time_str = timestamp[:8] if len(timestamp) > 8 else timestamp
                else:
                    time_str = datetime.now().strftime("%H:%M:%S")
                
                phase_icon = {
                    "planning": "📋",
                    "generating_tests": "⚡",
                    "fixing_tests": "🔧",
                    "completed": "✅"
                }.get(phase.lower(), "📊")
                
                print(f"[{time_str}] {phase_icon} Phase: {phase.upper()}")
            
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
            
            elif event_type == "log":
                # Handle generic log events
                log_level = event_data.get("level", "INFO")
                log_message = event_data.get("message", "")
                timestamp = event_data.get("timestamp", "")
                
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        time_str = dt.strftime("%H:%M:%S")
                    except:
                        time_str = timestamp[:8] if len(timestamp) > 8 else timestamp
                else:
                    time_str = datetime.now().strftime("%H:%M:%S")
                
                level_icon = {
                    "ERROR": "❌",
                    "WARNING": "⚠️",
                    "INFO": "ℹ️",
                    "DEBUG": "🔧"
                }.get(log_level.upper(), "📝")
                
                print(f"[{time_str}] {level_icon} {log_message}")
            
            else:
                # Handle unknown event types
                timestamp = event_data.get("timestamp", "")
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        time_str = dt.strftime("%H:%M:%S")
                    except:
                        time_str = timestamp[:8] if len(timestamp) > 8 else timestamp
                else:
                    time_str = datetime.now().strftime("%H:%M:%S")
                
                print(f"[{time_str}] 📥 {event_type}: {event_data}")
        
        except websockets.exceptions.ConnectionClosed:
            print("\n🔌 WebSocket connection closed by server")
            break
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON: {e}")
            print(f"Raw message: {message}")
        except Exception as e:
            print(f"❌ Error receiving message: {e}")
            break

def show_help():
    """Show usage help"""
    print("""
🔌 Universal WebSocket Logger

Usage:
  python websocket_logger.py <task_id> --env <environment> [options]

Environments:
  --env local         Local development (ws://localhost:5001)
  --env appservice    Azure App Service deployment (wss://...)
  --env containerapp  Azure Container Apps deployment (requires auth)

Options:
  --identifier <id>   Container Apps session identifier 
                      (default: ea26c5e0-0286-4da0-8d6f-925c71bd822c)

Examples:
  python websocket_logger.py abc123-def456 --env local
  python websocket_logger.py abc123-def456 --env appservice  
  python websocket_logger.py abc123-def456 --env containerapp
  python websocket_logger.py abc123-def456 --env containerapp --identifier my-session

Environment Variable:
  DEPLOYMENT_ENV=<local|appservice|containerapp>

Features:
  ✅ Real-time log streaming
  ✅ Phase tracking (📋 planning → ⚡ generating → 🔧 fixing)
  ✅ Status updates (⚡ running → ✅ completed)
  ✅ Automatic authentication for Container Apps
  ✅ Colored output with timestamps
  ✅ Error handling and reconnection info

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
    
    # Check for help
    if sys.argv[1].lower() in ['help', '--help', '-h']:
        show_help()
        return
    
    task_id = sys.argv[1]
    
    # Get deployment configuration
    env, config = get_deployment_config()
    
    # Get authentication if needed
    bearer_token = None
    if config['auth_type'] == 'bearer':
        print("🔑 Getting bearer token for Container Apps...")
        bearer_token = get_bearer_token()
        if not bearer_token:
            print("❌ Could not obtain bearer token. Please run: az login")
            return
        print("✅ Bearer token obtained successfully")
    
    try:
        await stream_task_logs(task_id, env, config, bearer_token)
    except KeyboardInterrupt:
        print("\n⏹️ Disconnected by user (Ctrl+C)")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    # Check for websockets dependency
    try:
        import websockets
        asyncio.run(main())
    except ImportError:
        print("❌ websockets library not installed.")
        print("Install it with: pip install websockets")