#!/usr/bin/env python3
"""API Tester - Just invoke different APIs"""

import sys
import time
import requests
from shared_config import *

def main():
    # Get configuration
    env, config = get_environment()
    bearer_token = None
    
    if config['auth_type'] == 'bearer':
        bearer_token = get_bearer_token()
        if not bearer_token:
            print("❌ Failed to get bearer token")
            return
    
    headers = get_headers(config, bearer_token)
    params = get_params(env)
    base_url = config['url']
    
    # Parse command
    command = sys.argv[1] if len(sys.argv) > 1 else 'help'
    
    if command == 'help':
        print("""
API Tester
Usage: python api_tester.py <command> [args...] --env <environment> [options]

Environments:
  --env local         Local development (http://localhost:5001)
  --env appservice    Azure App Service (no auth required)
  --env containerapp  Azure Container Apps (requires --identifier and bearer token)

Options:
  --identifier <id>   Container Apps session identifier (REQUIRED for containerapp)

Commands:
  health                     - Test health endpoint
  tasks                      - List all tasks
  create                     - Create a test task
  status <task_id>           - Get task status
  logs <task_id>             - Get task logs
  cancel <task_id>           - Cancel task
  sessions                   - List all sessions
  files <session_id>         - List files in session
  download <session_id>      - Download session ZIP
  file <session_id> <path>   - Download specific file
  plan <session_id>          - Download test plan
  cleanup                    - Delete all data
  auth                       - Check auth status
  auth-login                 - Start GitHub Copilot auth flow
  auth-inject <token>        - Inject GitHub Copilot refresh token

Examples:
  python api_tester.py health --env local
  python api_tester.py tasks --env appservice
  python api_tester.py create --env containerapp --identifier <session-id>
  python api_tester.py status abc123 --env local
  python api_tester.py download session-xyz --env appservice
  python api_tester.py plan session-xyz --env containerapp --identifier <session-id>
        """)
        return
    
    # Execute commands
    try:
        if command == 'health':
            response = requests.get(f"{base_url}/health", headers=headers, params=params)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
        
        elif command == 'tasks':
            response = requests.get(f"{base_url}/tasks", headers=headers, params=params)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
        
        elif command == 'create':
            # Complete payload with ALL fields (required + optional) - matches TaskRequest model
            payload = {
                # Required fields
                "task_type": "complete",  # Options: complete, plan, generate, fix, custom
                "configuration": {
                    "app_url": "https://demo.playwright.dev/todomvc/#/",
                    "sign_in": {
                        "method": "none",  # Options: none, username-password
                        "username": None,
                        "password": None
                    },
                    "instructions": ""
                },
                "session_id": f"api-test-{int(time.time())}",
                
                # Optional field - Real SAS URL for all environments
                "artifacts_url": {
                    "sas_url": "https://testingagentstorage.blob.core.windows.net/artifacts?se=2025-09-19&sp=rwdlac&spr=https&sv=2022-11-02&ss=b&srt=co&sig=nunlYhIwWlxPMnC1fIEt5Fv3WxlDgZqcbZ8mllopBBE%3D"
                }
            }
            response = requests.post(f"{base_url}/tasks", headers=headers, json=payload, params=params)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
        
        elif command == 'status':
            task_id = sys.argv[2] if len(sys.argv) > 2 else None
            if not task_id:
                print("❌ Need task_id")
                return
            response = requests.get(f"{base_url}/tasks/{task_id}", headers=headers, params=params)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
        
        elif command == 'logs':
            task_id = sys.argv[2] if len(sys.argv) > 2 else None
            if not task_id:
                print("❌ Need task_id")
                return
            response = requests.get(f"{base_url}/tasks/{task_id}/logs", headers=headers, params=params)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
        
        elif command == 'cancel':
            task_id = sys.argv[2] if len(sys.argv) > 2 else None
            if not task_id:
                print("❌ Need task_id")
                return
            response = requests.post(f"{base_url}/tasks/{task_id}/cancel", headers=headers, params=params)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
        
        elif command == 'sessions':
            response = requests.get(f"{base_url}/sessions", headers=headers, params=params)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
        
        elif command == 'files':
            session_id = sys.argv[2] if len(sys.argv) > 2 else None
            if not session_id:
                print("❌ Need session_id")
                return
            response = requests.get(f"{base_url}/sessions/{session_id}/files", headers=headers, params=params)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
        
        elif command == 'download':
            session_id = sys.argv[2] if len(sys.argv) > 2 else None
            if not session_id:
                print("❌ Need session_id")
                return
            response = requests.get(f"{base_url}/sessions/{session_id}/download", headers=headers, params=params)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                filename = f"{session_id}.zip"
                with open(filename, 'wb') as f:
                    f.write(response.content)
                print(f"Saved: {filename}")
            else:
                print(f"Response: {response.text}")
        
        elif command == 'file':
            session_id = sys.argv[2] if len(sys.argv) > 2 else None
            file_path = sys.argv[3] if len(sys.argv) > 3 else None
            if not session_id or not file_path:
                print("❌ Need session_id and file_path")
                return
            response = requests.get(f"{base_url}/sessions/{session_id}/files/{file_path}", headers=headers, params=params)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                filename = file_path.split('/')[-1]
                with open(filename, 'wb') as f:
                    f.write(response.content)
                print(f"Saved: {filename}")
            else:
                print(f"Response: {response.text}")
        
        elif command == 'plan':
            session_id = sys.argv[2] if len(sys.argv) > 2 else None
            if not session_id:
                print("❌ Need session_id")
                return
            response = requests.get(f"{base_url}/sessions/{session_id}/files/specs/test-plan.md", headers=headers, params=params)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                filename = f"{session_id}_test-plan.md"
                with open(filename, 'wb') as f:
                    f.write(response.content)
                print(f"Saved: {filename}")
            else:
                print(f"Response: {response.text}")
        
        elif command == 'cleanup':
            response = requests.delete(f"{base_url}/cleanup/all", headers=headers, params=params)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
        
        elif command == 'auth':
            response = requests.get(f"{base_url}/auth/status", headers=headers, params=params)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
        
        elif command == 'auth-login':
            response = requests.post(f"{base_url}/auth/login", headers=headers, params=params)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
        
        elif command == 'auth-inject':
            token = sys.argv[2] if len(sys.argv) > 2 else None
            if not token:
                print("❌ Need refresh token")
                return
            payload = {"refreshToken": token}
            response = requests.post(f"{base_url}/auth", headers=headers, json=payload, params=params)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
        
        else:
            print(f"❌ Unknown command: {command}")
            print("Run 'python api_tester.py help' for usage")
    
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()