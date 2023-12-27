"""Config flow to configure iLink lights integration"""
from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_DEVICES
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    selector,
)

from .const import (
    LOGGER,
    CONF_ACTION,
    CONF_ADD_DEVICE,
    CONF_EDIT_DEVICE,
    CONF_MAC,
    CONF_NAME,
    CONF_REMOVE_DEVICE,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL_FAST,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_FAST,
    DOMAIN,
)
from .light_bt_client import LightBtClient

CONFIG_ENTRY_NAME = "iLink Light"
SELECTED_DEVICE = "selected_device"

DEVICE_DATA = {
    CONF_NAME: "",
    CONF_MAC: "",
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL_FAST: DEFAULT_SCAN_INTERVAL_FAST,
}


class iLinkLightConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self):
        self.device_data = DEVICE_DATA.copy()  # Data of "current" device
        self.config_entry = None

    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return iLinkLightOptionsFlowHandler(config_entry)

    def get_ilink_light_config_entry(self, entry_title: str) -> ConfigEntry:
        if self.hass is not None:
            config_entries = self.hass.config_entries.async_entries(DOMAIN)
            for entry in config_entries:
                if entry.title == entry_title:
                    return entry

    def device_exists(self, device_key: str) -> bool:
        self.config_entry = self.get_ilink_light_config_entry(CONFIG_ENTRY_NAME)
        if self.config_entry is not None:
            if CONF_DEVICES in self.config_entry.data:
                if device_key in self.config_entry.data[CONF_DEVICES]:
                    return True
        return False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user, adding the integration."""
        errors = {}

        """Only one instance of the integration is allowed"""
        await self.async_set_unique_id(CONFIG_ENTRY_NAME)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=CONFIG_ENTRY_NAME, data={CONF_DEVICES: {}})

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle a flow initialized by bluetooth discovery."""
        LOGGER.info("Discovered device: %s", discovery_info.address)
        self.device_data[CONF_MAC] = dr.format_mac(discovery_info.address)

        """Abort if we already have a discovery in process for this device"""
        await self.async_set_unique_id(self.device_data[CONF_MAC])
        self._abort_if_unique_id_configured()

        """Abort if this device is already configured"""
        if self.device_exists(self.device_data[CONF_MAC]):
            LOGGER.info("Aborting because device exists!")
            return self.async_abort(
                reason="device_already_configured",
                description_placeholders={"dev_name": self.device_data[CONF_MAC]},
            )

        return await self.async_step_add_device()

    """##################################################
    ##################### ADD DEVICE ####################
    ##################################################"""

    async def async_step_add_device(self, user_input=None):
        """Handler for adding discovered device."""
        errors = {}

        if user_input is not None:
            if self.device_exists(dr.format_mac(user_input[CONF_MAC])):
                return self.async_abort(
                    reason="device_already_configured",
                    description_placeholders={"dev_name": user_input[CONF_MAC]},
                )

            light_client = LightBtClient(self.hass, user_input[CONF_MAC])

            if await light_client.connect():
                verified = light_client.is_connected()
                await light_client.disconnect(force=True)

                if verified:
                    """Make sure integration is installed"""
                    self.config_entry = self.get_ilink_light_config_entry(
                        CONFIG_ENTRY_NAME
                    )
                    if self.config_entry is None:
                        # No integration installed, add entry with new device
                        await self.async_set_unique_id(CONFIG_ENTRY_NAME)
                        new_data = {CONF_DEVICES: {}}
                        new_data[CONF_DEVICES][user_input[CONF_MAC]] = user_input
                        LOGGER.debug("Creating config entry: %s", new_data)

                        return self.async_create_entry(
                            title=CONFIG_ENTRY_NAME,
                            data=new_data,
                            description_placeholders={
                                "dev_name": new_data[CONF_DEVICES][
                                    user_input[CONF_MAC]
                                ][CONF_NAME]
                            },
                        )
                    else:
                        # Integration found, update with new device
                        new_data = self.config_entry.data.copy()
                        new_data[CONF_DEVICES][user_input[CONF_MAC]] = user_input

                        self.hass.config_entries.async_update_entry(
                            self.config_entry, data=new_data
                        )
                        self.hass.config_entries._async_schedule_save()

                        await self.hass.config_entries.async_reload(
                            self.config_entry.entry_id
                        )

                        return self.async_abort(
                            reason="add_success",
                            description_placeholders={
                                "dev_name": user_input[CONF_NAME]
                            },
                        )
                else:
                    errors["base"] = "cannot_connect"
                    # Store values for new attempt
                    self.device_data = user_input
            else:
                errors["base"] = "cannot_connect"
                # Store values for new attempt
                self.device_data = user_input

        data_schema = getDeviceSchemaAdd(self.device_data)
        return self.async_show_form(
            step_id="add_device", data_schema=data_schema, errors=errors
        )


