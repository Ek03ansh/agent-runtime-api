#!/usr/bin/env python3
"""Shared configuration for API and WebSocket clients"""
import subprocess
import json
import sys
import os

DEPLOYMENTS = {
    'local': {
        'url': 'http://localhost:5001',
        'auth_type': 'none'
    },
    'appservice': {
        'url': 'https://agent-runtime-pw-app.azurewebsites.net',
        'auth_type': 'none'
    },
    'containerapp': {
        'url': 'https://playwrightmcp-sessionpool.kindplant-1df81c5d.eastus.azurecontainerapps.io',
        'auth_type': 'bearer'
    }
}

def get_bearer_token():
    """Get bearer token from Azure CLI"""
    try:
        result = subprocess.run([
            'az', 'account', 'get-access-token', 
            '--resource', 'https://dynamicsessions.io'
        ], capture_output=True, text=True, check=True, shell=True)
        
        return json.loads(result.stdout).get('accessToken')
    except:
        print("❌ Failed to get bearer token. Run: az login")
        return None

def get_environment():
    """Get deployment environment from args or env var"""
    if '--env' in sys.argv:
        idx = sys.argv.index('--env')
        if idx + 1 < len(sys.argv):
            env = sys.argv[idx + 1].lower()
            if env in DEPLOYMENTS:
                return env, DEPLOYMENTS[env]
    
    env = os.environ.get('DEPLOYMENT_ENV', 'local').lower()
    if env in DEPLOYMENTS:
        return env, DEPLOYMENTS[env]
    
    print("❌ Invalid environment. Use: --env <local|appservice|containerapp>")
    sys.exit(1)

def get_identifier(env):
    """Get identifier for Container Apps - MANDATORY for containerapp"""
    if '--identifier' in sys.argv:
        idx = sys.argv.index('--identifier')
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    
    # For containerapp, identifier is mandatory
    if env == 'containerapp':
        print("❌ --identifier is REQUIRED for Container Apps")
        print("Usage: --identifier <your-session-identifier>")
        print("Example: --identifier b52e9f2d-6fef-4fd4-8eba-eba0a9d4e7dc")
        sys.exit(1)
    
    return "default-identifier"

def get_headers(config, bearer_token=None):
    """Get appropriate headers"""
    headers = {"Content-Type": "application/json"}
    if config['auth_type'] == 'bearer' and bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    return headers

def get_params(env):
    """Get query parameters for environment"""
    return {"identifier": get_identifier(env)} if env == 'containerapp' else {}