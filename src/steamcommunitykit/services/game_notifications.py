from __future__ import annotations

from typing import Any, Iterable, Optional

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.exceptions import SteamValidationError
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import ensure_not_blank, validate_app_id, validate_steam_id, validate_uint64


class GameNotificationsService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/IGameNotificationsService"

    def create_session(
        self,
        app_id,
        context: str,
        title: str,
        users: Iterable[Any],
        *,
        steam_id=None,
    ) -> dict:
        payload = {
            "appid": validate_app_id(app_id),
            "context": ensure_not_blank(context, "context"),
            "title": ensure_not_blank(title, "title"),
            "users": self._normalize_required_list(users, "users"),
        }
        if steam_id is not None:
            payload["steamid"] = validate_steam_id(steam_id)
        return self.transport.request(
            "POST",
            f"{self.base_url}/CreateSession/v1/",
            require_api_key=True,
            service_payload=payload,
        )

    def update_session(
        self,
        session_id,
        app_id,
        *,
        title: Optional[str] = None,
        users: Optional[Iterable[Any]] = None,
        steam_id=None,
    ) -> dict:
        payload = {
            "sessionid": validate_uint64(session_id, "session_id"),
            "appid": validate_app_id(app_id),
        }
        if title is not None:
            payload["title"] = ensure_not_blank(title, "title")
        if users is not None:
            payload["users"] = self._normalize_required_list(users, "users")
        if steam_id is not None:
            payload["steamid"] = validate_steam_id(steam_id)
        return self.transport.request(
            "POST",
            f"{self.base_url}/UpdateSession/v1/",
            require_api_key=True,
            service_payload=payload,
        )

    def delete_session(self, session_id, app_id, *, steam_id=None) -> dict:
        payload = {
            "sessionid": validate_uint64(session_id, "session_id"),
            "appid": validate_app_id(app_id),
        }
        if steam_id is not None:
            payload["steamid"] = validate_steam_id(steam_id)
        return self.transport.request(
            "POST",
            f"{self.base_url}/DeleteSession/v1/",
            require_api_key=True,
            service_payload=payload,
        )

    def delete_session_batch(self, app_id, session_ids: Iterable[Any]) -> dict:
        payload = {
            "appid": validate_app_id(app_id),
            "sessionids": self._normalize_session_ids(session_ids),
        }
        return self.transport.request(
            "POST",
            f"{self.base_url}/DeleteSessionBatch/v1/",
            require_api_key=True,
            service_payload=payload,
        )

    def enumerate_sessions_for_app(
        self,
        app_id,
        steam_id,
        *,
        include_all_user_messages: Optional[bool] = None,
        include_auth_user_message: Optional[bool] = None,
        language: Optional[str] = None,
    ) -> dict:
        payload = {
            "appid": validate_app_id(app_id),
            "steamid": validate_steam_id(steam_id),
        }
        if include_all_user_messages is not None:
            payload["include_all_user_messages"] = bool(include_all_user_messages)
        if include_auth_user_message is not None:
            payload["include_auth_user_message"] = bool(include_auth_user_message)
        if language is not None:
            payload["language"] = ensure_not_blank(language, "language")
        return self.transport.request(
            "GET",
            f"{self.base_url}/EnumerateSessionsForApp/v1/",
            require_api_key=True,
            service_payload=payload,
        )

    def get_session_details_for_app(
        self,
        app_id,
        sessions: Iterable[Any],
        *,
        language: Optional[str] = None,
    ) -> dict:
        payload = {
            "appid": validate_app_id(app_id),
            "sessions": self._normalize_required_list(sessions, "sessions"),
        }
        if language is not None:
            payload["language"] = ensure_not_blank(language, "language")
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetSessionDetailsForApp/v1/",
            require_api_key=True,
            service_payload=payload,
        )

    def request_notifications(self, app_id, steam_id) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/RequestNotifications/v1/",
            require_api_key=True,
            service_payload={
                "appid": validate_app_id(app_id),
                "steamid": validate_steam_id(steam_id),
            },
        )

    @staticmethod
    def _normalize_required_list(values: Iterable[Any], field_name: str) -> list:
        normalized = list(values)
        if not normalized:
            raise SteamValidationError("{0} cannot be empty.".format(field_name))
        return normalized

    @staticmethod
    def _normalize_session_ids(values: Iterable[Any]) -> list:
        normalized = [validate_uint64(value, "session_id") for value in values]
        if not normalized:
            raise SteamValidationError("session_ids cannot be empty.")
        return normalized
