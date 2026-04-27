from __future__ import annotations

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import validate_app_id


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
