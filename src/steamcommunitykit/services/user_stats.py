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

    def get_global_achievement_percentages_map(self, app_id) -> dict:
        payload = self.get_global_achievement_percentages_for_app(app_id)
        achievements = payload.get("achievementpercentages", {}).get("achievements", [])
        normalized = []
        mapping = {}
        for entry in achievements:
            item = {
                "name": entry.get("name"),
                "percent": entry.get("percent"),
                "raw": entry,
            }
            normalized.append(item)
            if item.get("name"):
                mapping[item["name"]] = item
        return {
            "app_id": validate_app_id(app_id),
            "achievement_count": len(normalized),
            "achievements": normalized,
            "achievements_map": mapping,
            "raw": payload,
        }

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

    def get_schema_for_game_summary(self, app_id, language: Optional[str] = None) -> dict:
        payload = self.get_schema_for_game(app_id, language=language)
        game = payload.get("game", {})
        available_game_stats = game.get("availableGameStats", {})
        achievements = available_game_stats.get("achievements", []) or []
        stats = available_game_stats.get("stats", []) or []
        normalized_achievements = []
        achievements_map = {}
        for entry in achievements:
            item = {
                "api_name": entry.get("name"),
                "display_name": entry.get("displayName"),
                "description": entry.get("description"),
                "default_value": entry.get("defaultvalue"),
                "hidden": entry.get("hidden"),
                "icon": entry.get("icon"),
                "icongray": entry.get("icongray"),
                "raw": entry,
            }
            normalized_achievements.append(item)
            if item.get("api_name"):
                achievements_map[item["api_name"]] = item
        normalized_stats = []
        stats_map = {}
        for entry in stats:
            item = {
                "api_name": entry.get("name"),
                "display_name": entry.get("displayName"),
                "default_value": entry.get("defaultvalue"),
                "raw": entry,
            }
            normalized_stats.append(item)
            if item.get("api_name"):
                stats_map[item["api_name"]] = item
        return {
            "app_id": validate_app_id(app_id),
            "game_name": game.get("gameName"),
            "game_version": game.get("gameVersion"),
            "achievement_count": len(normalized_achievements),
            "achievements": normalized_achievements,
            "achievements_map": achievements_map,
            "stat_count": len(normalized_stats),
            "stats": normalized_stats,
            "stats_map": stats_map,
            "raw": payload,
        }

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

    def get_global_stats_for_game_summary(
        self,
        app_id,
        names: List[str],
        *,
        start_date: Optional[int] = None,
        end_date: Optional[int] = None,
    ) -> dict:
        payload = self.get_global_stats_for_game(
            app_id,
            names,
            start_date=start_date,
            end_date=end_date,
        )
        result = payload.get("result", {}) if isinstance(payload.get("result"), dict) else {}
        global_stats = result.get("globalstats", {}) if isinstance(result.get("globalstats"), dict) else {}
        normalized = []
        stats_map = {}
        for name in names:
            item = {
                "name": name,
                "value": global_stats.get(name),
            }
            normalized.append(item)
            stats_map[name] = item
        return {
            "app_id": validate_app_id(app_id),
            "stats": normalized,
            "stats_map": stats_map,
            "error": payload.get("error"),
            "result": result,
            "raw": payload,
        }

    def get_player_achievements_summary(
        self, steam_id, app_id, language: Optional[str] = None
    ) -> dict:
        payload = self.get_player_achievements(steam_id, app_id, language=language)
        playerstats = payload.get("playerstats", {})
        achievements = playerstats.get("achievements", [])
        normalized = []
        achieved_count = 0
        for entry in achievements:
            achieved = bool(entry.get("achieved"))
            if achieved:
                achieved_count += 1
            normalized.append(
                {
                    "api_name": entry.get("apiname"),
                    "achieved": achieved,
                    "unlock_time": entry.get("unlocktime"),
                    "name": entry.get("name"),
                    "description": entry.get("description"),
                    "icon": entry.get("icon"),
                    "icongray": entry.get("icongray"),
                    "hidden": entry.get("hidden"),
                    "raw": entry,
                }
            )
        total_count = len(normalized)
        completion_percentage = 0.0
        if total_count:
            completion_percentage = round((achieved_count / total_count) * 100.0, 2)
        return {
            "steamid": validate_steam_id(steam_id),
            "app_id": validate_app_id(app_id),
            "game_name": playerstats.get("gameName"),
            "achievement_count": total_count,
            "achieved_count": achieved_count,
            "completion_percentage": completion_percentage,
            "achievements": normalized,
            "raw": payload,
        }
