from __future__ import annotations

from typing import Optional

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport


class StoreService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/IStoreService"

    def get_app_list(
        self,
        *,
        if_modified_since: Optional[int] = None,
        have_description_language: Optional[str] = None,
        include_games: Optional[bool] = None,
        include_dlc: Optional[bool] = None,
        include_software: Optional[bool] = None,
        include_videos: Optional[bool] = None,
        include_hardware: Optional[bool] = None,
    ) -> dict:
        params = {}
        if if_modified_since is not None:
            params["if_modified_since"] = int(if_modified_since)
        if have_description_language:
            params["have_description_language"] = have_description_language
        if include_games is not None:
            params["include_games"] = int(include_games)
        if include_dlc is not None:
            params["include_dlc"] = int(include_dlc)
        if include_software is not None:
            params["include_software"] = int(include_software)
        if include_videos is not None:
            params["include_videos"] = int(include_videos)
        if include_hardware is not None:
            params["include_hardware"] = int(include_hardware)
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetAppList/v1/",
            params=params,
            require_api_key=True,
        )
