#!/usr/bin/env python3
"""
Universal API Testing Client
Supports local, App Service, and Container Apps deployments with automatic authentication
Usage: python api_tester.py [command] [options] --env <local|appservice|containerapp>
"""
import requests
import json
import sys
import os
import subprocess
import time
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
    
    # Default to local with auto-detection
    print("🔍 No environment specified, trying auto-detection...")
    
    # Try local first
    try:
        response = requests.get(f"{DEPLOYMENTS['local']['url']}/health", timeout=3)
        if response.status_code == 200:
            print(f"✅ Detected local development server")
            return 'local', DEPLOYMENTS['local']
    except:
        pass
    
    # Ask user to specify
    print("❌ Could not auto-detect environment.")
    print("Please specify with --env <local|appservice|containerapp>")
    sys.exit(1)

def get_identifier():
    """Get identifier for Container Apps"""
    if '--identifier' in sys.argv:
        idx = sys.argv.index('--identifier')
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return "ea26c5e0-0286-4da0-8d6f-925c71bd822c"

def get_params_for_env(env):
    """Get query parameters needed for the environment"""
    if env == 'containerapp':
        return {"identifier": get_identifier()}
    return {}

def get_headers(config, bearer_token=None):
    """Get appropriate headers for the deployment type"""
    headers = {"Content-Type": "application/json"}
    
    if config['auth_type'] == 'bearer' and bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    
    return headers

def make_request(method, url, headers, **kwargs):
    """Make HTTP request with error handling"""
    try:
        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        return response
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection failed to {url}")
        return None
    except requests.exceptions.Timeout:
        print(f"❌ Request timed out to {url}")
        return None
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

def test_health(base_url, headers, env):
    """Test health endpoint"""
    print("🏥 Testing health endpoint...")
    
    params = get_params_for_env(env)
    response = make_request('GET', f"{base_url}/health", headers, params=params)
    
    if response is None:
        return False
    
    print(f"Status: {response.status_code}")
    try:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        return response.status_code == 200
    except:
        print(f"Response: {response.text[:200]}...")
        return response.status_code == 200

def test_tasks_list(base_url, headers, env):
    """Test tasks list endpoint"""
    print("📋 Testing tasks list endpoint...")
    
    params = get_params_for_env(env)
    response = make_request('GET', f"{base_url}/tasks", headers, params=params)
    
    if response is None:
        return False
    
    print(f"Status: {response.status_code}")
    try:
        data = response.json()
        if isinstance(data, list):
            print(f"Found {len(data)} tasks")
            if data:
                print("Recent tasks:")
                for task in data[:3]:
                    task_id = task.get('task_id', 'unknown')
                    status = task.get('status', 'unknown')
                    created = task.get('created_at', 'unknown')
                    print(f"  - {task_id} | {status} | {created}")
        else:
            print(f"Response: {json.dumps(data, indent=2)}")
        return response.status_code == 200
    except:
        print(f"Response: {response.text[:200]}...")
        return response.status_code == 200

