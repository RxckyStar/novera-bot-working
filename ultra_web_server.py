#!/usr/bin/env python3
"""
Ultra Web Server
----------------
This script runs ONLY the Flask web server portion of the bot,
completely separate from the Discord bot itself to avoid any
event loop conflicts.
"""

import os
import sys
import logging
import threading
from flask import Flask, jsonify, request
import psutil

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ultra_web.log')
    ]
)

# Create our Flask app
app = Flask(__name__)

@app.route('/')
def home():
    """Home endpoint"""
    return "Novera Assistant is watching you darling! 👀"

@app.route('/healthz')
def healthz():
    """Health check endpoint for monitoring"""
    return jsonify({
        "status": "ok",
        "pid": os.getpid(),
        "python_version": sys.version,
        "uptime": psutil.boot_time()
    })

@app.route('/restart')
def restart_bot_endpoint():
    """Endpoint to restart the bot"""
    auth_key = request.args.get('key')
    expected_key = os.environ.get("RESTART_KEY", "novera_restart_key")
    
    if auth_key != expected_key:
        return jsonify({"error": "Unauthorized"}), 403
        
    # Start restart in background thread
    def restart_thread():
        try:
            import subprocess
            subprocess.Popen(["python", "ultra_direct_run.py"])
        except Exception as e:
            logging.error(f"Failed to restart bot: {e}")
    
    threading.Thread(target=restart_thread).start()
    return jsonify({"status": "restarting"})

def run_webserver():
    """Run the Flask web server on port 5001"""
    try:
        app.run(host='0.0.0.0', port=5001)
    except Exception as e:
        logging.error(f"Web server error: {e}")

if __name__ == "__main__":
    # Run the web server
    run_webserver()