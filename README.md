# EF BLE Plus

Local Bluetooth support in Home Assistant for EcoFlow-compatible devices that the [EcoFlow
BLE](https://github.com/rabits/ha-ef-ble) integration does not cover. It installs **alongside** that
integration: each device is handled by exactly one of the two.

> Unofficial. Not affiliated with or endorsed by EcoFlow.

## Supported devices

| Device | Serial prefix | Notes |
|---|---|---|
| OCEAN Pro inverter | `HR51` | Battery, grid, PCS legs, PV1-8 strings |
| OCEAN Panel | `HR61`, `HR6B`, `HR6D` | 40 circuits, PV1-8 via the inverter, external PV power |
| STREAM Microinverter (US, four inputs) | `BK06` | PV1-4 |

Everything else (Delta, River, PowerStream, Smart Home Panels, other STREAM models) stays in the
upstream integration.

## Installation

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/aogden24-byte/ha-ef-ble-plus` as an
   **Integration**.
2. Download **EF BLE Plus** and restart Home Assistant.
3. Settings → Devices & services → **Add integration** → EF BLE Plus, or accept the discovered
   device.

If you previously ran these devices through a patched copy of `ef_ble`, remove them there first: a
device can only hold one Bluetooth link.

## OCEAN authentication (device token)

OCEAN devices use per-device token authentication. During setup, expand **EcoFlow Login** and enter
the account the device is bound to; the integration fetches the token for you and, if you choose to
store the credentials, renews it when it expires. Installer-provisioned systems are supported (the
enterprise endpoint is tried after the consumer one).

Account-free alternative: paste a device token into the **Device token** field instead.

The cloud request signing used for the token lives entirely in
`custom_components/ef_ble_plus/eflib/cloud_signer.py`. Deleting that file disables the login-based
token fetch and nothing else; pasted tokens keep working.

## Contributing

New devices that upstream does not support are welcome. Each mapping needs evidence from a real
device capture. Run before a pull request:

```bash
uv run pytest tests/eflib
uvx prek run --all-files
```

## Credits and licence

Derived from [ha-ef-ble](https://github.com/rabits/ha-ef-ble) by rabits, GnoX and contributors,
under the Apache License 2.0. See `LICENSE` and `NOTICE`.
