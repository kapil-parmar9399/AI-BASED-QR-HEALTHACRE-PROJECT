#!/usr/bin/env python3
"""Verify that ngrok tunnel makes the public link reachable from external network.

This script will:
1. Ensure NGROK_AUTHTOKEN is set in the environment.
2. Import the FastAPI app and use get_public_base_url() to establish a tunnel.
3. Use requests to fetch the '/' path via the returned URL to confirm it works.
"""
import os, time

from main import get_public_base_url, app
import requests

if not os.getenv('NGROK_AUTHTOKEN'):
    print('NGROK_AUTHTOKEN not configured; cannot test tunnel.')
    exit(1)

# call once to trigger tunnel creation
pub = get_public_base_url()
print('Public base URL:', pub)

# wait a moment for ngrok to settle
time.sleep(2)

try:
    r = requests.get(pub)
    print('GET', pub, '->', r.status_code)
    print('Content snippet:', r.text[:200])
except Exception as e:
    print('Request failed:', e)
