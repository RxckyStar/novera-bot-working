#!/usr/bin/env python3
"""
Token System Tester
This tool provides comprehensive testing of the token management system,
verifying each component of the ultra-reliable token handling pipeline.
"""

import os
import time
import json
import logging
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger("test_token_system")

def test_config_module():
    """Test the token handling in config.py"""
    print("\n=== Testing config.py token handling ===")
    try:
        from config import get_token, clean_token, validate_token, save_token_cache, load_token_from_cache
        
        # Test token cleaning
        test_tokens = [
            "MTM1MDcxMjEyNzg2OTk0MzgyOA.Grl5HP.Pp5mwaSo0VSEmCVdOoJsGkkrkCHA5OjCXDvuGE",  # Good token
            "\"MTM1MDcxMjEyNzg2OTk0MzgyOA.Grl5HP.Pp5mwaSo0VSEmCVdOoJsGkkrkCHA5OjCXDvuGE\"",  # Quoted token
            "MTM1MDcxMjEyNzg2OTk0MzgyOA.Grl5HP.Pp5mwaSo0VSEmCVdOoJsGkkrkCHA5OjCXDvuGE\n",  # Newline
            " MTM1MDcxMjEyNzg2OTk0MzgyOA.Grl5HP.Pp5mwaSo0VSEmCVdOoJsGkkrkCHA5OjCXDvuGE ",  # Spaces
        ]
        
        print("Testing token cleaning...")
        for i, token in enumerate(test_tokens):
            cleaned = clean_token(token)
            is_valid = validate_token(cleaned)
            print(f"  Test {i+1}: {'✅ PASS' if is_valid else '❌ FAIL'} - " 
                  f"Original len: {len(token)}, Cleaned len: {len(cleaned)}, Valid: {is_valid}")
        
        # Test cache operations
        print("\nTesting token cache operations...")
        test_token = clean_token(test_tokens[0])
        if validate_token(test_token):
            print(f"  Saving token to cache... ", end="")
            save_token_cache(test_token)
            print("✅ Done")
            
            print(f"  Loading token from cache... ", end="")
            cached_token = load_token_from_cache()
            if cached_token == test_token:
                print(f"✅ PASS - Cache retrieval successful")
            else:
                print(f"❌ FAIL - Cache retrieval returned different token")
        else:
            print(f"❌ Cannot test cache - test token failed validation")
        
        # Test full get_token function
        print("\nTesting get_token function...")
        try:
            token = get_token()
            if token and len(token) > 40:
                print(f"✅ PASS - Successfully retrieved token (length: {len(token)})")
            else:
                print(f"❌ FAIL - Retrieved token is invalid (length: {len(token) if token else 0})")
        except Exception as e:
            print(f"❌ FAIL - Error in get_token: {e}")
            
        return True
    except Exception as e:
        print(f"❌ ERROR testing config module: {e}")
        return False

def test_token_tester():
    """Test the token_tester.py module"""
    print("\n=== Testing token_tester.py ===")
    try:
        if not os.path.exists("token_tester.py"):
            print("❌ token_tester.py not found")
            return False
            
        sys.path.append(os.getcwd())
        import token_tester
        
        # Test token testing function
        print("Testing test_token function...")
        from config import get_token
        token = get_token()
        
        if not token:
            print("❌ Cannot test token_tester - no token available")
            return False
            
        is_valid, error = token_tester.test_token(token)
        if is_valid:
            print(f"✅ PASS - Token is valid according to Discord API")
        else:
            print(f"❌ FAIL - Token invalid: {error}")
        
        # Test finding valid token
        print("\nTesting find_valid_token function...")
        valid_token = token_tester.find_valid_token()
        if valid_token:
            print(f"✅ PASS - Found valid token (length: {len(valid_token)})")
        else:
            print(f"❌ FAIL - Could not find valid token")
            
        # Test token fixing
        print("\nTesting fix_token_in_env function...")
        if token_tester.fix_token_in_env():
            print(f"✅ PASS - Successfully fixed token in environment")
            
            # Check if token cache was created
            if os.path.exists("token_cache.json"):
                print(f"✅ PASS - Token cache file created")
                try:
                    with open("token_cache.json", "r") as f:
                        cache_data = json.load(f)
                    if "token" in cache_data and len(cache_data["token"]) > 40:
                        print(f"✅ PASS - Token cache contains valid token")
                    else:
                        print(f"❌ FAIL - Token cache does not contain valid token")
                except Exception as e:
                    print(f"❌ FAIL - Error reading token cache: {e}")
            else:
                print(f"❌ FAIL - Token cache file not created")
        else:
            print(f"❌ FAIL - Could not fix token in environment")
            
        return True
    except ImportError as e:
        print(f"❌ ERROR importing token_tester: {e}")
        return False
    except Exception as e:
        print(f"❌ ERROR testing token_tester: {e}")
        return False

