from __future__ import annotations

from typing import Optional

from steamcommunitykit.constants import PARTNER_API_BASE_URL, WEB_API_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import ensure_not_blank, validate_app_id


class AppsService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/ISteamApps"
        self.partner_base_url = f"{PARTNER_API_BASE_URL}/ISteamApps"

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

    def get_partner_app_list_for_web_api_key(self, type_filter: Optional[str] = None) -> dict:
        params = {}
        if type_filter:
            params["type_filter"] = ensure_not_blank(type_filter, "type_filter")
        return self.transport.request(
            "GET",
            f"{self.partner_base_url}/GetPartnerAppListForWebAPIKey/v2/",
            params=params,
            require_api_key=True,
        )

    def get_server_list(self, filter_query: str, limit: Optional[int] = None) -> dict:
        params = {"filter": ensure_not_blank(filter_query, "filter_query")}
        if limit is not None:
            params["limit"] = int(limit)
        return self.transport.request(
            "GET",
            f"{self.partner_base_url}/GetServerList/v1/",
            params=params,
            require_api_key=True,
        )

    def get_app_builds(self, app_id, count: Optional[int] = None) -> dict:
        params = {"appid": validate_app_id(app_id)}
        if count is not None:
            params["count"] = int(count)
        return self.transport.request(
            "GET",
            f"{self.partner_base_url}/GetAppBuilds/v1/",
            params=params,
            require_api_key=True,
        )

    def get_app_depot_versions(self, app_id) -> dict:
        return self.transport.request(
            "GET",
            f"{self.partner_base_url}/GetAppDepotVersions/v1/",
            params={"appid": validate_app_id(app_id)},
            require_api_key=True,
        )

    def get_players_banned(self, app_id) -> dict:
        return self.transport.request(
            "GET",
            f"{self.partner_base_url}/GetPlayersBanned/v1/",
            params={"appid": validate_app_id(app_id)},
            require_api_key=True,
        )
