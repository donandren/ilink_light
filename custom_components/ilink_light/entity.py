"""Base entity class for iLink Light integration."""
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LightCoordinator


class iLinkLightBaseEntity(CoordinatorEntity[LightCoordinator]):
    """iLink Light base entity class."""

    def __init__(self, coordinator: LightCoordinator, description: EntityDescription):
        super().__init__(coordinator)

        self._attr_name = f"{self.coordinator.device_name} {description.name}"
        self._attr_unique_id = f"{self.coordinator.address}-{self.name}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.coordinator.address)},
        }
