from __future__ import annotations

import json
import time
from typing import Any, Mapping, Optional

import requests

from steamcommunitykit.constants import DEFAULT_TIMEOUT, DEFAULT_USER_AGENT, RETRYABLE_STATUSES
from steamcommunitykit.exceptions import (
    SteamAPIError,
    SteamAuthenticationError,
    SteamHTTPError,
    SteamNetworkError,
    SteamNotFoundError,
    SteamRateLimitError,
    SteamResponseError,
)
from steamcommunitykit.models import CommunityCredentials


class SteamHTTPTransport:
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        session: Optional[requests.Session] = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        user_agent: str = DEFAULT_USER_AGENT,
        community_credentials: Optional[CommunityCredentials] = None,
    ) -> None:
        self.api_key = api_key
        self.session = session or requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.community_credentials = community_credentials
        self.session.headers.setdefault("User-Agent", user_agent)

    def close(self) -> None:
        self.session.close()

    def require_community_credentials(self) -> CommunityCredentials:
        if self.community_credentials is None:
            raise SteamAuthenticationError(
                "Community credentials are required for this operation.",
                status_code=401,
            )
        return self.community_credentials

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        data: Optional[Any] = None,
        json_body: Optional[Any] = None,
        headers: Optional[Mapping[str, str]] = None,
        cookies: Optional[Mapping[str, str]] = None,
        require_api_key: bool = False,
        service_payload: Optional[Mapping[str, Any]] = None,
        expected: str = "json",
    ) -> Any:
        request_params = dict(params or {})

        if require_api_key:
            if not self.api_key:
                raise SteamAuthenticationError(
                    "This endpoint requires a Steam Web API key.",
                    status_code=401,
                )
            request_params.setdefault("key", self.api_key)

        if expected == "json":
            request_params.setdefault("format", "json")

        if service_payload is not None:
            request_params["input_json"] = json.dumps(service_payload, separators=(",", ":"))

        last_error = None  # type: Optional[Exception]
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=request_params,
                    data=data,
                    json=json_body,
                    headers=headers,
                    cookies=cookies,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise SteamNetworkError(str(exc)) from exc
                time.sleep(self.backoff_factor * (attempt + 1))
                continue

            if response.status_code in RETRYABLE_STATUSES and attempt < self.max_retries:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else self.backoff_factor * (attempt + 1)
                time.sleep(delay)
                continue

            if response.status_code >= 400:
                self._raise_for_response(response)

            if expected == "text":
                return response.text
            if expected == "raw":
                return response
            if not response.content:
                return {}

            try:
                payload = response.json()
            except ValueError as exc:
                raise SteamResponseError(
                    f"Expected JSON response from {url}, received: {response.text[:500]}"
                ) from exc
            return self._unwrap_payload(payload)

        if last_error is not None:
            raise SteamNetworkError(str(last_error)) from last_error
        raise SteamNetworkError("Steam request failed for an unknown reason.")

    @staticmethod
    def _unwrap_payload(payload: Any) -> Any:
        if isinstance(payload, dict) and set(payload.keys()) == {"response"}:
            return payload["response"]
        return payload

    def _raise_for_response(self, response: requests.Response) -> None:
        payload = None
        message = response.text[:500]
        try:
            payload = response.json()
            message = self._extract_error_message(payload) or message
        except ValueError:
            message = response.text[:500] or f"HTTP {response.status_code}"
            if "Family View" in response.text:
                message = "Steam Family View is blocking this action. Unlock or disable Family View and try again."

        status_code = response.status_code
        error_cls: type[SteamHTTPError]
        if status_code in {401, 403}:
            error_cls = SteamAuthenticationError
        elif status_code == 404:
            error_cls = SteamNotFoundError
        elif status_code == 429:
            error_cls = SteamRateLimitError
        else:
            error_cls = SteamAPIError

        raise error_cls(message, status_code=status_code, payload=payload)

    @staticmethod
    def _extract_error_message(payload: Any) -> Optional[str]:
        if isinstance(payload, dict):
            for key in ("message", "error", "err_msg"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            response = payload.get("response")
            if isinstance(response, dict):
                for key in ("message", "error", "err_msg"):
                    value = response.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
        return None
