#!/usr/bin/env python3
"""
Test script to verify Radarr API connectivity and queue access
"""
import requests
import json
import sys
import time
import traceback

# Radarr connection details from config
API_URL = "http://10.0.0.10:7878"
API_KEY = "fff4318f18ca48da8fb33a9fe5b136c2"

def check_connection():
    """Test basic connectivity to Radarr API"""
    try:
        url = f"{API_URL.rstrip('/')}/api/v3/system/status"
        headers = {"X-Api-Key": API_KEY}
        
        print(f"Testing connection to Radarr at {API_URL}...")
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            print(f"Connection successful! Radarr version: {data.get('version', 'unknown')}")
            return True
        else:
            print(f"Connection failed with status code {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"Error connecting to Radarr: {str(e)}")
        traceback.print_exc()
        return False

def get_queue():
    """Test getting the download queue from Radarr"""
    try:
        url = f"{API_URL.rstrip('/')}/api/v3/queue"
        headers = {"X-Api-Key": API_KEY}
        
        print("Fetching Radarr queue...")
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            queue_items = data.get('records', [])
            print(f"Queue fetch successful! Found {len(queue_items)} items in queue")
            
            if queue_items:
                print("\nSample of queue items:")
                for i, item in enumerate(queue_items[:3]):  # Show first 3 items
                    print(f"Item {i+1}:")
                    print(f"  - Title: {item.get('title', 'Unknown')}")
                    print(f"  - Status: {item.get('status', 'Unknown')}")
                    print(f"  - Progress: {item.get('sizeleft', 0)}/{item.get('size', 0)}")
                    print(f"  - MovieID: {item.get('movieId', 'Unknown')}")
            
            return True
        else:
            print(f"Queue fetch failed with status code {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"Error fetching Radarr queue: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("-" * 50)
    print("RADARR API CONNECTION TEST")
    print("-" * 50)
    
    if check_connection():
        print("\n✅ Connection test passed")
    else:
        print("\n❌ Connection test failed")
        sys.exit(1)
        
    print("\n" + "-" * 50)
    
    if get_queue():
        print("\n✅ Queue test passed")
    else:
        print("\n❌ Queue test failed")
        sys.exit(1)
    
    print("\nAll tests passed successfully!")
