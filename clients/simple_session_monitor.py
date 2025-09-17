#!/usr/bin/env python3
"""
Simple Session Monitor
Creates 5 tasks with hardcoded identifiers and monitors their status.
Saves clean JSON responses to files.
"""

import json
import os
import requests
import time
from datetime import datetime
from pathlib import Path
from shared_config import get_bearer_token, DEPLOYMENTS

# Hardcoded identifiers (used as both session_id and identifier)
IDENTIFIERS = [
    "test-pool-1",
    "test-pool-2", 
    "test-pool-3",
    "test-pool-4",
    "test-pool-5"
]

class SimpleSessionMonitor:
    def __init__(self):
        self.config = DEPLOYMENTS['containerapp']
        self.base_url = self.config['url']
        self.bearer_token = get_bearer_token() if self.config['auth_type'] == 'bearer' else None
        
        self.sessions = {}
        self.active_tasks = {}
        
        # Create results directory
        self.results_dir = Path("session_pool_results")
        self.results_dir.mkdir(exist_ok=True)
        
        print(f"🚀 Simple Session Monitor")
        print(f"   Base URL: {self.base_url}")
        print(f"   Sessions: {len(IDENTIFIERS)}")

    def get_headers(self):
        headers = {'Content-Type': 'application/json'}
        if self.bearer_token:
            headers['Authorization'] = f'Bearer {self.bearer_token}'
        return headers

    def create_sessions(self):
        print(f"\n📋 Creating {len(IDENTIFIERS)} sessions...")
        
        for i, identifier in enumerate(IDENTIFIERS):
            session_info = {
                'identifier': identifier,
                'session_id': identifier,
                'created_at': datetime.now().isoformat(),
                'results_file': str(self.results_dir / f"session_{i+1}_{identifier}.json")
            }
            
            self.sessions[identifier] = session_info
            print(f"   ✅ Session {i+1}: {identifier}")
        
        print(f"✅ Created {len(self.sessions)} sessions")

    def load_prd_content(self):
        try:
            prd_file = Path(__file__).parent / "prd.md"
            if prd_file.exists():
                with open(prd_file, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                return "PRD file not found - using minimal instructions"
        except Exception as e:
            return f"Error loading PRD: {e}"

    def create_task_for_session(self, identifier):
        session_info = self.sessions[identifier]
        prd_content = self.load_prd_content()
        
        payload = {
            "task_type": "complete",
            "configuration": {
                "app_url": "https://timeawayhrapp.z8.web.core.windows.net",
                "sign_in": {
                    "method": "none",
                    "username": None,
                    "password": None
                },
                "instructions": f"Create a test plan that covers up to 10 key tests for the web app. Only include tests for read-only data and do not test any workflows that update data, such as Request Time Off. Here is the PRD: {prd_content}"
            },
            "artifacts_url": {
                "sas_url": "https://testingagentstorage.blob.core.windows.net/artifacts?se=2025-09-19&sp=rwdlac&spr=https&sv=2022-11-02&ss=b&srt=co&sig=nunlYhIwWlxPMnC1fIEt5Fv3WxlDgZqcbZ8mllopBBE%3D"
            },
            "session_id": session_info['session_id']
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/tasks",
                headers=self.get_headers(),
                json=payload,
                params={'identifier': identifier},
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                task_data = response.json()
                task_id = task_data.get('id')
                
                if task_id:
                    # Store task info
                    task_info = {
                        'task_id': task_id,
                        'identifier': identifier,
                        'created_at': datetime.now().isoformat()
                    }
                    
                    self.active_tasks[task_id] = task_info
                    session_info['task_id'] = task_id
                    
                    print(f"   ✅ Created task {task_id[:8]}... for {identifier}")
                    return task_id
                    
        except Exception as e:
            print(f"   ❌ Exception for {identifier}: {e}")
        
        return None

    def create_all_tasks(self):
        print(f"\n🎯 Creating tasks for all sessions...")
        
        created_count = 0
        for identifier in self.sessions:
            if self.create_task_for_session(identifier):
                created_count += 1
            time.sleep(1)
        
        print(f"✅ Created {created_count} tasks")

    def check_task_status(self, task_id):
        task_info = self.active_tasks.get(task_id)
        if not task_info:
            return
        
        identifier = task_info['identifier']
        
        try:
            response = requests.get(
                f"{self.base_url}/tasks/{task_id}",
                headers=self.get_headers(),
                params={'identifier': identifier},
                timeout=30
            )
            
            print(f"   📊 {identifier}: Status {response.status_code}")
            
            # Store raw response for file saving
            task_info['raw_response'] = {
                'status_code': response.status_code,
                'response_text': response.text,
                'timestamp': datetime.now().isoformat()
            }
                
        except Exception as e:
            print(f"   ❌ Exception for {identifier}: {e}")
            task_info['raw_response'] = {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def save_session_results(self, identifier):
        session_info = self.sessions[identifier]
        results_file = session_info['results_file']
        
        # Initialize file structure if needed
        if not os.path.exists(results_file):
            initial_data = {
                "session_details": {
                    "identifier": identifier,
                    "session_id": session_info.get('session_id'),
                    "task_id": session_info.get('task_id'),
                    "created_at": session_info.get('created_at'),
                    "api_endpoint": f"{self.base_url}/tasks/{session_info.get('task_id')}",
                },
                "api_responses": []
            }
            with open(results_file, 'w') as f:
                json.dump(initial_data, f, indent=2, default=str)
        
        # Load existing data and add new response
        with open(results_file, 'r') as f:
            data = json.load(f)
        
        task_id = session_info.get('task_id')
        if task_id and task_id in self.active_tasks:
            task_info = self.active_tasks[task_id]
            if 'raw_response' in task_info:
                raw_response = task_info['raw_response']
                
                # Parse JSON response for readability
                try:
                    if 'response_text' in raw_response:
                        parsed_response = json.loads(raw_response['response_text'])
                        response_data = {
                            "status_code": raw_response['status_code'],
                            "response": parsed_response
                        }
                    else:
                        response_data = raw_response
                except (json.JSONDecodeError, KeyError):
                    response_data = raw_response
                
                # Add to responses array
                response_entry = {
                    "timestamp": raw_response.get('timestamp', datetime.now().isoformat()),
                    "response": response_data
                }
                data["api_responses"].append(response_entry)
        
        # Save updated data
        with open(results_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)

    def monitor_all_tasks(self):
        if not self.active_tasks:
            print("   ℹ️ No active tasks to monitor")
            return
        
        print(f"\n🔍 Polling {len(self.active_tasks)} active tasks...")
        print("=" * 50)
        
        for task_id, task_info in self.active_tasks.items():
            self.check_task_status(task_id)
            identifier = task_info['identifier']
            self.save_session_results(identifier)

    def run(self):
        print("🔄 Starting monitoring loop (Ctrl+C to stop)")
        
        try:
            while True:
                self.monitor_all_tasks()
                time.sleep(5)  # Poll every 5 seconds
                
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped")

def main():
    monitor = SimpleSessionMonitor()
    
    # Setup
    monitor.create_sessions()
    monitor.create_all_tasks()
    
    # Show summary
    print(f"\n📊 Active Tasks: {len(monitor.active_tasks)}")
    for task_id, info in monitor.active_tasks.items():
        print(f"   • {info['identifier']}: {task_id[:8]}...")
    
    # Start monitoring
    monitor.run()

if __name__ == '__main__':
    main()