import logging

from homeassistant.const import Platform

# Global Constants
DOMAIN: str = "ilink_light"
PLATFORMS = [Platform.LIGHT]

# Configuration Constants
CONF_ACTION = "action"
CONF_ADD_DEVICE = "add_device"
CONF_EDIT_DEVICE = "edit_device"
CONF_REMOVE_DEVICE = "remove_device"

# Configuration Device Constants
CONF_NAME: str = "name"
CONF_MAC: str = "mac"
CONF_SCAN_INTERVAL: str = "scan_interval"
CONF_SCAN_INTERVAL_FAST: str = "scan_interval_fast"

# Defaults
DEFAULT_SCAN_INTERVAL: int = 300  # Seconds
DEFAULT_SCAN_INTERVAL_FAST: int = 5  # Seconds

LOGGER = logging.getLogger(__package__)
