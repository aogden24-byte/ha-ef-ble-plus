import importlib
import sys

import pytest

from custom_components.ef_ble_plus import eflib
from custom_components.ef_ble_plus.eflib import login


@pytest.fixture
def login_without_signer(monkeypatch):
    # Simulates the module having been deleted from the install
    monkeypatch.setitem(
        sys.modules, "custom_components.ef_ble_plus.eflib.cloud_signer", None
    )
    monkeypatch.delattr(eflib, "cloud_signer", raising=False)
    reloaded = importlib.reload(login)
    yield reloaded
    monkeypatch.undo()
    importlib.reload(login)


async def test_bind_info_reports_error_when_signer_is_removed(login_without_signer):
    client = login_without_signer.EcoFlowLogin(session=None)

    info = await client.get_device_bind_info("api.example", "Bearer x", "HR61XX")

    assert info.error == "cloud request signing is not installed"
    assert info.random_code is None
