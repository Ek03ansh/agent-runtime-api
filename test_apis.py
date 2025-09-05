#!/usr/bin/env python3
"""
Test script to check log and status APIs
This will help verify that our APIs are returning the detailed logs we see in the server
"""
import requests
import json
import time

def test_task_apis():
    """Test the task status and logs APIs"""
    base_url = 'http://localhost:5001'
    
    print("🔍 Testing Task APIs...")
    
    # First, get all tasks to find an existing one
    print("\n📋 Getting all tasks...")
    response = requests.get(f'{base_url}/tasks')
    if response.status_code == 200:
        tasks_data = response.json()
        tasks = tasks_data.get('tasks', [])
        print(f"Found {len(tasks)} tasks")
        
        if tasks:
            # Use the most recent task
            latest_task = tasks[-1]
            task_id = latest_task['id']
            print(f"Using latest task: {task_id}")
            print(f"Task status: {latest_task['status']}")
            print(f"Task type: {latest_task['task_type']}")
            
            # Test task status API
            print(f"\n📊 Getting detailed task status for {task_id}...")
            status_response = requests.get(f'{base_url}/tasks/{task_id}')
            if status_response.status_code == 200:
                task_details = status_response.json()
                print(f"✅ Task Status API working!")
                print(f"   ID: {task_details.get('id')}")
                print(f"   Status: {task_details.get('status')}")
                print(f"   Current Phase: {task_details.get('current_phase', 'N/A')}")
                print(f"   Session ID: {task_details.get('session_id', 'N/A')}")
                print(f"   Created: {task_details.get('created_at')}")
                print(f"   Updated: {task_details.get('updated_at')}")
                if task_details.get('error'):
                    print(f"   Error: {task_details.get('error')[:200]}...")
            else:
                print(f"❌ Task Status API failed: {status_response.status_code}")
                print(f"   Error: {status_response.text}")
            
            # Test task logs API
            print(f"\n📝 Getting detailed logs for {task_id}...")
            logs_response = requests.get(f'{base_url}/tasks/{task_id}/logs')
            if logs_response.status_code == 200:
                logs_data = logs_response.json()
                logs = logs_data.get('logs', [])
                print(f"✅ Task Logs API working!")
                print(f"   Total log entries: {logs_data.get('total_log_entries', 0)}")
                
                if logs:
                    print(f"\n📄 Log Details:")
                    for i, log in enumerate(logs):
                        print(f"   Log {i+1}:")
                        print(f"     Agent: {log.get('agent')}")
                        print(f"     Model: {log.get('model')}")
                        print(f"     Exit Code: {log.get('exit_code')}")
                        print(f"     Working Dir: {log.get('working_directory')}")
                        print(f"     Auth File: {log.get('auth_file')}")
                        
                        # Show command (truncated)
                        command = log.get('command', '')
                        if len(command) > 100:
                            command = command[:100] + "..."
                        print(f"     Command: {command}")
                        
                        # Show stdout/stderr preview
                        stdout = log.get('stdout', '')
                        stderr = log.get('stderr', '')
                        
                        if stdout:
                            stdout_preview = stdout[:200] + ("..." if len(stdout) > 200 else "")
                            print(f"     STDOUT Preview: {stdout_preview}")
                        
                        if stderr:
                            stderr_preview = stderr[:200] + ("..." if len(stderr) > 200 else "")
                            print(f"     STDERR Preview: {stderr_preview}")
                        
                        print(f"     Azure Resource: {log.get('azure_resource')}")
                        print(f"     Azure Endpoint: {log.get('azure_endpoint')}")
                        print()
                else:
                    print("   No logs available yet")
            else:
                print(f"❌ Task Logs API failed: {logs_response.status_code}")
                print(f"   Error: {logs_response.text}")
            
            # Test session files API
            print(f"\n📁 Getting session files for {task_id}...")
            files_response = requests.get(f'{base_url}/tasks/{task_id}/session/files')
            if files_response.status_code == 200:
                files = files_response.json()
                print(f"✅ Session Files API working!")
                print(f"   Found {len(files)} files in session")
                for file in files[:10]:  # Show first 10 files
                    print(f"     📄 {file.get('name')} ({file.get('size')} bytes)")
                    print(f"        Path: {file.get('path')}")
                    print(f"        Modified: {file.get('modified')}")
            else:
                print(f"❌ Session Files API failed: {files_response.status_code}")
        else:
            print("❌ No tasks found. Create a task first using create_google_task.py")
    else:
        print(f"❌ Failed to get tasks: {response.status_code}")
        print(f"   Error: {response.text}")
    
    # Test health API
    print(f"\n🏥 Testing Health API...")
    health_response = requests.get(f'{base_url}/health')
    if health_response.status_code == 200:
        health_data = health_response.json()
        print(f"✅ Health API working!")
        print(f"   Status: {health_data.get('status')}")
        print(f"   OpenCode Available: {health_data.get('opencode_available')}")
        print(f"   Version: {health_data.get('version')}")
        print(f"   Timestamp: {health_data.get('timestamp')}")
    else:
        print(f"❌ Health API failed: {health_response.status_code}")
    
    # Test config API
    print(f"\n⚙️ Testing Config API...")
    config_response = requests.get(f'{base_url}/config')
    if config_response.status_code == 200:
        config_data = config_response.json()
        print(f"✅ Config API working!")
        print(f"   Provider: {config_data.get('provider')}")
        print(f"   Model: {config_data.get('model')}")
        print(f"   Auth Type: {config_data.get('auth_type')}")
        print(f"   OpenCode Path: {config_data.get('opencode_path')}")
        print(f"   OpenCode Available: {config_data.get('opencode_available')}")
        print(f"   Environment: {config_data.get('environment')}")
        print(f"   Available Task Types: {config_data.get('available_task_types')}")
    else:
        print(f"❌ Config API failed: {config_response.status_code}")

if __name__ == "__main__":
    try:
        test_task_apis()
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server at http://localhost:5001")
        print("   Make sure the server is running with: python main.py")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
