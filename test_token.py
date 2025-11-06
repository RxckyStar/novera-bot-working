import os
import sys
import requests
import logging

logging.basicConfig(level=logging.INFO)

# Get the token from the environment
token = os.environ.get("DISCORD_TOKEN")
if not token:
    with open('.env', 'r') as f:
        for line in f:
            if line.startswith('DISCORD_TOKEN='):
                token = line.strip().split('=', 1)[1]
                break

if not token:
    logging.error("No Discord token found")
    sys.exit(1)

# Clean the token
token = token.strip().strip('"').strip("'")
logging.info(f"Token length: {len(token)}")

# Test the token
url = "https://discord.com/api/v10/users/@me"
headers = {
    "Authorization": f"Bot {token}"
}

try:
    response = requests.get(url, headers=headers)
    logging.info(f"Response status code: {response.status_code}")
    if response.status_code == 200:
        logging.info("Token is valid!")
        bot_info = response.json()
        logging.info(f"Bot username: {bot_info.get('username')}#{bot_info.get('discriminator')}")
        logging.info(f"Bot ID: {bot_info.get('id')}")
    else:
        logging.error(f"Token is invalid. Response: {response.text}")
except Exception as e:
    logging.error(f"Error testing token: {e}")