#!/usr/bin/env python3
"""
Comprehensive Agent Runtime API Testing Tool
Supports task creation, monitoring, and API testing
"""
import requests
import json
import time
import sys
from datetime import datetime

def test_all_apis():
    """Test all available API endpoints"""
    base_url = 'http://localhost:5001'
    
    print("🔍 Testing All API Endpoints...")
    print("=" * 50)
    
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
    
    # Test config API
    print(f"\n⚙️ Testing Config API...")
    try:
        config_response = requests.get(f'{base_url}/config', timeout=5)
        if config_response.status_code == 200:
            config_data = config_response.json()
            print(f"✅ Config API working!")
            print(f"   Provider: {config_data.get('provider')}")
            print(f"   Model: {config_data.get('model')}")
            print(f"   Auth Type: {config_data.get('auth_type')}")
            print(f"   OpenCode Path: {config_data.get('opencode_path')}")
            print(f"   Available Task Types: {config_data.get('available_task_types')}")
        else:
            print(f"❌ Config API failed: {config_response.status_code}")
    except Exception as e:
        print(f"❌ Config API error: {e}")
    
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
                print(f"   ws://localhost:5001/tasks/{task_id}/stream")
                print(f"   Use: python websocket_client.py {task_id}")
            else:
                print("   No tasks found - create one to test individual task APIs")
        else:
            print(f"❌ Tasks API failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Tasks API error: {e}")
    
    print(f"\n" + "=" * 50)
    print("🎯 API Testing Complete!")
    return True

def create_task(task_type='complete', session_id=None, app_url=None):
    """Create a task with flexible options"""
    
    # Default session ID with timestamp if not provided
    if not session_id:
        timestamp = datetime.now().strftime("%H%M%S")
        session_id = f'test-{timestamp}'
    
    # Default URL if not provided
    if not app_url:
        app_url = 'https://demo.playwright.dev/todomvc/#/'
    
    url = 'http://localhost:5001/tasks'
    data = {
        'task_type': task_type,
        'session_id': session_id,
        'configuration': {
            'app_url': app_url,
            'azure_openai': {
                'endpoint': 'https://apitesting.openai.azure.com.openai.azure.com/',
                'api_key': '474bd8c287164f39b8f4f5ead57e34ae',
                'model_name': 'gpt-4.1',
                'deployment_name': 'gpt-4.1',
                'api_version': '2024-10-21'
            }
        }
    }
    
    print(f'� Creating {task_type} task...')
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
                print('\n� Full pipeline will execute:')
                print('1. 📝 Agent 1 (playwright-test-planner): Create test plan')
                print('2. ⚡ Agent 2 (playwright-test-generator): Generate test files')
                print('3. 🔧 Agent 3 (playwright-test-fixer): Debug and fix tests')
            elif task_type == 'plan':
                print('\n� Planning phase will execute:')
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
    print(f'\n👀 Monitoring task {task_id}...')
    print('Choose monitoring method:')
    print('1. Polling (HTTP requests every 3 seconds)')
    print('2. WebSocket streaming (real-time)')
    
    choice = input('Enter choice (1-2) [2]: ').strip() or "2"
    
    if choice == "2":
        print('\n🔌 Starting WebSocket streaming...')
        print(f'Run this command in another terminal for real-time logs:')
        print(f'python websocket_client.py {task_id}')
        print('\nFalling back to polling for status updates...')
    
    print('Press Ctrl+C to stop monitoring\n')
    
    last_status = None
    last_phase = None
    
    try:
        while True:
            try:
                response = requests.get(f'http://localhost:5001/tasks/{task_id}', timeout=10)
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
    try:
        response = requests.get(f'http://localhost:5001/tasks/{task_id}/logs', timeout=10)
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
🎯 Agent Runtime API Task Creator

Usage:
  python create_google_task.py [task_type] [session_id] [url]

Task Types:
  complete  - Full pipeline (plan → generate → fix)
  plan      - Create test plan only
  generate  - Generate tests only  
  fix       - Fix existing tests only

Examples:
  python create_google_task.py
  python create_google_task.py complete
  python create_google_task.py plan mysession
  python create_google_task.py generate mysession https://example.com

Interactive mode: python create_google_task.py interactive
""")

def interactive_mode():
    """Interactive task creation"""
    print("🎯 Interactive Task Creator")
    print("=" * 40)
    
    # Choose task type
    print("\n📋 Select task type:")
    print("1. complete - Full pipeline (plan → generate → fix)")
    print("2. plan - Create test plan only")
    print("3. generate - Generate tests only")
    print("4. fix - Fix existing tests only")
    
    choice = input("\nEnter choice (1-4) [1]: ").strip() or "1"
    task_types = {"1": "complete", "2": "plan", "3": "generate", "4": "fix"}
    task_type = task_types.get(choice, "complete")
    
    # Get session ID
    session_id = input(f"\n🆔 Enter session ID [auto-generated]: ").strip()
    
    # Get URL
    default_url = "https://demo.playwright.dev/todomvc/#/"
    app_url = input(f"\n🌐 Enter target URL [{default_url}]: ").strip() or default_url
    
    # Create task
    task_id = create_task(task_type, session_id, app_url)
    
    if task_id:
        monitor_choice = input("\n👀 Monitor task progress? (y/N): ").strip().lower()
        if monitor_choice in ['y', 'yes']:
            monitor_task(task_id)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == 'help' or sys.argv[1] == '--help':
            show_help()
        elif sys.argv[1] == 'interactive':
            interactive_mode()
        else:
            # Parse command line arguments
            task_type = sys.argv[1] if len(sys.argv) > 1 else 'complete'
            session_id = sys.argv[2] if len(sys.argv) > 2 else None
            app_url = sys.argv[3] if len(sys.argv) > 3 else None
            
            task_id = create_task(task_type, session_id, app_url)
            
            if task_id:
                print(f'\n🔍 Quick Status Check:')
                print(f'📊 GET http://localhost:5001/tasks/{task_id}')
                print(f'📄 GET http://localhost:5001/tasks/{task_id}/logs')
                
                monitor_choice = input("\n� Monitor task progress? (y/N): ").strip().lower()
                if monitor_choice in ['y', 'yes']:
                    monitor_task(task_id)
    else:
        # Default behavior - create complete task
        task_id = create_task()
        if task_id:
            monitor_task(task_id)


def enhanced_interactive_mode():
    """Enhanced interactive mode with API testing"""
    print("🎯 Interactive Mode")
    print("=" * 40)
    
    print("\n📋 What would you like to do?")
    print("1. Test all API endpoints")
    print("2. Create and monitor a task")
    print("3. Monitor existing task")
    print("4. View logs for existing task")
    
    choice = input("\nEnter choice (1-4) [2]: ").strip() or "2"
    
    if choice == "1":
        test_all_apis()
    elif choice == "2":
        interactive_mode()  # Use existing interactive mode
    elif choice == "3":
        task_id = input("\n🆔 Enter task ID to monitor: ").strip()
        if task_id:
            monitor_task(task_id)
    elif choice == "4":
        task_id = input("\n🆔 Enter task ID for logs: ").strip()
        if task_id:
            get_logs(task_id)