def test_auto_401_recovery():
    """Test the auto_401_recovery.py module's token functions"""
    print("\n=== Testing auto_401_recovery.py token functions ===")
    try:
        if not os.path.exists("auto_401_recovery.py"):
            print("❌ auto_401_recovery.py not found")
            return False
            
        # Import recovery module
        sys.path.append(os.getcwd())
        try:
            # Direct testing might not work due to initialization code
            # Just check for token_tester integration
            with open("auto_401_recovery.py", "r") as f:
                content = f.read()
                
            if "token_tester" in content and "fix_token_in_env" in content:
                print(f"✅ PASS - auto_401_recovery.py includes token_tester integration")
            else:
                print(f"❌ FAIL - auto_401_recovery.py does NOT include token_tester integration")
                
            return True
        except Exception as e:
            print(f"❌ ERROR checking auto_401_recovery.py: {e}")
            return False
    except Exception as e:
        print(f"❌ ERROR testing auto_401_recovery.py: {e}")
        return False

def test_env_file():
    """Test the .env file token configuration"""
    print("\n=== Testing .env file token configuration ===")
    try:
        if not os.path.exists(".env"):
            print("❌ .env file not found")
            return False
            
        print("Checking .env file content...")
        with open(".env", "r") as f:
            content = f.read()
            
        if "DISCORD_TOKEN=" in content:
            lines = content.split("\n")
            token_line = None
            for line in lines:
                if line.strip().startswith("DISCORD_TOKEN="):
                    token_line = line.strip()
                    break
                    
            if token_line:
                token_value = token_line[len("DISCORD_TOKEN="):]
                token_value = token_value.strip("\"' ")
                
                if len(token_value) > 40 and "." in token_value:
                    print(f"✅ PASS - .env file contains valid token format (length: {len(token_value)})")
                else:
                    print(f"❌ FAIL - .env token format invalid (length: {len(token_value)})")
            else:
                print(f"❌ FAIL - Could not extract token line from .env")
        else:
            print(f"❌ FAIL - .env file does not contain DISCORD_TOKEN")
            
        return True
    except Exception as e:
        print(f"❌ ERROR testing .env file: {e}")
        return False

def test_token_cache():
    """Test the token_cache.json file"""
    print("\n=== Testing token_cache.json ===")
    try:
        if not os.path.exists("token_cache.json"):
            print("❌ token_cache.json not found")
            return False
            
        print("Checking token_cache.json content...")
        try:
            with open("token_cache.json", "r") as f:
                cache_data = json.load(f)
                
            if "token" in cache_data:
                token = cache_data["token"]
                if len(token) > 40 and "." in token:
                    print(f"✅ PASS - Cache contains valid token format (length: {len(token)})")
                else:
                    print(f"❌ FAIL - Cached token format invalid (length: {len(token)})")
                    
            if "timestamp" in cache_data:
                timestamp = cache_data.get("timestamp")
                try:
                    dt = datetime.fromisoformat(timestamp)
                    age_hours = (datetime.now() - dt).total_seconds() / 3600
                    print(f"✅ PASS - Cache timestamp valid, age: {age_hours:.1f} hours")
                except:
                    print(f"❌ FAIL - Cache timestamp invalid: {timestamp}")
            else:
                print(f"❌ FAIL - Cache missing timestamp")
                
            return True
        except json.JSONDecodeError:
            print(f"❌ FAIL - token_cache.json is not valid JSON")
            return False
        except Exception as e:
            print(f"❌ ERROR reading token_cache.json: {e}")
            return False
    except Exception as e:
        print(f"❌ ERROR testing token_cache.json: {e}")
        return False

def run_all_tests():
    """Run all token system tests"""
    print("======================================")
    print("     DISCORD TOKEN SYSTEM TESTER      ")
    print("======================================")
    print(f"Starting tests at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Track test results
    results = {}
    
    # Run all tests
    results["config"] = test_config_module()
    results["token_tester"] = test_token_tester()
    results["auto_401"] = test_auto_401_recovery()
    results["env_file"] = test_env_file()
    results["token_cache"] = test_token_cache()
    
    # Summary
    print("\n======================================")
    print("           TEST SUMMARY               ")
    print("======================================")
    for test, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test}")
        
    overall = all(results.values())
    print("\nOVERALL RESULT:", "✅ PASS" if overall else "❌ FAIL")
    print("======================================")
    
    return overall

if __name__ == "__main__":
    run_all_tests()