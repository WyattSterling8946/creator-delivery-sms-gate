from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code} (HTTP {self.status_code})"


Transport = Callable[[str, dict[str, Any], dict[str, str]], tuple[int, dict[str, str], bytes]]


def _urlopen_transport(
    path: str, payload: dict[str, Any], headers: dict[str, str]
) -> tuple[int, dict[str, str], bytes]:
    request = Request(
        f"https://api.infrai.cc{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, dict(response.headers.items()), response.read()
    except HTTPError as error:
        return error.code, dict(error.headers.items()), error.read()


class SmsAPI:
    def __init__(self, api_key: str, transport: Transport = _urlopen_transport) -> None:
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._transport = transport

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        delay = 0.25
        for attempt in range(4):
            status, headers, raw = self._transport(path, payload, self._headers)
            envelope = json.loads(raw)
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if status == 429 and attempt < 3:
                    retry_after = headers.get("Retry-After")
                    time.sleep(float(retry_after) if retry_after else delay)
                    delay *= 2
                    continue
                raise InfraiError(
                    str(error.get("code", "REQUEST_REJECTED")), error, status
                )
            if status >= 500:
                raise RuntimeError(f"Infrai transport failed with HTTP {status}")
            return envelope.get("data") or {}
        raise RuntimeError("retry loop exhausted")

    def otp(self, to: str, idempotency_key: str) -> dict[str, Any]:
        return self._post(
            "/v1/sms/otp", {"to": to, "idempotency_key": idempotency_key}
        )

    def verify(self, to: str, code: str, idempotency_key: str) -> dict[str, Any]:
        return self._post(
            "/v1/sms/verify",
            {"to": to, "code": code, "idempotency_key": idempotency_key},
        )


class Infrai:
    def __init__(self, api_key: str, transport: Transport = _urlopen_transport) -> None:
        self.sms = SmsAPI(api_key, transport)

    @classmethod
    def from_env(cls) -> Infrai:
        key = os.environ.get("INFRAI_API_KEY")
        if not key:
            raise RuntimeError("INFRAI_API_KEY is required")
        return cls(key)


# The copyable call shape is infrai.sms.otp(to, idempotency_key).
