import asyncio
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
    LightEntityFeature,
)
from homeassistant.const import CONF_DEVICES

from .commands import ColorTempLevelUtil, Scenes
from .const import CONF_NAME, DOMAIN, LOGGER
from .coordinator import LightCoordinator, LightState
from .entity import iLinkLightBaseEntity

light_description = LightEntityDescription(
    key="light",
    name="Light",
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    ha_entities = []

    for device_id in config_entry.data[CONF_DEVICES]:
        LOGGER.debug("Starting iLink lights: %s", config_entry.data[CONF_DEVICES])
        LOGGER.debug(
            "Starting iLink lights: %s",
            config_entry.data[CONF_DEVICES][device_id][CONF_NAME],
        )

        # Find coordinator for this device
        coordinator = hass.data[DOMAIN][CONF_DEVICES][device_id]

        # Create entities for this device
        ha_entities.append(iLinkLightEntity(coordinator, light_description))

    async_add_entities(ha_entities, True)


class iLinkLightEntity(iLinkLightBaseEntity, LightEntity):
    min_color_temp_kelvin = 3000
    max_color_temp_kelvin = 6000

    _attr_supported_color_modes = {
        ColorMode.COLOR_TEMP,
        ColorMode.RGB,
    }
    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect = None

    def __init__(
        self, coordinator: LightCoordinator, description: LightEntityDescription
    ) -> None:
        super().__init__(coordinator, description)
        self._attr_effect_list = ["100%", "Sleep"] + Scenes.all()

    @property
    def brightness(self):
        return self.coordinator.state[LightState.BRIGHTNESS]

    @property
    def color_temp_kelvin(self) -> int | None:
        return self.coordinator.state[LightState.COLORTEMP]

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color value [int, int, int]."""
        return self.coordinator.state[LightState.RGB]

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self._attr_effect

    @property
    def is_on(self) -> bool:
        return self.coordinator.state[LightState.POWER]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """turn on"""
        if not self.is_on:
            self.coordinator.state[LightState.POWER] = True
            self.async_write_ha_state()
            await self.coordinator.async_update_state(LightState.POWER, True)

        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            await self.coordinator.async_update_state(
                LightState.COLORTEMP, kwargs[ATTR_COLOR_TEMP_KELVIN]
            )
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_effect = None
        if ATTR_RGB_COLOR in kwargs:
            await self.coordinator.async_update_state(
                LightState.RGB, kwargs[ATTR_RGB_COLOR]
            )
            self._attr_color_mode = ColorMode.RGB
            self._attr_effect = None
        if ATTR_EFFECT in kwargs:
            match kwargs[ATTR_EFFECT]:
                case "100%":
                    # only sun light level 3 has the most powerfull brightness
                    await self.coordinator.async_update_state(
                        LightState.COLORTEMP, ColorTempLevelUtil.level_to_color_temp(3)
                    )
                    await asyncio.sleep(0.03)
                    await self.coordinator.async_update_state(
                        LightState.BRIGHTNESS, 255
                    )
                    self._attr_effect = kwargs[ATTR_EFFECT]
                    self._attr_color_mode = ColorMode.COLOR_TEMP
                case "Sleep":
                    await self.coordinator.async_update_state(
                        LightState.COLORTEMP, ColorTempLevelUtil.level_to_color_temp(5)
                    )
                    await asyncio.sleep(0.03)
                    await self.coordinator.async_update_state(LightState.BRIGHTNESS, 4)
                    self._attr_effect = kwargs[ATTR_EFFECT]
                    self._attr_color_mode = ColorMode.COLOR_TEMP
                case _:
                    await self.coordinator.async_update_state(
                        "scene", Scenes.name_to_id(kwargs[ATTR_EFFECT])
                    )
                    self._attr_effect = kwargs[ATTR_EFFECT]
                    self._attr_color_mode = ColorMode.RGB
        if ATTR_BRIGHTNESS in kwargs:
            await self.coordinator.async_update_state(
                LightState.BRIGHTNESS, kwargs[ATTR_BRIGHTNESS]
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """turn off"""
        if self.is_on:
            self.coordinator.state[LightState.POWER] = False
            self.async_write_ha_state()
        await self.coordinator.async_update_state(LightState.POWER, False)
