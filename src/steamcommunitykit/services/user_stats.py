from __future__ import annotations

from typing import List, Mapping, Optional, Union

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.exceptions import SteamValidationError
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import validate_app_id, validate_steam_id, validate_uint32


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

    def set_user_stats_for_game(
        self,
        steam_id,
        app_id,
        stats: Mapping[str, Union[int, bool, str]],
    ) -> dict:
        if not stats:
            raise SteamValidationError("stats cannot be empty.")
        data = {
            "steamid": validate_steam_id(steam_id),
            "appid": validate_app_id(app_id),
            "count": len(stats),
        }
        for index, (name, value) in enumerate(stats.items()):
            if not str(name).strip():
                raise SteamValidationError("stat names must be non-empty strings.")
            data["name[{0}]".format(index)] = str(name).strip()
            data["value[{0}]".format(index)] = validate_uint32(
                int(value),
                "value[{0}]".format(index),
                allow_zero=True,
            )
        return self.transport.request(
            "POST",
            f"{self.base_url}/SetUserStatsForGame/v1/",
            data=data,
            require_api_key=True,
        )
