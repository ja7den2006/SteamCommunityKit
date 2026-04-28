from __future__ import annotations

from typing import List, Optional

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import validate_app_id, validate_steam_id


class UserStatsService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/ISteamUserStats"

    def get_number_of_current_players(self, app_id) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetNumberOfCurrentPlayers/v1/",
            params={"appid": validate_app_id(app_id)},
        )

    def get_global_achievement_percentages_for_app(self, app_id) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetGlobalAchievementPercentagesForApp/v2/",
            params={"gameid": validate_app_id(app_id)},
        )

    def get_player_achievements(
        self, steam_id, app_id, language: Optional[str] = None
    ) -> dict:
        params = {
            "steamid": validate_steam_id(steam_id),
            "appid": validate_app_id(app_id),
        }
        if language:
            params["l"] = language
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetPlayerAchievements/v1/",
            params=params,
            require_api_key=True,
        )

    def get_schema_for_game(self, app_id, language: Optional[str] = None) -> dict:
        params = {"appid": validate_app_id(app_id)}
        if language:
            params["l"] = language
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetSchemaForGame/v2/",
            params=params,
            require_api_key=True,
        )

    def get_user_stats_for_game(self, steam_id, app_id) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetUserStatsForGame/v2/",
            params={
                "steamid": validate_steam_id(steam_id),
                "appid": validate_app_id(app_id),
            },
            require_api_key=True,
        )

    def get_global_stats_for_game(
        self,
        app_id,
        names: List[str],
        *,
        start_date: Optional[int] = None,
        end_date: Optional[int] = None,
    ) -> dict:
        params = {
            "appid": validate_app_id(app_id),
            "count": len(names),
        }
        for index, name in enumerate(names):
            params[f"name[{index}]"] = name
        if start_date is not None:
            params["startdate"] = int(start_date)
        if end_date is not None:
            params["enddate"] = int(end_date)
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetGlobalStatsForGame/v1/",
            params=params,
            require_api_key=True,
        )