class iLinkLightOptionsFlowHandler(OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry
        self.selected_device = None  # Mac address / key
        self.device_data = DEVICE_DATA.copy()  # Data of "current" device

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        # Manage the options for the custom component."""

        if user_input is not None:
            if user_input.get(CONF_ACTION) == CONF_ADD_DEVICE:
                return await self.async_step_add_device()
            if user_input.get(CONF_ACTION) == CONF_EDIT_DEVICE:
                return await self.async_step_select_edit_device()
            if user_input.get(CONF_ACTION) == CONF_REMOVE_DEVICE:
                return await self.async_step_remove_device()

        return self.async_show_form(step_id="init", data_schema=CONFIGURE_SCHEMA)

    def device_exists(self, device_key) -> bool:
        if device_key in self.config_entry.data[CONF_DEVICES]:
            return True
        return False

    """##################################################
    ##################### ADD DEVICE ####################
    ##################################################"""

    async def async_step_add_device(self, user_input=None):
        """Handler for adding device."""
        errors = {}

        if user_input is not None:
            if self.device_exists(dr.format_mac(user_input[CONF_MAC])):
                return self.async_abort(
                    reason="already_configured",
                    description_placeholders={
                        "dev_name": user_input[CONF_MAC],
                    },
                )

            light_client = LightBtClient(self.hass, user_input[CONF_MAC])

            if await light_client.connect():
                verified = light_client.is_connected()
                await light_client.disconnect()

                if verified:
                    # Add device to config entry
                    new_data = self.config_entry.data.copy()
                    new_data[CONF_DEVICES][user_input[CONF_MAC]] = user_input

                    self.hass.config_entries.async_update_entry(
                        self.config_entry, data=new_data
                    )
                    self.hass.config_entries._async_schedule_save()
                    await self.hass.config_entries.async_reload(
                        self.config_entry.entry_id
                    )

                    return self.async_abort(
                        reason="add_success",
                        description_placeholders={
                            "dev_name": new_data[CONF_DEVICES][user_input[CONF_MAC]][
                                CONF_NAME
                            ],
                        },
                    )
                else:
                    errors["base"] = "cannot_connect"
                    # Store values for new attempt
                    self.device_data = user_input
            else:
                errors["base"] = "cannot_connect"
                # Store values for new attempt
                self.device_data = user_input

        data_schema = getDeviceSchemaAdd(self.device_data)
        return self.async_show_form(
            step_id="add_device", data_schema=data_schema, errors=errors
        )

    """##################################################
    ################# SELECT EDIT DEVICE ################
    ##################################################"""

    async def async_step_select_edit_device(self, user_input=None):
        """Handler for selecting device to edit."""
        errors = {}

        if user_input is not None:
            self.selected_device = user_input[SELECTED_DEVICE]
            self.device_data = self.config_entry.data[CONF_DEVICES][
                self.selected_device
            ]

            return await self.async_step_edit_device()

        devices = {}
        for dev_id, dev_config in self.config_entry.data[CONF_DEVICES].items():
            devices[dev_id] = dev_config[CONF_NAME]

        return self.async_show_form(
            step_id="select_edit_device",
            data_schema=getDeviceSchemaSelect(devices),
            errors=errors,
        )

    """##################################################
    #################### EDIT DEVICE ###################
    ##################################################"""

    async def async_step_edit_device(self, user_input=None):
        """Handler for inputting new data for device."""
        errors = {}

        if user_input is not None:
            # Update device in config entry
            new_data = self.config_entry.data.copy()
            new_data[CONF_DEVICES][self.selected_device][
                CONF_SCAN_INTERVAL
            ] = user_input[CONF_SCAN_INTERVAL]
            new_data[CONF_DEVICES][self.selected_device][
                CONF_SCAN_INTERVAL_FAST
            ] = user_input[CONF_SCAN_INTERVAL_FAST]

            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            self.hass.config_entries._async_schedule_save()
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            return self.async_abort(
                reason="edit_success",
                description_placeholders={
                    "dev_name": new_data[CONF_DEVICES][self.selected_device][CONF_NAME]
                },
            )

        return self.async_show_form(
            step_id="edit_device",
            data_schema=getDeviceSchemaEdit(self.device_data),
            errors=errors,
            description_placeholders={
                "dev_name": self.config_entry.data[CONF_DEVICES][self.selected_device][
                    CONF_NAME
                ]
            },
        )

    """##################################################
    #################### REMOVE DEVICE ##################
    ##################################################"""

    async def async_step_remove_device(self, user_input=None):
        """Handler for selecting device to remove."""
        errors = {}

        if user_input is not None:
            self.selected_device = user_input[SELECTED_DEVICE]
            self.device_data = self.config_entry.data[CONF_DEVICES][
                self.selected_device
            ]

            # Remove device from config entry
            new_data = self.config_entry.data.copy()
            new_data[CONF_DEVICES].pop(self.selected_device)

            await self.async_remove_device(
                self.config_entry.entry_id, self.selected_device
            )
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            self.hass.config_entries._async_schedule_save()

            return self.async_abort(
                reason="remove_success",
                description_placeholders={"dev_name": self.device_data[CONF_NAME]},
            )

        devices = {}
        for dev_id, dev_config in self.config_entry.data[CONF_DEVICES].items():
            devices[dev_id] = dev_config[CONF_NAME]

        return self.async_show_form(
            step_id="remove_device",
            data_schema=getDeviceSchemaSelect(devices),
            errors=errors,
        )

    async def async_remove_device(self, entry_id, mac) -> None:
        """Remove device"""
        device_id = None
        dev_reg = dr.async_get(self.hass)
        dev_entry = dev_reg.async_get_device({(DOMAIN, mac)})
        if dev_entry is not None:
            device_id = dev_entry.id
            dev_reg.async_remove_device(device_id)

        """Remove entities"""
        ent_reg = er.async_get(self.hass)
        reg_entities = {}
        for ent in er.async_entries_for_config_entry(ent_reg, entry_id):
            if device_id == ent.device_id:
                reg_entities[ent.unique_id] = ent.entity_id
        for entity_id in reg_entities.values():
            ent_reg.async_remove(entity_id)


""" ################################################### """
"""                      Static schemas                 """
""" ################################################ """

CONF_ACTIONS = [CONF_ADD_DEVICE, CONF_EDIT_DEVICE, CONF_REMOVE_DEVICE]
CONFIGURE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACTION): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=CONF_ACTIONS, translation_key=CONF_ACTION
            ),
        )
    }
)

