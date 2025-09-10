#!/usr/bin/env python3
"""
Comprehensive Agent Runtime API Testing Tool
Supports task creation, monitoring, and API testing for both local and deployed endpoints
"""
import requests
import json
import time
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
    
    # Auto-detect: try local first, then deployed
    local_url = ENDPOINTS['local']
    deployed_url = ENDPOINTS['deployed']
    
    try:
        response = requests.get(f'{local_url}/health', timeout=3)
        if response.status_code == 200:
            print(f"🏠 Using LOCAL endpoint: {local_url}")
            return local_url
    except:
        pass
    
    print(f"☁️ Using DEPLOYED endpoint: {deployed_url}")
    return deployed_url

def show_endpoint_info():
    """Show current endpoint information"""
    base_url = get_base_url()
    print(f"🌐 Current endpoint: {base_url}")
    
    # Test connectivity
    try:
        response = requests.get(f'{base_url}/health', timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ Endpoint is accessible")
            print(f"   Status: {health_data.get('status', 'Unknown')}")
            print(f"   Version: {health_data.get('version', 'Unknown')}")
        else:
            print(f"⚠️ Endpoint returned status: {response.status_code}")
    except Exception as e:
        print(f"❌ Endpoint not accessible: {str(e)}")
    print()

def test_all_apis():
    """Test all available API endpoints"""
    base_url = get_base_url()
    
    print("🔍 Testing All API Endpoints...")
    print("=" * 50)
    print(f"🌐 Using endpoint: {base_url}")
    print()
    
    # Test health API
    print(f"\n🏥 Testing Health API...")
    try:
        health_response = requests.get(f'{base_url}/health', timeout=5)
        if health_response.status_code == 200:
            health_data = health_response.json()
            print(f"✅ Health API working!")
            print(f"   Status: {health_data.get('status')}")
            print(f"   OpenCode Available: {health_data.get('opencode_available')}")
            print(f"   Version: {health_data.get('version')}")
            print(f"   Timestamp: {health_data.get('timestamp')}")
        else:
            print(f"❌ Health API failed: {health_response.status_code}")
    except Exception as e:
        print(f"❌ Health API error: {e}")
    
    # Test tasks list API
    print(f"\n📋 Testing Tasks List API...")
    try:
        response = requests.get(f'{base_url}/tasks', timeout=5)
        if response.status_code == 200:
            tasks_data = response.json()
            tasks = tasks_data.get('tasks', [])
            print(f"✅ Tasks API working!")
            print(f"   Total tasks: {len(tasks)}")
            
            if tasks:
                latest_task = tasks[-1]
                task_id = latest_task['id']
                print(f"   Latest task: {task_id}")
                print(f"   Status: {latest_task['status']}")
                print(f"   Type: {latest_task['task_type']}")
                
                # Test individual task API
                print(f"\n📊 Testing Task Details API...")
                status_response = requests.get(f'{base_url}/tasks/{task_id}', timeout=5)
                if status_response.status_code == 200:
                    task_details = status_response.json()
                    print(f"✅ Task Details API working!")
                    print(f"   Current Phase: {task_details.get('current_phase', 'N/A')}")
                    print(f"   Session ID: {task_details.get('session_id', 'N/A')}")
                else:
                    print(f"❌ Task Details API failed: {status_response.status_code}")
                
                # Test task logs API
                print(f"\n📝 Testing Task Logs API...")
                logs_response = requests.get(f'{base_url}/tasks/{task_id}/logs', timeout=5)
                if logs_response.status_code == 200:
                    logs_data = logs_response.json()
                    logs = logs_data.get('logs', [])
                    debug_logs = logs_data.get('debug_logs', [])
                    print(f"✅ Task Logs API working!")
                    print(f"   Structured logs: {len(logs)} entries")
                    print(f"   Debug messages: {len(debug_logs)} entries")
                else:
                    print(f"❌ Task Logs API failed: {logs_response.status_code}")
                
                # Test WebSocket endpoint (connection test only)
                print(f"\n🔌 WebSocket Stream Available at:")
                websocket_url = base_url.replace('http://', 'ws://').replace('https://', 'wss://')
                print(f"   {websocket_url}/tasks/{task_id}/stream")
                print(f"   Use: python websocket_client.py {task_id} --endpoint {base_url}")
            else:
                print("   No tasks found - create one to test individual task APIs")
        else:
            print(f"❌ Tasks API failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Tasks API error: {e}")
    
    print(f"\n" + "=" * 50)
    print("🎯 API Testing Complete!")
    return True

def create_task(task_type='complete', session_id=None, app_url=None, instructions=''):
    """Create a task with flexible options"""
    base_url = get_base_url()
    
    # Default session ID with timestamp if not provided
    if not session_id:
        timestamp = datetime.now().strftime("%H%M%S")
        session_id = f'test-{timestamp}'
    
    # Default URL if not provided
    if not app_url:
        app_url = 'https://demo.playwright.dev/todomvc/#/'
    
    url = f'{base_url}/tasks'
    data = {
        'task_type': task_type,
        'session_id': session_id,
        'configuration': {
            'app_url': app_url,
            'instructions': instructions
        }
    }
    
    print(f'🚀 Creating {task_type} task...')
    print(f'📋 Session ID: {session_id}')
    print(f'🌐 Target URL: {app_url}')
    print(f'⏰ Timestamp: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    
    try:
        response = requests.post(url, json=data, timeout=30)
        print(f'\n📡 Response Status: {response.status_code}')
        
        if response.status_code == 201:
            result = response.json()
            task_id = result.get("task_id")
            print(f'✅ Task Created Successfully!')
            print(f'🆔 Task ID: {task_id}')
            print(f'📊 Status: {result.get("status")}')
            
            # Show what will execute based on task type
            if task_type == 'complete':
                print('\n🔄 Full pipeline will execute:')
                print('1. 📝 Agent 1 (playwright-test-planner): Create test plan')
                print('2. ⚡ Agent 2 (playwright-test-generator): Generate test files')
                print('3. 🔧 Agent 3 (playwright-test-fixer): Debug and fix tests')
            elif task_type == 'plan':
                print('\n📋 Planning phase will execute:')
                print('1. 📋 Agent (playwright-test-planner): Create comprehensive test plan')
            elif task_type == 'generate':
                print('\n⚡ Generation phase will execute:')
                print('1. 🏗️ Agent (playwright-test-generator): Generate test files')
            elif task_type == 'fix':
                print('\n🔧 Fixing phase will execute:')
                print('1. 🛠️ Agent (playwright-test-fixer): Debug and fix tests')
            
            return task_id
        else:
            print(f'❌ Task Creation Failed!')
            print(f'Error: {response.text}')
            return None
            
    except Exception as e:
        print(f'❌ Task Creation Failed with exception!')
        print(f'Error: {str(e)}')
        return None

def monitor_task(task_id):
    """Monitor task progress with real-time updates"""
    base_url = get_base_url()
    
    print(f'\n👀 Monitoring task {task_id}...')
    print(f'🌐 Using endpoint: {base_url}')
    print('Choose monitoring method:')
    print('1. Polling (HTTP requests every 3 seconds)')
    print('2. WebSocket streaming (real-time)')
    
    choice = input('Enter choice (1-2) [2]: ').strip() or "2"
    
    if choice == "2":
        print('\n🔌 Starting WebSocket streaming...')
        websocket_url = base_url.replace('http://', 'ws://').replace('https://', 'wss://')
        print(f'WebSocket URL: {websocket_url}/tasks/{task_id}/stream')
        print(f'Run this command in another terminal for real-time logs:')
        print(f'python websocket_client.py {task_id} --endpoint {base_url}')
        print('\nFalling back to polling for status updates...')
    
    print('Press Ctrl+C to stop monitoring\n')
    
    last_status = None
    last_phase = None
    
    try:
        while True:
            try:
                response = requests.get(f'{base_url}/tasks/{task_id}', timeout=10)
                if response.status_code == 200:
                    task = response.json()
                    status = task.get('status')
                    phase = task.get('current_phase')
                    
                    # Only print if status or phase changed
                    if status != last_status or phase != last_phase:
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        print(f'[{timestamp}] Status: {status.upper()}', end='')
                        if phase:
                            print(f' | Phase: {phase}')
                        else:
                            print()
                        
                        last_status = status
                        last_phase = phase
                    
                    # Stop monitoring if task is complete
                    if status in ['completed', 'failed', 'cancelled']:
                        print(f'\n🏁 Task finished with status: {status.upper()}')
                        if status == 'failed' and task.get('error'):
                            print(f'❌ Error: {task.get("error")}')
                        elif status == 'completed':
                            print('✅ Task completed successfully!')
                        break
                
                time.sleep(3)  # Check every 3 seconds
                
            except requests.RequestException as e:
                print(f'⚠️ Error checking status: {e}')
                time.sleep(5)
                
    except KeyboardInterrupt:
        print('\n⏹️ Monitoring stopped by user')

def get_logs(task_id):
    """Get detailed logs for a task"""
    base_url = get_base_url()
    
    try:
        response = requests.get(f'{base_url}/tasks/{task_id}/logs', timeout=10)
        if response.status_code == 200:
            logs_data = response.json()
            logs = logs_data.get('logs', [])
            debug_logs = logs_data.get('debug_logs', [])
            
            print(f'\n📄 Task Logs:')
            print(f'📋 Structured Logs: {len(logs)} entries')
            print(f'🔧 Debug Messages: {len(debug_logs)} entries')
            print('=' * 80)
            
            # Show debug logs first (real-time execution flow)
            if debug_logs:
                print('\n🔧 Real-time Debug Messages:')
                print('-' * 40)
                for i, debug_msg in enumerate(debug_logs, 1):
                    print(f'{i:3d}. {debug_msg}')
                print('-' * 40)
            
            # Show structured logs (agent execution summaries)
            if logs:
                print(f'\n📋 Agent Execution Logs:')
                print('-' * 40)
                for i, log in enumerate(logs, 1):
                    print(f'\n📋 Log Entry #{i}:')
                    print(f'  🤖 Agent: {log.get("agent")}')
                    print(f'  🎯 Model: {log.get("model")}')
                    print(f'  💻 Exit Code: {log.get("exit_code")}')
                    print(f'  📁 Working Dir: {log.get("working_directory")}')
                    
                    stdout = log.get("stdout", "").strip()
                    stderr = log.get("stderr", "").strip()
                    
                    if stdout:
                        print(f'  📤 STDOUT: {stdout[:200]}...' if len(stdout) > 200 else f'  📤 STDOUT: {stdout}')
                    if stderr:
                        print(f'  📤 STDERR: {stderr[:200]}...' if len(stderr) > 200 else f'  📤 STDERR: {stderr}')
                    
                    print('-' * 40)
        else:
            print(f'❌ Failed to get logs: {response.status_code} - {response.text}')
    except Exception as e:
        print(f'❌ Error getting logs: {e}')

def show_help():
    """Show usage help"""
    print("""
🎯 Agent Runtime API Testing Tool

Usage:
  python test_agent_api.py [command] [options] [--endpoint <url>]

Commands:
  test          - Test all API endpoints
  create [type] - Create task (complete, plan, generate, fix)
  monitor [id]  - Monitor task progress
  logs [id]     - Get task logs
  interactive   - Interactive mode
  help          - Show this help

Endpoint Options:
  --endpoint local     - Use http://localhost:5001
  --endpoint deployed  - Use https://agent-runtime-pw-app.azurewebsites.net
  --endpoint <url>     - Use custom URL

Environment Variable:
  AGENT_API_URL=<url>  - Set default endpoint

Auto-detection:
  If no endpoint specified, tries local first, then deployed

Task Types:
  complete  - Full pipeline (plan → generate → fix)
  plan      - Create test plan only
  generate  - Generate tests only  
  fix       - Fix existing tests only

Examples:
  python test_agent_api.py test
  python test_agent_api.py create complete --endpoint deployed
  python test_agent_api.py monitor abc123-def456 --endpoint local
  python test_agent_api.py interactive --endpoint deployed
  
  # Using environment variable
  set AGENT_API_URL=https://agent-runtime-pw-app.azurewebsites.net
  python test_agent_api.py test
""")

def interactive_mode():
    """Interactive task creation"""
    base_url = get_base_url()
    
    print("🎯 Interactive Task Creator")
    print("=" * 40)
    print(f"🌐 Using endpoint: {base_url}")
    
    # Choose task type
    print("\n📋 Select task type:")
    print("1. complete - Full pipeline (plan → generate → fix)")
    print("2. plan - Create test plan only")
    print("3. generate - Generate tests only")
    print("4. fix - Fix existing tests only")
    print("5. custom - Direct user instructions (iterative)")
    
    choice = input("\nEnter choice (1-5) [1]: ").strip() or "1"
    task_types = {"1": "complete", "2": "plan", "3": "generate", "4": "fix", "5": "custom"}
    task_type = task_types.get(choice, "complete")
    
    # Get session ID
    session_id = input(f"\n🆔 Enter session ID [auto-generated]: ").strip()
    
    # Get URL
    default_url = "https://demo.playwright.dev/todomvc/#/"
    app_url = input(f"\n🌐 Enter target URL [{default_url}]: ").strip() or default_url
    
    # Get custom instructions for custom task type
    instructions = ""
    if task_type == "custom":
        print(f"\n📝 Custom task type selected - provide direct instructions:")
        instructions = input("Instructions: ").strip()
        if not instructions:
            print("❌ Custom task type requires instructions!")
            return
    
    # Create task
    task_id = create_task(task_type, session_id, app_url, instructions)
    
    if task_id:
        monitor_choice = input("\n👀 Monitor task progress? (y/N): ").strip().lower()
        if monitor_choice in ['y', 'yes']:
            monitor_task(task_id)


def enhanced_interactive_mode():
    """Enhanced interactive mode with API testing"""
    print("🎯 Interactive Mode")
    print("=" * 40)
    
    options = {
        "1": ("Test all API endpoints", test_all_apis),
        "2": ("Create and monitor a task", interactive_mode),
        "3": ("Monitor existing task", lambda: monitor_task(input("\n🆔 Enter task ID to monitor: ").strip())),
        "4": ("View logs for existing task", lambda: get_logs(input("\n🆔 Enter task ID for logs: ").strip()))
    }
    
    print("\n📋 What would you like to do?")
    for key, (description, _) in options.items():
        print(f"{key}. {description}")
    
    choice = input("\nEnter choice (1-4) [2]: ").strip() or "2"
    
    if choice in options:
        _, action = options[choice]
        action()
    else:
        print("❌ Invalid choice")


if __name__ == "__main__":
    # Show endpoint info for all commands except help
    if len(sys.argv) == 1 or (len(sys.argv) > 1 and sys.argv[1].lower() not in ['help', '--help', '-h']):
        show_endpoint_info()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        # Dictionary-based command mapping for cleaner logic
        command_map = {
            'help': show_help,
            '--help': show_help,
            '-h': show_help,
            'test': test_all_apis,
            'interactive': enhanced_interactive_mode
        }
        
        if command in command_map:
            command_map[command]()
        elif command == 'create':
            task_type = sys.argv[2] if len(sys.argv) > 2 else 'complete'
            session_id = sys.argv[3] if len(sys.argv) > 3 else None
            app_url = sys.argv[4] if len(sys.argv) > 4 else None
            
            task_id = create_task(task_type, session_id, app_url)
            if task_id:
                print(f'\n🔍 Quick Status Check:')
                print(f'📊 GET {base_url}/tasks/{task_id}')
                print(f'📄 GET {base_url}/tasks/{task_id}/logs')
                
                monitor_choice = input("\n👀 Monitor task progress? (y/N): ").strip().lower()
                if monitor_choice in ['y', 'yes']:
                    monitor_task(task_id)
        elif command in ['monitor', 'logs']:
            if len(sys.argv) < 3:
                print(f"❌ Task ID required for {command}")
                print(f"Usage: python test_agent_api.py {command} <task_id>")
            else:
                task_id = sys.argv[2]
                if command == 'monitor':
                    monitor_task(task_id)
                else:
                    get_logs(task_id)
        else:
            print(f"❌ Unknown command: {command}")
            show_help()
    else:
        # Default behavior - create complete task
        show_endpoint_info()
        task_id = create_task()
        if task_id:
            monitor_task(task_id)
