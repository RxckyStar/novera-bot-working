#!/usr/bin/env python3
"""
Recovery Tools Verification Script

This script checks that all components of the ultra-aggressive 401 recovery system
are correctly installed and configured.
"""

import os
import sys
import subprocess
import logging
from typing import List, Dict, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='verify_recovery.log'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(levelname)s: %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)
logger = logging.getLogger("verify_recovery")

# Required files for the recovery system
REQUIRED_FILES = [
    "auto_401_recovery.py",
    "401_recovery_control.sh",
    "bulletproof.sh",
    "check_auth_errors.py",
    "keep_running.py",
    "health_monitor.py",
    "TOKEN_RECOVERY.md",
    "UPTIME_GUARANTEED.md",
    "UPTIME.md"
]

# Required directories
REQUIRED_DIRS = [
    "logs"
]

# Files that should be executable
SHOULD_BE_EXECUTABLE = [
    "401_recovery_control.sh",
    "bulletproof.sh",
    "check_status.sh"
]

# Configuration values to verify
CONFIG_CHECKS = {
    "auto_401_recovery.py": [
        ("CHECK_INTERVAL", 20, "<"),  # Should be less than 20 seconds
        ("MAX_CONSECUTIVE_RESETS", 10, ">"),  # Should be more than 10
        ("COOLDOWN_PERIOD", 120, "<"),  # Should be less than 120 seconds
    ]
}

def check_file_exists(filename: str) -> bool:
    """Check if a file exists"""
    exists = os.path.isfile(filename)
    if exists:
        logger.info(f"✓ Found {filename}")
    else:
        logger.error(f"✗ Missing {filename}")
    return exists

def check_dir_exists(dirname: str) -> bool:
    """Check if a directory exists"""
    exists = os.path.isdir(dirname)
    if exists:
        logger.info(f"✓ Found directory {dirname}")
    else:
        logger.error(f"✗ Missing directory {dirname}")
    return exists

def check_file_executable(filename: str) -> bool:
    """Check if a file is executable"""
    if not os.path.isfile(filename):
        logger.error(f"✗ Cannot check executable status: {filename} does not exist")
        return False
    
    is_executable = os.access(filename, os.X_OK)
    if is_executable:
        logger.info(f"✓ {filename} is executable")
    else:
        logger.error(f"✗ {filename} is NOT executable")
    return is_executable

def check_service_running(service_name: str, process_pattern: str) -> bool:
    """Check if a service is running"""
    try:
        # Use ps and grep to find the process
        cmd = f"ps aux | grep -v grep | grep '{process_pattern}'"
        result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
        
        running = result.returncode == 0 and result.stdout.strip() != ""
        if running:
            logger.info(f"✓ {service_name} is running")
        else:
            logger.warning(f"! {service_name} is not running")
        return running
    except Exception as e:
        logger.error(f"✗ Error checking if {service_name} is running: {e}")
        return False

def check_config_values(filename: str) -> List[Tuple[bool, str]]:
    """Check configuration values in a file"""
    if not os.path.isfile(filename):
        logger.error(f"✗ Cannot check config values: {filename} does not exist")
        return [(False, f"File {filename} not found")]
    
    results = []
    
    try:
        with open(filename, 'r') as f:
            content = f.read()
            
        for config_name, threshold, operator in CONFIG_CHECKS.get(filename, []):
            # Try to extract the value using a simple pattern matching approach
            import re
            pattern = rf"{config_name}\s*=\s*(\d+)"
            match = re.search(pattern, content)
            
            if match:
                value = int(match.group(1))
                
                # Check the condition based on operator
                if operator == "<" and value < threshold:
                    results.append((True, f"✓ {config_name} is {value} (less than {threshold} as required)"))
                elif operator == ">" and value > threshold:
                    results.append((True, f"✓ {config_name} is {value} (greater than {threshold} as required)"))
                elif operator == "==" and value == threshold:
                    results.append((True, f"✓ {config_name} is exactly {threshold} as required"))
                else:
                    if operator == "<":
                        results.append((False, f"✗ {config_name} is {value}, which is NOT less than {threshold}"))
                    elif operator == ">":
                        results.append((False, f"✗ {config_name} is {value}, which is NOT greater than {threshold}"))
                    else:
                        results.append((False, f"✗ {config_name} is {value}, which does NOT match required value {threshold}"))
            else:
                results.append((False, f"✗ Could not find {config_name} in {filename}"))
    except Exception as e:
        results.append((False, f"✗ Error checking config in {filename}: {e}"))
    
    # Log the results
    for success, message in results:
        if success:
            logger.info(message)
        else:
            logger.error(message)
    
    return results

def verify_all() -> Dict[str, int]:
    """Run all verification checks and return counts"""
    counts = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "warnings": 0
    }
    
    # Check required files
    for filename in REQUIRED_FILES:
        counts["total"] += 1
        if check_file_exists(filename):
            counts["passed"] += 1
        else:
            counts["failed"] += 1
    
    # Check required directories
    for dirname in REQUIRED_DIRS:
        counts["total"] += 1
        if check_dir_exists(dirname):
            counts["passed"] += 1
        else:
            counts["failed"] += 1
    
    # Check executable files
    for filename in SHOULD_BE_EXECUTABLE:
        counts["total"] += 1
        if check_file_executable(filename):
            counts["passed"] += 1
        else:
            counts["failed"] += 1
    
    # Check services
    services = [
        ("Auto 401 Recovery", "auto_401_recovery.py"),
        ("Health Monitor", "health_monitor.py"),
        ("Keep Running", "keep_running.py")
    ]
    
    for service_name, pattern in services:
        counts["total"] += 1
        if check_service_running(service_name, pattern):
            counts["passed"] += 1
        else:
            counts["warnings"] += 1  # Just a warning since services might be intentionally stopped
    
    # Check configuration values
    for filename, checks in CONFIG_CHECKS.items():
        results = check_config_values(filename)
        for success, _ in results:
            counts["total"] += 1
            if success:
                counts["passed"] += 1
            else:
                counts["failed"] += 1
    
    return counts

def print_summary(counts: Dict[str, int]) -> None:
    """Print a summary of verification results"""
    print("\n" + "=" * 50)
    print("RECOVERY SYSTEM VERIFICATION SUMMARY")
    print("=" * 50)
    
    total = counts["total"]
    passed = counts["passed"]
    failed = counts["failed"]
    warnings = counts["warnings"]
    
    if total > 0:
        pass_percent = (passed / total) * 100
    else:
        pass_percent = 0
    
    print(f"Total checks:    {total}")
    print(f"Passed:          {passed} ({pass_percent:.1f}%)")
    print(f"Failed:          {failed}")
    print(f"Warnings:        {warnings}")
    print("=" * 50)
    
    if failed == 0 and warnings == 0:
        print("✓ ALL CHECKS PASSED! Recovery system is fully operational.")
    elif failed == 0 and warnings > 0:
        print("! CHECKS PASSED WITH WARNINGS. Recovery system may need attention.")
    elif failed <= 2:
        print("! MINOR ISSUES DETECTED. Recovery system needs some fixes.")
    else:
        print("✗ CRITICAL ISSUES DETECTED. Recovery system needs immediate attention!")
    
    print("=" * 50)

def main() -> int:
    """Main function"""
    print("Ultra-aggressive 401 Recovery System Verification")
    print("------------------------------------------------")
    
    counts = verify_all()
    print_summary(counts)
    
    logger.info(f"Verification completed. Passed: {counts['passed']}, Failed: {counts['failed']}, Warnings: {counts['warnings']}")
    
    if counts["failed"] > 0:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())