""" ################################################### """
"""                     Dynamic schemas                 """
""" ################################################### """


# Schema taking device details when adding
def getDeviceSchemaAdd(user_input: dict[str, Any] | None = None) -> vol.Schema:
    data_schema = vol.Schema(
        {
            vol.Required(
                CONF_NAME, description="Name", default=user_input[CONF_NAME]
            ): cv.string,
            vol.Required(
                CONF_MAC, description="MAC Address", default=user_input[CONF_MAC]
            ): cv.string,
            vol.Optional(
                CONF_SCAN_INTERVAL, default=user_input[CONF_SCAN_INTERVAL]
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=999)),
            vol.Optional(
                CONF_SCAN_INTERVAL_FAST, default=user_input[CONF_SCAN_INTERVAL_FAST]
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=999)),
        }
    )

    return data_schema


# Schema taking device details when editing
def getDeviceSchemaEdit(user_input: dict[str, Any] | None = None) -> vol.Schema:
    data_schema = vol.Schema(
        {
            vol.Optional(
                CONF_SCAN_INTERVAL, default=user_input[CONF_SCAN_INTERVAL]
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=999)),
            vol.Optional(
                CONF_SCAN_INTERVAL_FAST, default=user_input[CONF_SCAN_INTERVAL_FAST]
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=999)),
        }
    )

    return data_schema


# Schema for selecting device to edit
def getDeviceSchemaSelect(devices: dict[str, Any] | None = None) -> vol.Schema:
    schema_devices = {}
    for dev_key, dev_name in devices.items():
        schema_devices[dev_key] = f"{dev_name} ({dev_key})"

    data_schema = vol.Schema({vol.Required(SELECTED_DEVICE): vol.In(schema_devices)})

    return data_schema
