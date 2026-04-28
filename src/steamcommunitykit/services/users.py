from __future__ import annotations

import xml.etree.ElementTree as ET

from steamcommunitykit.constants import COMMUNITY_BASE_URL, WEB_API_BASE_URL
from steamcommunitykit.exceptions import SteamNotFoundError, SteamResponseError
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import (
    ensure_not_blank,
    normalize_steam_ids,
    parse_steam_profile_identifier,
    validate_steam_id,
)


class UsersService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/ISteamUser"

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

    def resolve_community_profile_xml(self, identifier) -> dict:
        parsed = parse_steam_profile_identifier(identifier)
        if parsed["type"] == "steam_id":
            url = "{0}/profiles/{1}/".format(COMMUNITY_BASE_URL, parsed["value"])
        else:
            url = "{0}/id/{1}/".format(COMMUNITY_BASE_URL, parsed["value"])
        response_text = self.transport.request(
            "GET",
            url,
            params={"xml": "1"},
            expected="text",
        )
        try:
            root = ET.fromstring(response_text.lstrip())
        except ET.ParseError as exc:
            raise SteamResponseError(
                "Steam returned malformed profile XML: {0}".format(response_text[:500])
            ) from exc
        steam_id = root.findtext("steamID64")
        if not steam_id:
            raise SteamNotFoundError(
                "Steam community profile could not be resolved for the provided identifier.",
                status_code=404,
                payload={"identifier": identifier},
            )
        return {
            "steamid": validate_steam_id(steam_id, "steam_id"),
            "personaname": root.findtext("steamID") or "",
            "custom_url": root.findtext("customURL") or "",
            "profile_url": root.findtext("profileURL") or "",
            "avatar_icon": root.findtext("avatarIcon") or "",
            "avatar_medium": root.findtext("avatarMedium") or "",
            "avatar_full": root.findtext("avatarFull") or "",
            "privacy_state": root.findtext("privacyState") or "",
            "visibility_state": root.findtext("visibilityState") or "",
            "state_message": root.findtext("stateMessage") or "",
            "online_state": root.findtext("onlineState") or "",
            "raw_xml": response_text,
        }

    @staticmethod
    def _community_profile_to_summary(profile: dict) -> dict:
        visibility_state = profile.get("visibility_state")
        online_state = (profile.get("online_state") or "").lower()
        personastate_map = {
            "offline": 0,
            "online": 1,
            "busy": 2,
            "away": 3,
            "snooze": 4,
            "looking to trade": 5,
            "looking to play": 6,
        }
        summary = {
            "steamid": profile.get("steamid", ""),
            "personaname": profile.get("personaname", ""),
            "profileurl": profile.get("profile_url", ""),
            "avatar": profile.get("avatar_icon", ""),
            "avatarmedium": profile.get("avatar_medium", ""),
            "avatarfull": profile.get("avatar_full", ""),
            "communityvisibilitystate": int(visibility_state) if str(visibility_state).isdigit() else None,
            "personastate": personastate_map.get(online_state),
            "profilestate": 1 if profile.get("custom_url") else 0,
            "realname": None,
            "primaryclanid": None,
            "timecreated": None,
            "loccountrycode": None,
            "locstatecode": None,
            "loccityid": None,
            "online_state": profile.get("online_state", ""),
            "privacy_state": profile.get("privacy_state", ""),
            "state_message": profile.get("state_message", ""),
            "custom_url": profile.get("custom_url", ""),
        }
        return summary

    def resolve_steam_id(self, identifier, url_type=None) -> str:
        parsed = parse_steam_profile_identifier(identifier)
        if parsed["type"] == "steam_id":
            return parsed["value"]
        if not self.transport.api_key:
            return self.resolve_community_profile_xml(identifier)["steamid"]

        response = self.resolve_vanity_url(parsed["value"], url_type=url_type)
        steam_id = response.get("steamid")
        if steam_id:
            return validate_steam_id(steam_id, "steam_id")
        success = response.get("success")
        message = response.get("message")
        if success == 42:
            raise SteamNotFoundError(
                message or "Steam vanity URL could not be resolved.",
                status_code=404,
                payload=response,
            )
        raise SteamResponseError(
            message or "Steam did not return a resolvable steamid for the provided identifier."
        )

    def get_player_summary(self, identifier, url_type=None) -> dict:
        if not self.transport.api_key:
            return self._community_profile_to_summary(
                self.resolve_community_profile_xml(identifier)
            )
        steam_id = self.resolve_steam_id(identifier, url_type=url_type)
        players = self.get_player_summaries(steam_id)
        if not players:
            raise SteamNotFoundError(
                "Steam did not return a player summary for the provided identifier.",
                status_code=404,
                payload={"identifier": identifier, "steamid": steam_id},
            )
        return players[0]

    def get_player_summaries(self, steam_ids) -> list:
        if not self.transport.api_key:
            return [
                self._community_profile_to_summary(
                    self.resolve_community_profile_xml(steam_id)
                )
                for steam_id in normalize_steam_ids(steam_ids)
            ]
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

    def get_player_summaries_map(self, steam_ids) -> dict:
        return {
            str(player.get("steamid")): player
            for player in self.get_player_summaries(steam_ids)
            if player.get("steamid")
        }

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

    def get_friend_ids(self, steam_id, relationship: str = "friend") -> list:
        payload = self.get_friend_list(steam_id, relationship=relationship)
        friends = payload.get("friendslist", {}).get("friends", [])
        return [friend.get("steamid") for friend in friends if friend.get("steamid")]

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

    def get_user_group_ids(self, steam_id) -> list:
        payload = self.get_user_group_list(steam_id)
        groups = payload.get("groups", [])
        return [group.get("gid") for group in groups if group.get("gid")]
