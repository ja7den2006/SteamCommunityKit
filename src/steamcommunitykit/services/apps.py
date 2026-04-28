from __future__ import annotations

from typing import Optional

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import ensure_not_blank, validate_app_id


class AppsService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/ISteamApps"

    def get_app_list(self) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetAppList/v2/",
        )

    def get_servers_at_address(self, address: str) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetServersAtAddress/v1/",
            params={"addr": address},
        )

    def up_to_date_check(self, app_id, version: int) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/UpToDateCheck/v1/",
            params={"appid": validate_app_id(app_id), "version": int(version)},
        )

    def get_server_list(self, filter_query: str, limit: Optional[int] = None) -> dict:
        params = {"filter": ensure_not_blank(filter_query, "filter_query")}
        if limit is not None:
            params["limit"] = int(limit)
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetServerList/v1/",
            params=params,
            require_api_key=True,
        )

    def get_players_banned(self, app_id) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetPlayersBanned/v1/",
            params={"appid": validate_app_id(app_id)},
            require_api_key=True,
        )
