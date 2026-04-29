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

    def get_badges_summary(self, steam_id) -> dict:
        payload = self.get_badges(steam_id)
        badges = payload.get("badges", []) or []
        normalized = []
        for entry in badges:
            normalized.append(
                {
                    "badge_id": entry.get("badgeid"),
                    "level": entry.get("level"),
                    "completion_time": entry.get("completion_time"),
                    "xp": entry.get("xp"),
                    "scarcity": entry.get("scarcity"),
                    "border_color": entry.get("border_color"),
                    "appid": entry.get("appid"),
                    "communityitemid": entry.get("communityitemid"),
                    "raw": entry,
                }
            )
        return {
            "steamid": validate_steam_id(steam_id),
            "player_level": payload.get("player_level"),
            "player_xp": payload.get("player_xp"),
            "player_xp_needed_to_level_up": payload.get("player_xp_needed_to_level_up"),
            "player_xp_needed_current_level": payload.get("player_xp_needed_current_level"),
            "badge_count": len(normalized),
            "badges": normalized,
            "raw": payload,
        }

    def get_community_badge_progress_summary(self, steam_id, badge_id: int) -> dict:
        payload = self.get_community_badge_progress(steam_id, badge_id)
        quests = payload.get("quests", []) or []
        normalized = []
        completed_count = 0
        for entry in quests:
            completed = bool(entry.get("completed"))
            if completed:
                completed_count += 1
            normalized.append(
                {
                    "quest_id": entry.get("questid"),
                    "completed": completed,
                    "raw": entry,
                }
            )
        return {
            "steamid": validate_steam_id(steam_id),
            "badge_id": int(badge_id),
            "quest_count": len(normalized),
            "completed_count": completed_count,
            "quests": normalized,
            "raw": payload,
        }

    @staticmethod
    def _normalize_game_entry(game: dict) -> dict:
        return {
            "app_id": game.get("appid"),
            "name": game.get("name"),
            "playtime_forever": game.get("playtime_forever"),
            "playtime_windows_forever": game.get("playtime_windows_forever"),
            "playtime_mac_forever": game.get("playtime_mac_forever"),
            "playtime_linux_forever": game.get("playtime_linux_forever"),
            "playtime_2weeks": game.get("playtime_2weeks"),
            "img_icon_url": game.get("img_icon_url"),
            "img_logo_url": game.get("img_logo_url"),
            "has_community_visible_stats": game.get("has_community_visible_stats"),
            "content_descriptorids": game.get("content_descriptorids", []),
            "sort_as": game.get("sort_as"),
            "capsule_filename": game.get("capsule_filename"),
            "raw": game,
        }

    def get_owned_games_summary(
        self,
        steam_id,
        *,
        include_appinfo: bool = True,
        include_played_free_games: bool = False,
        appids_filter: Optional[List[int]] = None,
        language: Optional[str] = None,
    ) -> dict:
        payload = self.get_owned_games(
            steam_id,
            include_appinfo=include_appinfo,
            include_played_free_games=include_played_free_games,
            appids_filter=appids_filter,
            language=language,
        )
        games = payload.get("games", [])
        normalized_games = [self._normalize_game_entry(game) for game in games]
        return {
            "steamid": validate_steam_id(steam_id),
            "game_count": payload.get("game_count", len(normalized_games)),
            "games": normalized_games,
            "games_map": {
                game["app_id"]: game
                for game in normalized_games
                if game.get("app_id") is not None
            },
            "raw": payload,
        }

    def get_recently_played_games_summary(self, steam_id, count: int = 0) -> dict:
        payload = self.get_recently_played_games(steam_id, count=count)
        games = payload.get("games", [])
        normalized_games = [self._normalize_game_entry(game) for game in games]
        return {
            "steamid": validate_steam_id(steam_id),
            "total_count": payload.get("total_count", len(normalized_games)),
            "games": normalized_games,
            "games_map": {
                game["app_id"]: game
                for game in normalized_games
                if game.get("app_id") is not None
            },
            "raw": payload,
        }

    def find_owned_game(
        self,
        steam_id,
        *,
        app_id=None,
        name_query: Optional[str] = None,
        include_appinfo: bool = True,
        include_played_free_games: bool = False,
        appids_filter: Optional[List[int]] = None,
        language: Optional[str] = None,
    ) -> dict:
        payload = self.get_owned_games_summary(
            steam_id,
            include_appinfo=include_appinfo,
            include_played_free_games=include_played_free_games,
            appids_filter=appids_filter,
            language=language,
        )
        query = (name_query or "").strip().lower()
        target_app_id = validate_app_id(app_id) if app_id is not None else None
        matches = []
        for game in payload.get("games", []):
            if target_app_id is not None and game.get("app_id") != target_app_id:
                continue
            if query and query not in (game.get("name") or "").lower():
                continue
            matches.append(game)
        return {
            "steamid": payload.get("steamid"),
            "count": len(matches),
            "games": matches,
            "raw": payload,
        }

    def find_recently_played_game(
        self,
        steam_id,
        *,
        app_id=None,
        name_query: Optional[str] = None,
        count: int = 0,
    ) -> dict:
        payload = self.get_recently_played_games_summary(steam_id, count=count)
        query = (name_query or "").strip().lower()
        target_app_id = validate_app_id(app_id) if app_id is not None else None
        matches = []
        for game in payload.get("games", []):
            if target_app_id is not None and game.get("app_id") != target_app_id:
                continue
            if query and query not in (game.get("name") or "").lower():
                continue
            matches.append(game)
        return {
            "steamid": payload.get("steamid"),
            "count": len(matches),
            "games": matches,
            "raw": payload,
        }