def get_session_files(task_id, base_url, headers, env):
    """Get session files for a task"""
    print(f"📁 Getting session files for task {task_id}...")
    
    params = get_params_for_env(env)
    if env == 'containerapp':
        print(f"🆔 Using identifier: {get_identifier()}")
    
    # First get task info to get the session_path
    try:
        response = requests.get(f"{base_url}/tasks/{task_id}", headers=headers, params=params)
        print(f"Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Failed to get task info: {response.text}")
            return False
            
        task_data = response.json()
        session_path = task_data.get('session_path')
        session_id = task_data.get('session_id')
        
        if not session_path:
            print("❌ No session_path found in task data")
            return False
            
        print(f"📂 Session path: {session_path}")
        print(f"🆔 Session ID: {session_id}")
        
        # Try to get session files - this might be a different endpoint
        # Let's try a few possible endpoints
        possible_endpoints = [
            f"/tasks/{task_id}/files",
            f"/sessions/{session_id}/files", 
            f"/files/{session_path}",
            f"/session-files/{task_id}"
        ]
        
        for endpoint in possible_endpoints:
            try:
                print(f"🔍 Trying endpoint: {endpoint}")
                response = requests.get(f"{base_url}{endpoint}", headers=headers, params=params)
                print(f"   Status: {response.status_code}")
                
                if response.status_code == 200:
                    files_data = response.json()
                    print(f"✅ Session files found at {endpoint}:")
                    print(json.dumps(files_data, indent=2))
                    return True
                elif response.status_code == 404:
                    print(f"   ❌ Not found at {endpoint}")
                else:
                    print(f"   ⚠️ Error {response.status_code}: {response.text[:100]}...")
                    
            except Exception as e:
                print(f"   ❌ Error trying {endpoint}: {e}")
                
        print("❌ No session files endpoint found")
        print("💡 Available session info from task:")
        session_info = {
            'session_path': session_path,
            'session_id': session_id,
            'artifacts_url': task_data.get('artifacts_url'),
            'uploaded_artifacts': task_data.get('uploaded_artifacts')
        }
        print(json.dumps(session_info, indent=2))
        return False
        
    except Exception as e:
        print(f"❌ Error getting session files: {e}")
        return False

def get_task_info(task_id, base_url, headers, env, get_logs=True, get_status=True):
    """Get task information"""
    params = get_params_for_env(env)
    success = True
    
    if get_status:
        print(f"📊 Getting status for task {task_id}...")
        url = f"{base_url}/tasks/{task_id}"
        
        response = make_request('GET', url, headers, params=params)
        if response:
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                try:
                    data = response.json()
                    print("✅ Task status:")
                    print(json.dumps(data, indent=2))
                except:
                    print("✅ Raw response:")
                    print(response.text[:500])
            else:
                success = False
                print("❌ Failed to get status")
        else:
            success = False
    
    if get_logs:
        if get_status:
            print("\n" + "=" * 40)
        
        print(f"📋 Getting logs for task {task_id}...")
        url = f"{base_url}/tasks/{task_id}/logs"
        
        response = make_request('GET', url, headers, params=params)
        if response:
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                try:
                    data = response.json()
                    print("✅ Task logs:")
                    print(json.dumps(data, indent=2))
                except:
                    print("✅ Raw response:")
                    print(response.text[:500])
            else:
                success = False
                print("❌ Failed to get logs")
        else:
            success = False
    
    return success

def create_test_task(base_url, headers, env):
    """Create a test task with hardcoded defaults for simplicity"""
    # Hardcoded values for simplicity
    task_type = "complete"
    app_url = "https://demo.playwright.dev/todomvc/#/"
    instructions = "Create comprehensive test plan and generate tests"
    
    print(f"🧪 Creating {task_type} task...")
    print(f"🌐 Target URL: {app_url}")
    
    # Different payload structures for different environments
    if env == 'containerapp':
        # Container Apps format - always include identifier
        payload = {
            "task_type": "test-planning",  # Container apps uses different naming
            "url": app_url,
            "name": "Test ToDo MVC App",
            "identifier": get_identifier()
        }
    else:
        # App Service and Local format
        payload = {
            "task_type": task_type,
            "session_id": f"api-test-{int(time.time())}",
            "configuration": {
                "app_url": app_url,
                "instructions": instructions
            }
        }
    
    response = make_request('POST', f"{base_url}/tasks", headers, json=payload)
    
    if response is None:
        return None
    
    print(f"Status: {response.status_code}")
    
    if response.status_code in [200, 201]:
        try:
            task = response.json()
            print("✅ Task created successfully:")
            print(json.dumps(task, indent=2))
            return task.get('task_id')
        except:
            print("✅ Raw response:")
            print(response.text)
            return "task-created"
    else:
        print(f"❌ Failed to create task:")
        try:
            error = response.json()
            print(json.dumps(error, indent=2))
        except:
            print(response.text)
    
    return None

