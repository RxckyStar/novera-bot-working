"""
Test script for server-specific configuration settings
This will check if server configuration is working as expected
"""

import logging
from server_config import (
    is_command_disabled, 
    uses_sassy_language, 
    get_message_style,
    get_server_configs
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('test_server_config')

def test_server_config():
    """Test server configuration settings for specific servers"""
    
    # Define test servers
    servers = {
        "1350165280940228629": "Original Novera Server",
        "1301830184307130401": "Second Server",
        "1345538548027232307": "BLR: NoVera E-Sports League Server"
    }
    
    # Define test commands
    commands = ["spank", "headpat", "checkvalue", "activity"]
    
    # Test each server
    for server_id, server_name in servers.items():
        logger.info(f"Testing configuration for {server_name} (ID: {server_id})")
        
        # Test if server uses sassy language
        sassy = uses_sassy_language(server_id)
        logger.info(f"  Uses sassy language: {sassy}")
        
        # Test if specific commands are disabled
        for cmd in commands:
            disabled = is_command_disabled(cmd, server_id)
            logger.info(f"  Command '{cmd}' disabled: {disabled}")
        
        # Test message styles
        success_msg = get_message_style("success", server_id)
        error_msg = get_message_style("error", server_id)
        logger.info(f"  Success message style: {success_msg}")
        logger.info(f"  Error message style: {error_msg}")
        
        logger.info(f"Configuration testing complete for {server_name}")
        logger.info("---")

if __name__ == "__main__":
    test_server_config()