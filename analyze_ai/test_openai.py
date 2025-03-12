#!/usr/bin/env python3
"""
Simple script to test OpenAI API key
"""

import os
import sys
import requests
from dotenv import load_dotenv, find_dotenv

# Print current working directory and script location
print(f"Current working directory: {os.getcwd()}")
print(f"Script location: {os.path.dirname(os.path.abspath(__file__))}")

# Try to find .env file
dotenv_path = find_dotenv()
print(f"Found .env file at: {dotenv_path if dotenv_path else 'Not found'}")

# Try multiple locations for .env file
possible_env_paths = [
    os.path.join(os.getcwd(), '.env'),
    os.path.join(os.getcwd(), 'PushshiftDumps', '.env'),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
]

for path in possible_env_paths:
    if os.path.exists(path):
        print(f"Loading .env from: {path}")
        load_dotenv(path)
        break
else:
    print("Could not find .env file in any of the expected locations:")
    for path in possible_env_paths:
        print(f"  - {path} {'(exists)' if os.path.exists(path) else '(not found)'}")

# Get API key from environment variable
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ORG_ID = os.getenv("OPENAI_ORG_ID")

print(f"API Key found: {'Yes' if OPENAI_API_KEY else 'No'}")
if OPENAI_API_KEY:
    # Only show the first few and last few characters for security
    masked_key = OPENAI_API_KEY[:4] + "..." + OPENAI_API_KEY[-4:] if len(OPENAI_API_KEY) > 8 else "Too short"
    print(f"API Key (masked): {masked_key}")

print(f"Organization ID found: {'Yes' if OPENAI_ORG_ID else 'No'}")
if OPENAI_ORG_ID:
    print(f"Organization ID: {OPENAI_ORG_ID}")

# Test the API key with a simple request
def test_openai_api():
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    
    # Add organization ID if available
    if OPENAI_ORG_ID:
        headers["OpenAI-Organization"] = OPENAI_ORG_ID
        print(f"Using organization ID: {OPENAI_ORG_ID}")
    
    # Try with a simpler model first
    model = "gpt-3.5-turbo"
    print(f"Testing with model: {model}")
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Say hello"}],
        "max_tokens": 10
    }
    
    try:
        print("Sending test request to OpenAI API...")
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload
        )
        
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            print("Success! API key is working.")
            print(f"Response: {response.json()['choices'][0]['message']['content']}")
            return True
        else:
            print(f"Error: {response.text}")
            
            # Common error troubleshooting
            if response.status_code == 401:
                print("\nTroubleshooting 401 Unauthorized:")
                print("1. Check if your API key is correct")
                print("2. Make sure your API key is active and not revoked")
                print("3. Verify your .env file is in the correct location and formatted properly")
                print("   It should contain: OPENAI_API_KEY=your_key_here")
                
            elif response.status_code == 429:
                print("\nTroubleshooting 429 Rate Limit:")
                print("1. You may have exceeded your API quota")
                print("2. Try again later or check your usage limits in OpenAI dashboard")
                
            elif response.status_code == 404:
                print("\nTroubleshooting 404 Not Found:")
                print(f"1. The model '{model}' may not exist or you don't have access to it")
                print("2. Try using a different model like 'gpt-3.5-turbo'")
                
            return False
                
    except Exception as e:
        print(f"Exception occurred: {e}")
        return False

if __name__ == "__main__":
    if not OPENAI_API_KEY:
        print("No OpenAI API key found. Please add your API key to the .env file.")
        print("The .env file should be in the root directory and contain: OPENAI_API_KEY=your_key_here")
    else:
        test_openai_api() 