def run_all_tests(env, config, headers):
    """Run comprehensive API tests"""
    base_url = config['url']
    
    print(f"🧪 Running comprehensive API tests...")
    print(f"🌐 Environment: {env} ({config['description']})")
    print(f"🔗 URL: {base_url}")
    print("=" * 80)
    
    # Test health
    health_ok = test_health(base_url, headers, env)
    print()
    
    # Test tasks list
    tasks_ok = test_tasks_list(base_url, headers, env)
    print()
    
    # Create test task
    task_id = create_test_task(base_url, headers, env)
    
    results = {
        'health': health_ok,
        'tasks_list': tasks_ok,
        'task_creation': task_id is not None
    }
    
    print("\n" + "=" * 80)
    print("📊 Test Results Summary:")
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
    
    if task_id:
        print(f"\n🎉 Created task: {task_id}")
        print(f"Monitor it with: python websocket_logger.py {task_id} --env {env}")
    
    return results

def show_help():
    """Show usage help"""
    print("""
🎯 Universal API Testing Client

Usage:
  python api_tester.py [command] [options] --env <environment>

Environments:
  --env local         Local development (http://localhost:5001)
  --env appservice    Azure App Service deployment  
  --env containerapp  Azure Container Apps deployment (requires auth)

Commands:
  test               Run comprehensive API tests
  status <task_id>   Get task status only
  logs <task_id>     Get task logs only  
  info <task_id>     Get both status and logs
  files <task_id>    Get session files for a task
  create             Create a test task (hardcoded: complete task, TodoMVC app)
  help               Show this help

Container Apps Options:
  --identifier <id>  Session identifier (default: ea26c5e0-0286-4da0-8d6f-925c71bd822c)

Examples:
  python api_tester.py test --env local
  python api_tester.py test --env appservice
  python api_tester.py test --env containerapp
  python api_tester.py info abc123-def456 --env containerapp
  python api_tester.py files abc123-def456 --env containerapp
  python api_tester.py create --env local
  python api_tester.py status abc123-def456 --env appservice

Environment Variable:
  DEPLOYMENT_ENV=<local|appservice|containerapp>

Hardcoded Defaults:
  Task Type: complete (full pipeline)
  Target URL: https://demo.playwright.dev/todomvc/#/
  Instructions: Create comprehensive test plan and generate tests
""")

def main():
    if len(sys.argv) > 1 and sys.argv[1].lower() in ['help', '--help', '-h']:
        show_help()
        return
    
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
        print("✅ Bearer token obtained")
    
    headers = get_headers(config, bearer_token)
    base_url = config['url']
    
    print(f"🌐 Using {env.upper()} environment")
    print(f"📍 {config['description']}: {base_url}")
    if env == 'containerapp':
        print(f"🆔 Identifier: {get_identifier()}")
    print()
    
    # Parse command
    if len(sys.argv) < 2 or '--env' in sys.argv and len([arg for arg in sys.argv if not arg.startswith('--') and arg != sys.argv[0]]) < 1:
        # Default: run all tests
        run_all_tests(env, config, headers)
        return
    
    # Find the actual command (not --env or its value)
    command_args = [arg for arg in sys.argv[1:] if not arg.startswith('--') and arg not in DEPLOYMENTS.keys()]
    if not command_args:
        run_all_tests(env, config, headers)
        return
    
    command = command_args[0].lower()
    
    if command == 'test':
        run_all_tests(env, config, headers)
    elif command == 'create':
        task_id = create_test_task(base_url, headers, env)
        if task_id:
            print(f"🎉 Task created: {task_id}")
    elif command in ['status', 'logs', 'info', 'files']:
        if len(command_args) < 2:
            print(f"❌ Task ID required for {command} command")
            return
        
        task_id = command_args[1]
        
        if command == 'files':
            get_session_files(task_id, base_url, headers, env)
        else:
            get_status = command in ['status', 'info']
            get_logs = command in ['logs', 'info'] 
            get_task_info(task_id, base_url, headers, env, get_logs, get_status)
    else:
        print(f"❌ Unknown command: {command}")
        show_help()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted by user (Ctrl+C)")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")