from __future__ import annotations

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport


class WebAPIUtilService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/ISteamWebAPIUtil"

    def get_server_info(self) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetServerInfo/v1/",
        )

    def get_supported_api_list(self, *, include_restricted: bool = False) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetSupportedAPIList/v1/",
            require_api_key=include_restricted,
        )
