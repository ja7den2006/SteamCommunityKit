from __future__ import annotations

from typing import Union

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import (
    ensure_not_blank,
    normalize_binary_value,
    validate_app_id,
    validate_steam_id,
)


class UserAuthService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/ISteamUserAuth"

    def authenticate_user(
        self,
        steam_id,
        *,
        session_key: Union[str, bytes, bytearray],
        encrypted_login_key: Union[str, bytes, bytearray],
    ) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/AuthenticateUser/v1/",
            data={
                "steamid": validate_steam_id(steam_id),
                "sessionkey": normalize_binary_value(session_key, "session_key"),
                "encrypted_loginkey": normalize_binary_value(
                    encrypted_login_key, "encrypted_login_key"
                ),
            },
        )

    def authenticate_user_ticket(self, app_id, ticket: str, identity: str) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/AuthenticateUserTicket/v1/",
            params={
                "appid": validate_app_id(app_id),
                "ticket": ensure_not_blank(ticket, "ticket"),
                "identity": ensure_not_blank(identity, "identity"),
            },
            require_api_key=True,
        )
