from __future__ import annotations

from typing import List, Optional

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import validate_app_id, validate_steam_id


class PlayersService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/IPlayerService"

    def get_owned_games(
        self,
        steam_id,
        *,
        include_appinfo: bool = True,
        include_played_free_games: bool = False,
        appids_filter: Optional[List[int]] = None,
        language: Optional[str] = None,
    ) -> dict:
        params = {
            "steamid": validate_steam_id(steam_id),
            "include_appinfo": int(include_appinfo),
            "include_played_free_games": int(include_played_free_games),
        }
        if language:
            params["l"] = language
        if appids_filter:
            for index, app_id in enumerate(appids_filter):
                params[f"appids_filter[{index}]"] = validate_app_id(app_id)
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetOwnedGames/v1/",
            params=params,
            require_api_key=True,
        )

    def get_recently_played_games(self, steam_id, count: int = 0) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetRecentlyPlayedGames/v1/",
            params={"steamid": validate_steam_id(steam_id), "count": int(count)},
            require_api_key=True,
        )

    def get_single_game_playtime(self, steam_id, app_id) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetSingleGamePlaytime/v1/",
            params={
                "steamid": validate_steam_id(steam_id),
                "appid": validate_app_id(app_id),
            },
            require_api_key=True,
        )

    def get_steam_level(self, steam_id) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetSteamLevel/v1/",
            params={"steamid": validate_steam_id(steam_id)},
            require_api_key=True,
        )

    def get_badges(self, steam_id) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetBadges/v1/",
            params={"steamid": validate_steam_id(steam_id)},
            require_api_key=True,
        )

    def get_community_badge_progress(self, steam_id, badge_id: int) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetCommunityBadgeProgress/v1/",
            params={"steamid": validate_steam_id(steam_id), "badgeid": int(badge_id)},
            require_api_key=True,
        )
