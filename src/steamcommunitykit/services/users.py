from __future__ import annotations

from steamcommunitykit.constants import PARTNER_API_BASE_URL, WEB_API_BASE_URL
from steamcommunitykit.exceptions import SteamValidationError
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import ensure_not_blank, normalize_steam_ids, validate_app_id, validate_steam_id


class UsersService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/ISteamUser"
        self.partner_base_url = f"{PARTNER_API_BASE_URL}/ISteamUser"

    def resolve_vanity_url(self, vanity_url: str, url_type=None) -> dict:
        params = {"vanityurl": ensure_not_blank(vanity_url, "vanity_url")}
        if url_type is not None:
            params["url_type"] = int(url_type)
        return self.transport.request(
            "GET",
            f"{self.base_url}/ResolveVanityURL/v1/",
            params=params,
            require_api_key=True,
        )

    def get_player_summaries(self, steam_ids) -> list:
        players = []
        normalized = normalize_steam_ids(steam_ids)
        for offset in range(0, len(normalized), 100):
            chunk = normalized[offset : offset + 100]
            response = self.transport.request(
                "GET",
                f"{self.base_url}/GetPlayerSummaries/v2/",
                params={"steamids": ",".join(chunk)},
                require_api_key=True,
            )
            players.extend(response.get("players", []))
        return players

    def get_friend_list(self, steam_id, relationship: str = "friend") -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetFriendList/v1/",
            params={
                "steamid": validate_steam_id(steam_id),
                "relationship": ensure_not_blank(relationship, "relationship"),
            },
            require_api_key=True,
        )

    def get_player_bans(self, steam_ids) -> list:
        response = self.transport.request(
            "GET",
            f"{self.base_url}/GetPlayerBans/v1/",
            params={"steamids": ",".join(normalize_steam_ids(steam_ids))},
            require_api_key=True,
        )
        return response.get("players", [])

    def get_user_group_list(self, steam_id) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetUserGroupList/v1/",
            params={"steamid": validate_steam_id(steam_id)},
            require_api_key=True,
        )

    def check_app_ownership(self, steam_id, app_id) -> dict:
        return self.transport.request(
            "GET",
            f"{self.partner_base_url}/CheckAppOwnership/v4/",
            params={
                "steamid": validate_steam_id(steam_id),
                "appid": validate_app_id(app_id),
            },
            require_api_key=True,
        )

    def get_app_price_info(self, steam_id, app_ids) -> dict:
        normalized_ids = [str(validate_app_id(app_id)) for app_id in app_ids]
        if not normalized_ids:
            raise SteamValidationError("app_ids cannot be empty.")
        return self.transport.request(
            "GET",
            f"{self.partner_base_url}/GetAppPriceInfo/v1/",
            params={
                "steamid": validate_steam_id(steam_id),
                "appids": ",".join(normalized_ids[:100]),
            },
            require_api_key=True,
        )

    def get_deleted_steam_ids(self, rowversion) -> dict:
        return self.transport.request(
            "GET",
            f"{self.partner_base_url}/GetDeletedSteamIDs/v1/",
            params={"rowversion": int(rowversion)},
            require_api_key=True,
        )

    def get_publisher_app_ownership(self, steam_id) -> dict:
        return self.transport.request(
            "GET",
            f"{self.partner_base_url}/GetPublisherAppOwnership/v4/",
            params={"steamid": validate_steam_id(steam_id)},
            require_api_key=True,
        )
