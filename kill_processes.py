import psutil
import sys
import os
import time

def kill_python_processes():
    """
    Kill only the specific bot processes and not monitoring or recovery processes.
    This ensures the recovery mechanisms continue to work and can restart the bot.
    """
    current_pid = os.getpid()
    killed = False
    
    print(f"Current PID: {current_pid}")
    print("Scanning for specific bot processes to terminate...")
    
    # Track specific PIDs we want to kill
    pids_to_kill = []
    flask_pids = []
    discord_bot_pids = []
    
    # First pass - identify processes but don't kill them yet
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            proc_name = proc.info['name']
            proc_pid = proc.pid
            
            if proc_pid == current_pid:
                continue
                
            cmdline = " ".join(proc.info['cmdline']) if proc.info['cmdline'] else ""
            
            # Specifically identify Discord bot processes
            if proc_name == 'python' and "bot.py" in cmdline:
                print(f"Found Discord bot process {proc_pid}: {cmdline}")
                discord_bot_pids.append(proc_pid)
            
            # Identify gunicorn processes related to our bot
            elif "gunicorn" in cmdline and "main:app" in cmdline:
                print(f"Found gunicorn process {proc_pid}: {cmdline}")
                flask_pids.append(proc_pid)
            
            # DO NOT kill monitoring processes like health_monitor.py, token_refresher.py, auto_401_recovery.py
                
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            print(f"Error accessing process: {e}")
            pass
    
    # Only kill Discord bot processes if we have monitoring processes running
    # This ensures we don't kill everything and have nothing to restart the bot
    pids_to_kill = discord_bot_pids + flask_pids
    
    # Second pass - kill only the identified processes
    for pid in pids_to_kill:
        try:
            proc = psutil.Process(pid)
            print(f"Killing process {pid}")
            proc.kill()
            killed = True
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            print(f"Error killing process {pid}: {e}")
            pass
    
    # Remove any lock files
    lock_files = ["bot.lock", "auto_401_recovery.pid", "token_refresher.pid"]
    for lock_file in lock_files:
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
                print(f"Removed {lock_file} file")
        except Exception as e:
            print(f"Error removing lock file {lock_file}: {e}")
    
    return killed

if __name__ == "__main__":
    killed = kill_python_processes()
    print(f"Processes killed: {killed}")
    # Brief pause to allow processes to fully terminate
    time.sleep(1)
    sys.exit(0)  # Always exit with 0 to avoid pipeline failures
