"""EcoFlow account login helper - region routing and credential probing."""

import base64
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import aiohttp

try:
    from . import cloud_signer
except ImportError:  # removable: without it, OMOS devices need a pasted device token
    cloud_signer = None


# Bind-material endpoints, tried in order: the consumer `refreshToken` path, then the
# enterprise path used by installer-provisioned devices.
_BIND_INFO_ENDPOINTS = (
    "/iot-service/user/device/refreshToken",
    "/iot-service/enterprise-device",
)


class Region(StrEnum):
    """Selectable EcoFlow API host"""

    AUTO = "auto"
    API = "api"
    API_E = "api-e"
    API_A = "api-a"
    API_J = "api-j"
    API_R = "api-r"
    API_CN = "api-cn"

    @classmethod
    def _missing_(cls, value: object) -> "Region | None":
        if isinstance(value, str):
            for member in cls:
                if member.value.lower() == value.lower():
                    return member
        return None

    @property
    def base_url(self) -> str | None:
        """Hostname for this region, or None for `AUTO`"""
        if self is Region.AUTO:
            return None
        return f"{self.value}.ecoflow.com"


@dataclass(frozen=True)
class LoginResult:
    user_id: str | None = None
    token: str | None = None
    base_url: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class DeviceBindInfo:
    """Cloud-issued material to complete an OMOS (per-device-token) BLE bind"""

    random_code: str | None = None
    user_info_en: str | None = None
    error: str | None = None


def encode_device_token(sn: str, random_code: str, user_info_en: str) -> str:
    """
    Encode bind material into the base64 blob the device-token field accepts

    Inverse of `decode_device_token`; lets the reauth flow persist freshly fetched
    cloud bind material in the same format a manually pasted token uses.
    """
    payload = json.dumps(
        {"sn": sn, "randomCode": random_code, "userInfoEn": user_info_en}
    )
    return base64.b64encode(payload.encode()).decode()


def decode_device_token(token: str) -> DeviceBindInfo:
    """
    Decode the base64 bind-token blob from the companion device-token web page

    The blob is base64(JSON) of `{sn, randomCode, userInfoEn}`. Returns a
    `DeviceBindInfo` with the bind material, or with `error` set when it cannot be
    parsed.
    """
    try:
        payload = json.loads(base64.b64decode(token, validate=True))
    except (ValueError, json.JSONDecodeError) as exc:
        return DeviceBindInfo(error=f"invalid device token: {exc}")
    random_code = payload.get("randomCode")
    user_info_en = payload.get("userInfoEn")
    if not random_code or not user_info_en:
        return DeviceBindInfo(error="device token is missing bind material")
    return DeviceBindInfo(random_code=random_code, user_info_en=user_info_en)


class EcoFlowLogin:
    """Resolve an EcoFlow user ID from credentials and a region selection"""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    @staticmethod
    def is_phone_identifier(identifier: str) -> bool:
        """Return True if identifier looks like an E.164 phone number"""
        digits = identifier.removeprefix("+").replace(" ", "")
        return digits.isdigit() and 6 <= len(digits) <= 15

    async def login(
        self,
        identifier: str,
        password: str,
        region: Region | str,
    ) -> LoginResult:
        """Resolve an EcoFlow user ID for the given identifier/password/region"""
        region = Region(region)
        identifier = identifier.strip()
        is_phone = self.is_phone_identifier(identifier)

        if region is Region.API_CN and not is_phone:
            return LoginResult(error="api-cn requires phone number, not email")

        if region is Region.AUTO:
            region = Region.API_CN if is_phone else Region.API

        assert region.base_url is not None
        return await self._try_login_at(
            region.base_url,
            identifier,
            password,
            is_phone=is_phone and region is Region.API_CN,
        )

    async def _try_login_at(
        self,
        base_url: str,
        identifier: str,
        password: str,
        *,
        is_phone: bool,
    ) -> LoginResult:
        json_payload: dict[str, Any] = {
            "scene": "IOT_APP",
            "appVersion": "1.0.0",
            "password": base64.b64encode(password.encode()).decode(),
            "oauth": {"bundleId": "com.ef.EcoFlow"},
            "userType": "ECOFLOW",
        }
        if is_phone:
            json_payload["phone"] = identifier.removeprefix("+86")
        else:
            json_payload["email"] = identifier

        async with self._session.post(
            url=f"https://{base_url}/auth/login",
            json=json_payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        ) as response:
            if not response.ok:
                return LoginResult(
                    error=(
                        f"Login failed with status code {response.status}: "
                        f"{response.reason}"
                    )
                )

            result_json = await response.json()
            if result_json["code"] != "0":
                return LoginResult(error=f"Login failed: '{result_json['message']}'")

            data = result_json["data"]
            return LoginResult(
                user_id=data["user"]["userId"],
                token=data.get("token"),
                base_url=base_url,
            )

    def _signed_headers(
        self, method: str, path: str, sorted_query: str, bearer: str
    ) -> dict[str, str]:
        assert cloud_signer is not None
        return cloud_signer.signed_headers(method, path, sorted_query, bearer)

    async def _signed_get(
        self, base_url: str, path: str, sorted_query: str, bearer: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        if cloud_signer is None:
            return None, "cloud request signing is not installed"
        headers = self._signed_headers("GET", path, sorted_query, bearer)
        url = f"https://{base_url}{path}"
        if sorted_query:
            url = f"{url}?{sorted_query}"

        async with self._session.get(url=url, headers=headers) as response:
            if not response.ok:
                return None, (f"HTTP {response.status}: {response.reason}")
            result_json = await response.json()
            if str(result_json.get("code")) != "0":
                return (
                    None,
                    f"code={result_json.get('code')}: {result_json.get('message')}",
                )
            return result_json, None

    async def verify_session(self, base_url: str, bearer: str) -> str | None:
        """Check the bearer + request signing against a device-independent endpoint"""
        _, error = await self._signed_get(
            base_url,
            "/iot-service/user/security/key",
            "scene=APP_SECURITY_KEY",
            bearer,
        )
        return error

    async def get_device_bind_info(
        self, base_url: str, bearer: str, sn: str
    ) -> DeviceBindInfo:
        """
        Fetch the cloud bind material for `sn` needed by OMOS device auth

        Consumer-owned devices answer on the app's `refreshToken` endpoint; installer-
        provisioned devices answer only on the enterprise endpoint. The endpoint a given
        device accepts is not known ahead of time, so try the consumer path first and
        fall back to the enterprise path, returning the first with usable material.
        """
        last_error: str | None = None
        for path in _BIND_INFO_ENDPOINTS:
            result_json, error = await self._signed_get(
                base_url, path, f"sn={sn}", bearer
            )
            if error is None and result_json is not None:
                data = result_json.get("data") or {}
                info = DeviceBindInfo(
                    random_code=data.get("randomCode"),
                    user_info_en=data.get("userInfoEn"),
                )
                if info.random_code and info.user_info_en:
                    return info
            last_error = error or last_error
        return DeviceBindInfo(error=last_error or "no bind material returned")
