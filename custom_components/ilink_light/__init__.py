"""Support for iLink lights."""


from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from .const import LOGGER, CONF_MAC, CONF_NAME, DOMAIN, PLATFORMS
from .coordinator import LightCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Set up platform from a ConfigEntry."""
    LOGGER.debug("Setting up configuration for iLink lights!")
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][CONF_DEVICES] = {}

    # Create one coordinator for each device
    for device_id in entry.data[CONF_DEVICES]:
        conf = entry.data[CONF_DEVICES][device_id]

        # Create device
        device_registry = dr.async_get(hass)
        device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, conf[CONF_MAC])},
            name=conf[CONF_NAME],
        )

        # Set up coordinator
        coordinator = LightCoordinator(hass, device.id, conf)
        hass.data[DOMAIN][CONF_DEVICES][device_id] = coordinator

    # Forward the setup to the platforms.
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    )

    # Set up options listener
    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


# Example migration function
async def async_migrate_entry(hass, config_entry: ConfigEntry):
    if config_entry.version == 1:
        LOGGER.error(
            "Sorry you have an old configuration, please remove and add again!"
        )
        return False

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    LOGGER.debug("Updating iLink Light BLE entry!")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    LOGGER.debug("Unloading iLink Light BLE entry!")

    for dev_id, coordinator in hass.data[DOMAIN][CONF_DEVICES].items():
        await coordinator.async_shutdown()

    # Unload entries
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove entities and device from HASS"""
    device_id = device_entry.id
    ent_reg = er.async_get(hass)
    reg_entities = {}
    for ent in er.async_entries_for_config_entry(ent_reg, config_entry.entry_id):
        if device_id == ent.device_id:
            reg_entities[ent.unique_id] = ent.entity_id
    for entity_id in reg_entities.values():
        ent_reg.async_remove(entity_id)
    dev_reg = dr.async_get(hass)
    dev_reg.async_remove_device(device_id)

    """Remove from config_entry"""
    devices = []
    for dev_id, dev_config in config_entry.data[CONF_DEVICES].items():
        if dev_config[CONF_NAME] == device_entry.name:
            devices.append(dev_config[CONF_MAC])

    new_data = config_entry.data.copy()
    for dev in devices:
        # Remove device from config entry
        new_data[CONF_DEVICES].pop(dev)
    hass.config_entries.async_update_entry(config_entry, data=new_data)
    hass.config_entries._async_schedule_save()

    return True
