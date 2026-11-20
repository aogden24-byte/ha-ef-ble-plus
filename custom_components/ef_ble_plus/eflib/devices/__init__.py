import importlib
from types import ModuleType
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from ..devicebase import DeviceBase

    class ModuleWithDevice(Protocol):
        Device: type[DeviceBase]


# Only the devices the upstream EcoFlow BLE integration does not support are claimed,
# so the two integrations can be installed side by side without competing for a
# device. The other modules stay because the shared base classes and platform code
# import them.
__all__ = ["ocean_panel", "ocean_pro", "stream_microinverter_us"]

devices: list["ModuleWithDevice | ModuleType"] = [
    importlib.import_module(f".{device}", __name__) for device in __all__
]
