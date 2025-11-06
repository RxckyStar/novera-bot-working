#!/usr/bin/env python3
"""Test script for auto_401_recovery.py"""

import time
import sys
import subprocess
import signal

# Run auto_401_recovery.py for a limited time
print("Starting auto_401_recovery.py test")
process = subprocess.Popen(["python", "auto_401_recovery.py"])

# Wait for 10 seconds
print(f"Waiting for 10 seconds...")
time.sleep(10)

# Kill the process
print(f"Terminating auto_401_recovery.py (PID: {process.pid})")
process.terminate()
process.wait(timeout=5)

print("Test completed")