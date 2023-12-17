import asyncio
import datetime as dt
import functools
from enum import StrEnum

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
)
from homeassistant.core import HassJob, HassJobType
from homeassistant.helpers import device_registry, event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .commands import ColorTempLevelUtil, ResponseStatus
from .const import (
    LOGGER,
    CONF_MAC,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL_FAST,
)
from .light_bt_client import LightBtClient


class LightState(StrEnum):
    """color temp 1-5"""

    COLORTEMP = ATTR_COLOR_TEMP_KELVIN
    """rgb color rrggbb in hex"""
    RGB = ATTR_RGB_COLOR
    """dim of the light 0-100%"""
    BRIGHTNESS = ATTR_BRIGHTNESS
    """power true or false"""
    POWER = "power"


class LightCoordinator(DataUpdateCoordinator):
    _fast_poll_count = 0
    _normal_poll_interval = 60
    _fast_poll_interval = 10
    _initialized = False
    _request_status_update = True
    _unsub_update_state: event.CALLBACK_TYPE | None = None
    _concurent_update_state = 0

    def __init__(self, hass, device_id, conf):
        self.device_id = device_id
        self.device_name = conf[CONF_NAME]
        self.address = conf[CONF_MAC]
        self._normal_poll_interval = int(conf[CONF_SCAN_INTERVAL])
        self._fast_poll_interval = int(conf[CONF_SCAN_INTERVAL_FAST])

        """Initialize coordinator parent"""
        super().__init__(
            hass,
            LOGGER,
            name="iLink Light: " + self.device_name,
            # let's give at least 30 seconds for initial connect to device
            update_interval=dt.timedelta(seconds=30),
            update_method=self.async_update,
        )

        self._client = LightBtClient(hass, self.address, self._client_status_updated)

        # Initialize state in case of new integration
        self.data = {}
        self.data[LightState.COLORTEMP] = 4000
        self.data[LightState.BRIGHTNESS] = 255
        self.data[LightState.POWER] = True
        self.data[LightState.RGB] = (0xFF, 0xFF, 0xFF)

    async def _client_status_updated(self, status: ResponseStatus) -> None:
        self.data[LightState.COLORTEMP] = ColorTempLevelUtil.level_to_color_temp(
            status.temp_level
        )
        self.data[LightState.BRIGHTNESS] = status.brightness
        self.data[LightState.POWER] = status.on
        self.data[LightState.RGB] = status.rgb

        self._request_status_update = False
        self.async_set_updated_data(self.data)

    def _set_poll_mode(self, fast: bool):
        self._fast_poll_count = 0 if fast else -1
        interval = self._fast_poll_interval if fast else self._normal_poll_interval
        self.update_interval = dt.timedelta(seconds=interval)
        self._schedule_refresh()

    def _update_poll(self):
        if self._fast_poll_count > -1:
            self._fast_poll_count += 1
            if self._fast_poll_count > 1:
                self._set_poll_mode(fast=False)

    async def _disconnect(self):
        await self._client.disconnect()

    async def async_update(self):
        # skip update if we are sending commands right now
        if self._client.busy:
            self._set_poll_mode(fast=True)
            return self.data

        self._update_poll()

        if not self._initialized:
            await self._initialize()

        try:
            if (not self._client.waiting_status_update) or self._request_status_update:
                if await self._client.connect():
                    await self._client.request_status_update()

            # do not keep constant connection to the device
            await self._disconnect()
        finally:
            # next time update status
            self._request_status_update = True

        return self.data

    async def _initialize(self):
        try:
            if self._client.service_info is not None:
                self._initialized = True
                reg = device_registry.async_get(self.hass)
                reg.async_update_device(
                    self.device_id,
                    name=self._client.service_info.name,
                    manufacturer=self._client.device_manifacturer,
                    hw_version=self._client.device_version,
                )
        except Exception as e:
            LOGGER.warning("Failed to initialize %s: %s", self.address, str(e))

    @property
    def state(self) -> dict:
        return self.data

    async def async_update_state(self, key: LightState, value) -> bool:
        if self._unsub_update_state:
            self._unsub_update_state()
            self._unsub_update_state = None

        if self._client.busy:
            job = HassJob(
                functools.partial(self._async_update_state_debounced, key, value),
                "async_update_state",
                job_type=HassJobType.Coroutinefunction,
            )
            # delay a bit so we don't flood too many messages too quickly
            self._unsub_update_state = event.async_call_later(
                self.hass, dt.timedelta(seconds=1), job
            )
            self._concurent_update_state += 1
            if self._concurent_update_state > 9:
                # 1/10 let's make try to call it anyway
                # at least user will be notified in case of error
                self._concurent_update_state = 0
                raise RuntimeError(
                    "Not able to send Command - device is busy! Try again later!"
                )
        else:
            await self._async_update_state(key, value)

    async def _async_update_state_debounced(self, date, key: LightState, value) -> bool:
        self._unsub_update_state = None
        self._concurent_update_state = 0
        LOGGER.debug(
            "_async_update_state_debounced date:%s, %s - %s", date, key, value
        )
        await self._async_update_state(key, value)

    async def _async_update_state(self, key: LightState, value) -> bool:
        self._request_status_update = True
        await self.ensure_connected()

        # Write data back
        match key:
            case LightState.BRIGHTNESS:
                await self._client.set_brightness(int(value))
            case LightState.COLORTEMP:
                kelvin = int(value)
                level = ColorTempLevelUtil.color_temp_to_level(kelvin)
                value = ColorTempLevelUtil.level_to_color_temp(level)
                await self._client.set_white_temp(level)
                await asyncio.sleep(0.03)
                await self._client.set_brightness(
                    int(self.state[LightState.BRIGHTNESS])
                )
            case LightState.RGB:
                await self._client.set_rgb(value[0], value[1], value[2])
                await asyncio.sleep(0.03)
                # set brightness again as it's lost when color is set
                await self._client.set_brightness(
                    int(self.state[LightState.BRIGHTNESS])
                )
            case LightState.POWER:
                if value:
                    await self._client.turn_on()
                else:
                    await self._client.turn_off()
            case "scene":
                await self._client.set_scene(int(value))
            case _:
                return False

        self.state[key] = value

        LOGGER.info("async_update_state: %s - %s", key, value)

        self.async_set_updated_data(self.state)
        self._set_poll_mode(fast=True)

        return True

    async def ensure_connected(self):
        # Make sure we are connected
        if not await self._client.connect():
            raise ConnectionError("Not connected!")

    async def async_shutdown(self) -> None:
        await self._client.disconnect(force=True)
        await super().async_shutdown()
