"""
Server Configuration Module
Manages server-specific settings for multi-server Discord bot support
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional, Union

# Configure logging
logger = logging.getLogger('novera.server_config')

# Define the path to the server configuration file
CONFIG_FILE = "server_config.json"

# Default server configurations
DEFAULT_CONFIGS = {
    # Original Novera server
    "1350165280940228629": {
        "name": "Novera",
        "roles": {
            "management": ["1350175902738419734"],  # Management role
            "verified": ["1350182725725982850"],    # Verified member role
            "tryouter": ["1353217343357980824"],    # Tryouter role
            "noverian": ["1350181431055519774"],    # Noverian role
            "pro": ["1350181841556836402"],         # Professional player role
            "veteran": ["1350182201511669831"]      # Veteran player role
        },
        "channels": {
            "announcements": "announcements",       # Channel for announcements
            "tryout_results": "1347678723750760489", # Channel for tryout results
            "values": "1343780575248646245",        # Channel for player values
            "welcome": "1350199401426980955",       # Channel for welcome/leave messages
            "giveaways": "1337572584589627422"      # Channel for giveaways
        },
        "settings": {
            "assign_roles_on_join": True,           # Auto-assign roles on join
            "remove_roles_on_tryout": True,         # Remove roles on tryout
            "assign_roles_on_tryout": True,         # Assign roles on tryout
            "use_sassy_language": True,             # Use playful language with pet names
            "disabled_commands": []                 # No disabled commands
        },
        "message_style": {
            "success": [
                "Mommy is so proud of you, sweetheart! 💖",
                "That's my good little Novarian! 💋",
                "You're making Mommy so happy, darling! 💅✨",
                "Such a good baby for Mommy! 💝",
                "Mommy loves when you behave so well! 😘"
            ],
            "error": [
                "Oh no, sweetie! Mommy needs to fix this for you! 💔",
                "Don't worry, darling, Mommy will make it all better! 💋",
                "Oopsie! Even Mommy makes mistakes sometimes, honey! 💝",
                "Mommy's having a little trouble, sweetheart! Let me fix that! 💖",
                "Something's gone wrong, baby! Mommy will handle it! 💅"
            ]
        }
    },
    # New server configuration
    "1301830184307130401": {
        "name": "Novera Alternate",
        "roles": {
            "management": [
                "1301830696536379442",  # Admin role
                "1301830837666320405",  # Moderator role
                "1301954206231695413"   # Staff role
            ],
            "verified": ["1301831200822042744"],    # Member role
            "tryouter": ["1353217343357980824"],    # Tryouter role
            "noverian": ["1301831096519045213"],    # Noverian role
            "pro": ["1301831334721392640"],         # Professional player role
            "veteran": ["1301831430783971470"]      # Veteran player role
        },
        "channels": {
            "announcements": "1354613683442942052", # Channel for announcements
            "tryout_results": "1347678723750760489", # Channel for tryout results
            "values": "1343780575248646245",        # Channel for player values
            "welcome": "1301830184307130403",       # Channel for welcome/leave messages
            "giveaways": "giveaways"                # Channel for giveaways
        },
        "settings": {
            "assign_roles_on_join": False,          # Don't auto-assign roles on join
            "remove_roles_on_tryout": False,        # Don't remove roles on tryout
            "assign_roles_on_tryout": False,        # Don't assign roles on tryout
            "use_sassy_language": True,             # Use playful language with pet names
            "disabled_commands": []                 # No disabled commands
        },
        "message_style": {
            "success": [
                "Mommy is so proud of you, sweetheart! 💖",
                "That's my good little Novarian! 💋",
                "You're making Mommy so happy, darling! 💅✨",
                "Such a good baby for Mommy! 💝",
                "Mommy loves when you behave so well! 😘"
            ],
            "error": [
                "Oh no, sweetie! Mommy needs to fix this for you! 💔",
                "Don't worry, darling, Mommy will make it all better! 💋",
                "Oopsie! Even Mommy makes mistakes sometimes, honey! 💝",
                "Mommy's having a little trouble, sweetheart! Let me fix that! 💖",
                "Something's gone wrong, baby! Mommy will handle it! 💅"
            ]
        }
    },
    # BLR NoVera Server configuration
    "1345538548027232307": {
        "name": "BLR: NoVera E-Sports League | [NATIONAL]",
        "roles": {
            "management": [
                "1345539263042687016",              # Manager role
                "1360251493252333821"               # Evaluator role
            ],
            "verified": [],                         # Member role
            "tryouter": [],                         # Tryouter role
            "noverian": [],                         # Noverian role
            "pro": [],                              # Professional player role
            "veteran": []                           # Veteran player role
        },
        "channels": {
            "announcements": "announcements",       # Channel for announcements
            "tryout_results": "1360253118406988120", # Channel for tryout/evaluation results
            "values": "1360253232806625361",        # Channel for player values
            "welcome": "1345547232648106105",       # Channel for welcome/leave messages
            "giveaways": "giveaways",               # Channel for giveaways
            "evaluation_requests": "1360251844907106365" # Channel for evaluation requests
        },
        "settings": {
            "assign_roles_on_join": False,          # Don't auto-assign roles on join
            "remove_roles_on_tryout": False,        # Don't remove roles on tryout
            "assign_roles_on_tryout": False,        # Don't assign roles on tryout
            "use_sassy_language": False,            # Use professional language, no pet names
            "disabled_commands": ["spank", "headpat"] # Disabled commands for BLR server
        },
        "message_style": {
            "success": [
                "Operation completed successfully! ✅",
                "Command executed successfully! ✅",
                "Action completed! ✅",
                "Success! ✅",
                "Command processed successfully! ✅"
            ],
            "error": [
                "There was an error processing your request. Please try again. ❌",
                "Command failed. Please check your input and try again. ❌",
                "An error occurred. Please try again later. ❌",
                "Unable to complete the requested action. ❌",
                "Command error. Please try again with correct parameters. ❌"
            ]
        }
    }
}

# In-memory server configurations
_server_configs: Dict[str, Dict[str, Any]] = {}


def _load_server_configs() -> Dict[str, Dict[str, Any]]:
    """Load server configs from file or create default if doesn't exist"""
    global _server_configs
    
    if _server_configs:
        return _server_configs
    
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                configs = json.load(f)
            logger.info(f"Loaded server configurations from {CONFIG_FILE}")
            
            # Ensure all default servers are included
            for server_id, default_config in DEFAULT_CONFIGS.items():
                if server_id not in configs:
                    configs[server_id] = default_config
                    logger.info(f"Added missing default config for server {server_id}")
            
            _server_configs = configs
            return configs
        else:
            logger.info(f"Server config file {CONFIG_FILE} not found, creating defaults")
            _save_server_configs(DEFAULT_CONFIGS)
            _server_configs = DEFAULT_CONFIGS
            return DEFAULT_CONFIGS
    except Exception as e:
        logger.error(f"Error loading server configs: {e}", exc_info=True)
        _server_configs = DEFAULT_CONFIGS
        return DEFAULT_CONFIGS


