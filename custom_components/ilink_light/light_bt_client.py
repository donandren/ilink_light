import asyncio
from typing import Awaitable, Callable

import async_timeout
from bleak import BleakClient, BleakGATTCharacteristic, BLEDevice
from bleak.exc import BleakError
from home_assistant_bluetooth import BluetoothServiceInfoBleak

from homeassistant.components import bluetooth

from .commands import (
    CHARACTERISTIC_REQUEST_STATUS,
    CHARACTERISTIC_SEND_CMD,
    Commands,
    Response,
    ResponseStatus,
)
from .const import LOGGER


class LightBtClient:
    service_info: BluetoothServiceInfoBleak | None = None
    device_manifacturer: str | None = None
    device_version: str | None = None
    _status = None
    _callback = None
    _current_connect = None
    waiting_status_update = False
    _disconnect_next = False
    _busy = False
    _connecting = False
    _ble_device: BLEDevice | None = None

    def __init__(
        self,
        hass,
        address,
        callback: Callable[[ResponseStatus], Awaitable[None]] = None,
    ):
        self._hass = hass
        self._bt_client = None
        self._address = address
        self._send_command_err_count = 0
        # self.device_manifacturer = None
        self._callback = callback

    @property
    def busy(self):
        return self._connecting or (self._busy and self.is_connected())

    async def _notification_handler(
        self, characteristic: BleakGATTCharacteristic, data: bytearray
    ):
        LOGGER.debug(
            "_notification_handler received %s: %s: %s - %r",
            self._address,
            characteristic.description,
            data.hex(),
            data,
        )

        if Response.is_status(data):
            status = Response.parse_status(data)
            LOGGER.info("status received %s: %s", self._address, vars(status))
            self._status = status
            if self._callback:
                await self._callback(status)
            self.waiting_status_update = False

        await self.disconnect(only_if_needed=True)

    async def _initialize(self) -> None:
        try:
            self._busy = False
            self.waiting_status_update = False
            self._disconnect_next = False
            self.service_info = bluetooth.async_last_service_info(
                self._hass, self._address, connectable=True
            )

            if self.service_info and self.service_info.manufacturer_data:
                LOGGER.debug(
                    "_initialize %s service_info.adv: %s",
                    self._address,
                    self.service_info.advertisement,
                )
                md = self.service_info.manufacturer_data
                if value := md.get(5101, None):
                    self.device_version = f"{value[0]}.{value[1]}.{value[2]}.{value[3]}"
                if value := md.get(1494, None):
                    self.device_manifacturer = value.decode("ascii") or None

            await self._bt_client.start_notify(
                CHARACTERISTIC_REQUEST_STATUS, self._notification_handler
            )

            if self.status is None:
                await self.request_status_update()

            LOGGER.debug("initialized %s", self._address)
        except Exception as e:
            LOGGER.warning("initialize error: %s", str(e), exc_info=e)

    async def connect(self, retries=3) -> bool:
        try:
            if self._current_connect is None:
                self._current_connect = self._connect(retries)
            result = await self._current_connect
            return result
        finally:
            self._current_connect = None

    async def _connect(self, retries=3) -> bool:
        if self.is_connected():
            return True
        if self._connecting:
            return False

        tries = 0
        self._connecting = True

        LOGGER.debug("Connecting to %s", self._address)
        while tries < retries:
            tries += 1

            try:
                if self._bt_client is None:
                    ble_device = bluetooth.async_ble_device_from_address(
                        self._hass, self._address.upper()
                    )
                    if ble_device:
                        self._ble_device = ble_device
                    if not self._ble_device:
                        raise BleakError(
                            f"A device with address {self._address} could not be found."
                        )
                    self._bt_client = BleakClient(self._ble_device)
                ret = await self._bt_client.connect()
                if ret:
                    LOGGER.debug("Connected to %s", self._address)
                    await self._initialize()
                    break
            except Exception as e:
                if tries == retries:
                    LOGGER.info("Not able to connect to %s! %s", self._address, str(e))
                else:
                    LOGGER.debug("Retrying %s", self._address)
                    await asyncio.sleep(1)
        self._connecting = False
        return self.is_connected()

    async def disconnect(
        self, force: bool = False, only_if_needed: bool = False
    ) -> None:
        if not force:
            if self.busy or self.waiting_status_update:
                self._disconnect_next = True
                return
            elif only_if_needed and not self._disconnect_next:
                return

        self.waiting_status_update = False
        self._busy = False
        self._disconnect_next = False

        if self.is_connected():
            try:
                LOGGER.debug("disconnecting %s", self._address)
                await self._bt_client.disconnect()
            except Exception as e:
                LOGGER.warning("Error disconnecting %s! %s", self._address, str(e))
            if self.status is None:
                self._bt_client = None

    @property
    def status(self) -> ResponseStatus | None:
        return self._status

    def is_connected(self) -> bool:
        return self._bt_client is not None and self._bt_client.is_connected

    async def _write_uuid(self, uuid, val) -> None:
        if self._busy:
            raise RuntimeError("device busy")
        try:
            self._busy = True
            await self._bt_client.write_gatt_char(
                char_specifier=uuid, data=val, response=True
            )
        finally:
            self._busy = False
            await self.disconnect(only_if_needed=True)

    async def _send_command(self, command: str) -> None:
        LOGGER.debug("send command %s: %s", self._address, command)
        try:
            async with async_timeout.timeout(1):
                await self._write_uuid(CHARACTERISTIC_SEND_CMD, bytes.fromhex(command))
            self._send_command_err_count = 0
            # command is exected immediatelly, but client sometime waits for 10 seconds
            # so we don't have any result anyway and no need to wait
        except Exception as e:
            self._send_command_err_count += 1
            if self._send_command_err_count > 10:
                LOGGER.info(
                    "%s errors occurred in send command %s! Last: %s",
                    self._send_command_err_count,
                    self._address,
                    str(e),
                )
                self._send_command_err_count = 0

    async def request_status_update(self) -> None:
        self.waiting_status_update = True
        LOGGER.debug("request_status_update %s", self._address)
        await self._send_command(Commands.status())

    async def set_brightness(self, value: int) -> None:
        if value < 0 or value > 0xFF:
            raise ValueError("Brightness must be between 0 and 255")

        LOGGER.debug("set_brightness: %s", value)
        await self._send_command(Commands.brightness(value))

    async def set_white_temp(self, value: int) -> None:
        if value < 1 or value > 5:
            raise ValueError("White temperature must be between 1 and 5")

        LOGGER.debug("set_white_temp: %s", value)
        await self._send_command(Commands.white_temp(value))

    async def set_rgb(self, r: int, g: int, b: int) -> None:
        if r < 0 or r > 0xFF or g < 0 or g > 0xFF or b < 0 or b > 0xFF:
            raise ValueError("RGB values must be between 0 and 255")

        LOGGER.debug("set_rgb: %s %s %s", r, g, b)
        await self._send_command(Commands.rgb(r, g, b))

    async def set_scene(self, value: int) -> None:
        if value < 1 or value > 93:
            raise ValueError("Scene must be between 1 and 93")

        LOGGER.debug("set_scene: %s", value)
        await self._send_command(Commands.scene(value))

    async def turn_on(self) -> None:
        LOGGER.debug("turn_on")
        await self._send_command(Commands.on())

    async def turn_off(self) -> None:
        LOGGER.debug("turn_off")
        await self._send_command(Commands.off())
