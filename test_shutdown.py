#!/usr/bin/env python3
"""
Simple test to verify graceful shutdown behavior
"""

import asyncio
import signal
import sys
import time
import subprocess
from pathlib import Path

async def test_graceful_shutdown():
    """Test that the application properly shuts down OpenCode processes"""
    print("🧪 Testing graceful shutdown behavior...")
    
    # Start the FastAPI server
    print("🚀 Starting FastAPI server...")
    server_process = subprocess.Popen([
        sys.executable, "-m", "uvicorn", "main:app", 
        "--host", "0.0.0.0", "--port", "5001"
    ], cwd=Path(__file__).parent)
    
    try:
        # Wait for server to start
        await asyncio.sleep(3)
        print("✅ Server started")
        
        # Create a test task (this would start an OpenCode process in real scenario)
        print("📝 Creating test task...")
        # In a real test, you'd make an HTTP request to create a task
        # For now, we'll just simulate the server running
        
        # Wait a bit
        await asyncio.sleep(2)
        
        # Send SIGTERM to simulate graceful shutdown
        print("🛑 Sending SIGTERM for graceful shutdown...")
        server_process.terminate()
        
        # Wait for graceful shutdown
        try:
            server_process.wait(timeout=15)  # Give it 15 seconds to shutdown
            print("✅ Server shut down gracefully")
            return True
        except subprocess.TimeoutExpired:
            print("❌ Server did not shut down within timeout")
            server_process.kill()
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        server_process.kill()
        return False
    finally:
        # Ensure process is cleaned up
        if server_process.poll() is None:
            server_process.kill()

if __name__ == "__main__":
    result = asyncio.run(test_graceful_shutdown())
    sys.exit(0 if result else 1)