def _save_server_configs(configs: Dict[str, Dict[str, Any]]) -> None:
    """Save server configs to file"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(configs, f, indent=2)
        logger.info(f"Saved server configurations to {CONFIG_FILE}")
    except Exception as e:
        logger.error(f"Error saving server configs: {e}", exc_info=True)


def get_server_configs() -> Dict[str, Dict[str, Any]]:
    """Get all server configurations"""
    return _load_server_configs()


def get_server_config(server_id: str) -> Dict[str, Any]:
    """Get the configuration for a specific server"""
    configs = _load_server_configs()
    
    if server_id in configs:
        return configs[server_id]
    
    # If server not found, create a default configuration
    logger.warning(f"Server {server_id} not configured, creating default configuration")
    configs[server_id] = {
        "name": f"Server {server_id}",
        "roles": {
            "management": [],
            "verified": [],
            "tryouter": [],
            "noverian": [],
            "pro": [],
            "veteran": []
        },
        "channels": {
            "announcements": "announcements",
            "tryout_results": "tryout-results",
            "values": "player-values",
            "giveaways": "giveaways"
        }
    }
    _save_server_configs(configs)
    return configs[server_id]


def update_server_config(server_id: str, new_config: Dict[str, Any]) -> None:
    """Update the configuration for a specific server"""
    configs = _load_server_configs()
    configs[server_id] = new_config
    _save_server_configs(configs)
    logger.info(f"Updated configuration for server {server_id}")


def get_role_ids(role_type: str, server_id: str) -> List[str]:
    """Get role IDs for a specific server and role type"""
    server_config = get_server_config(server_id)
    
    if role_type in server_config.get("roles", {}):
        return server_config["roles"][role_type]
    
    logger.warning(f"Role type {role_type} not configured for server {server_id}")
    return []


def get_role_id(role_type: str, server_id: str) -> Optional[str]:
    """Get a single role ID for a specific server and role type (first one if multiple)"""
    role_ids = get_role_ids(role_type, server_id)
    return role_ids[0] if role_ids else None


def get_channel_id(channel_type: str, server_id: str) -> Optional[str]:
    """Get channel ID/name for a specific server and channel type"""
    server_config = get_server_config(server_id)
    
    if channel_type in server_config.get("channels", {}):
        return server_config["channels"][channel_type]
    
    logger.warning(f"Channel type {channel_type} not configured for server {server_id}")
    return None


def set_role_ids(role_type: str, server_id: str, role_ids: List[str]) -> None:
    """Set role IDs for a specific server and role type"""
    server_config = get_server_config(server_id)
    
    if "roles" not in server_config:
        server_config["roles"] = {}
        
    server_config["roles"][role_type] = role_ids
    update_server_config(server_id, server_config)
    logger.info(f"Updated {role_type} roles for server {server_id}: {role_ids}")


def set_channel_id(channel_type: str, server_id: str, channel_id: str) -> None:
    """Set channel ID for a specific server and channel type"""
    server_config = get_server_config(server_id)
    
    if "channels" not in server_config:
        server_config["channels"] = {}
        
    server_config["channels"][channel_type] = channel_id
    update_server_config(server_id, server_config)
    logger.info(f"Updated {channel_type} channel for server {server_id}: {channel_id}")


def get_server_name(server_id: str) -> str:
    """Get the human-readable name for a server"""
    server_config = get_server_config(server_id)
    return server_config.get("name", f"Server {server_id}")


def get_new_member_role_id(server_id: str) -> Optional[str]:
    """Get the new member role ID for a server"""
    return get_role_id("verified", server_id)  # Use "verified" as the default role for new members


def get_server_setting(setting_name: str, server_id: str, default: Any = False) -> Any:
    """
    Get a server-specific setting
    
    Parameters:
        setting_name: The name of the setting to get
        server_id: The server ID
        default: Default value if setting is not found
        
    Returns:
        The setting value or default if not found
    """
    server_config = get_server_config(server_id)
    
    if "settings" in server_config and setting_name in server_config["settings"]:
        return server_config["settings"][setting_name]
    
    return default


def has_management_permission(roles, server_id: str) -> bool:
    """
    Check if a member has management permission based on their roles
    
    Parameters:
        roles: List of discord.Role objects
        server_id: The ID of the server to check permissions in
        
    Returns:
        True if the member has management permission, False otherwise
    """
    try:
        # Get management role IDs for this server
        management_role_ids = get_role_ids("management", server_id)
        
        # Convert member roles to strings for comparison
        member_role_ids = [str(role.id) for role in roles]
        
        # Check if any management roles match member roles
        for role_id in management_role_ids:
            if role_id in member_role_ids:
                return True
                
        return False
    except Exception as e:
        logger.error(f"Error checking management permission: {e}", exc_info=True)
        return False


def get_message_style(style_type: str, server_id: str) -> str:
    """
    Get a random message for a specific style type and server
    
    Parameters:
        style_type: The type of message style to get (success, error, etc.)
        server_id: The server ID
        
    Returns:
        A message string in the appropriate style for the server
    """
    import random
    
    try:
        server_config = get_server_config(server_id)
        
        # Default message styles if not found
        default_styles = {
            "success": ["Success!"],
            "error": ["Error occurred. Please try again."]
        }
        
        # Check if server has message styles configured
        if "message_style" in server_config and style_type in server_config["message_style"]:
            # Get a random message from the appropriate style list
            messages = server_config["message_style"][style_type]
            if messages:
                return random.choice(messages)
        
        # If no style found or empty, use defaults
        if style_type in default_styles:
            return random.choice(default_styles[style_type])
            
        # If no default either, return a generic message
        return "Operation completed" if style_type == "success" else "Error"
        
    except Exception as e:
        logger.error(f"Error getting message style: {e}", exc_info=True)
        return "Operation completed" if style_type == "success" else "Error"


def is_command_disabled(command_name: str, server_id: str) -> bool:
    """
    Check if a command is disabled for a specific server
    
    Parameters:
        command_name: The name of the command to check
        server_id: The server ID
        
    Returns:
        True if the command is disabled, False otherwise
    """
    try:
        # Get disabled commands for this server
        disabled_commands = get_server_setting("disabled_commands", server_id, [])
        
        # Check if the command is in the disabled list
        return command_name.lower() in [cmd.lower() for cmd in disabled_commands]
        
    except Exception as e:
        logger.error(f"Error checking if command is disabled: {e}", exc_info=True)
        return False


def uses_sassy_language(server_id: str) -> bool:
    """
    Check if a server uses sassy/mommy language or professional language
    
    Parameters:
        server_id: The server ID
        
    Returns:
        True if server uses sassy language, False for professional language
    """
    return get_server_setting("use_sassy_language", server_id, True)  # Default to sassy language