from __future__ import annotations

from typing import Optional, Union

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.exceptions import SteamValidationError
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import (
    ensure_not_blank,
    normalize_binary_value,
    validate_app_id,
    validate_int32,
    validate_steam_id,
    validate_uint32,
)


class LeaderboardsService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/ISteamLeaderboards"

    def delete_leaderboard(self, app_id, name: str) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/DeleteLeaderboard/v1/",
            data={
                "appid": validate_app_id(app_id),
                "name": ensure_not_blank(name, "name"),
            },
            require_api_key=True,
        )

    def delete_leaderboard_score(self, app_id, leaderboard_id: int, steam_id) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/DeleteLeaderboardScore/v1/",
            data={
                "appid": validate_app_id(app_id),
                "leaderboardid": validate_uint32(leaderboard_id, "leaderboard_id"),
                "steamid": validate_steam_id(steam_id),
            },
            require_api_key=True,
        )

    def find_or_create_leaderboard(
        self,
        app_id,
        name: str,
        *,
        sort_method: Optional[str] = None,
        display_type: Optional[str] = None,
        create_if_not_found: Optional[bool] = None,
        only_trusted_writes: Optional[bool] = None,
        only_friends_reads: Optional[bool] = None,
    ) -> dict:
        data = {
            "appid": validate_app_id(app_id),
            "name": ensure_not_blank(name, "name"),
        }
        if sort_method:
            data["sortmethod"] = ensure_not_blank(sort_method, "sort_method")
        if display_type:
            data["displaytype"] = ensure_not_blank(display_type, "display_type")
        if create_if_not_found is not None:
            data["createifnotfound"] = int(create_if_not_found)
        if only_trusted_writes is not None:
            data["onlytrustedwrites"] = int(only_trusted_writes)
        if only_friends_reads is not None:
            data["onlyfriendsreads"] = int(only_friends_reads)
        return self.transport.request(
            "POST",
            f"{self.base_url}/FindOrCreateLeaderboard/v2/",
            data=data,
            require_api_key=True,
        )

    def get_leaderboard_entries(
        self,
        app_id,
        leaderboard_id: int,
        range_start: int,
        range_end: int,
        data_request: str,
        *,
        steam_id=None,
    ) -> dict:
        params = {
            "appid": validate_app_id(app_id),
            "leaderboardid": validate_int32(leaderboard_id, "leaderboard_id"),
            "rangestart": validate_int32(range_start, "range_start"),
            "rangeend": validate_int32(range_end, "range_end"),
            "datarequest": ensure_not_blank(data_request, "data_request"),
        }
        if steam_id is not None:
            params["steamid"] = validate_steam_id(steam_id)
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetLeaderboardEntries/v1/",
            params=params,
            require_api_key=True,
        )

    def get_leaderboards_for_game(self, app_id) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetLeaderboardsForGame/v2/",
            params={"appid": validate_app_id(app_id)},
            require_api_key=True,
        )

    def reset_leaderboard(self, app_id, leaderboard_id: int) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/ResetLeaderboard/v1/",
            data={
                "appid": validate_app_id(app_id),
                "leaderboardid": validate_uint32(leaderboard_id, "leaderboard_id"),
            },
            require_api_key=True,
        )

    def set_leaderboard_score(
        self,
        app_id,
        leaderboard_id: int,
        steam_id,
        score: int,
        score_method: str,
        *,
        details: Optional[Union[str, bytes, bytearray]] = None,
    ) -> dict:
        data = {
            "appid": validate_app_id(app_id),
            "leaderboardid": validate_uint32(leaderboard_id, "leaderboard_id"),
            "steamid": validate_steam_id(steam_id),
            "score": validate_int32(score, "score"),
            "scoremethod": ensure_not_blank(score_method, "score_method"),
        }
        if details is not None:
            normalized = normalize_binary_value(details, "details")
            if len(normalized) > 512:
                raise SteamValidationError("details cannot exceed 256 bytes.")
            data["details"] = normalized
        return self.transport.request(
            "POST",
            f"{self.base_url}/SetLeaderboardScore/v1/",
            data=data,
            require_api_key=True,
        )
