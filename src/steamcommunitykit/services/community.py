from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Dict, Union

from steamcommunitykit.constants import COMMUNITY_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import ensure_not_blank, validate_steam_id


class CommunityService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport

    def _community_cookies(self) -> Dict[str, str]:
        credentials = self.transport.require_community_credentials()
        return {
            "steamLoginSecure": credentials.steam_login_secure_value,
            "sessionid": credentials.session_id,
        }

    def set_profile_privacy(
        self,
        steam_id,
        *,
        privacy_profile: int = 1,
        privacy_inventory: int = 2,
        privacy_inventory_gifts: int = 1,
        privacy_owned_games: int = 2,
        privacy_playtime: int = 3,
        privacy_friends_list: int = 3,
        comment_permission: int = 0,
    ) -> dict:
        credentials = self.transport.require_community_credentials()
        privacy_payload = (
            "{"
            f"\"PrivacyProfile\":{int(privacy_profile)},"
            f"\"PrivacyInventory\":{int(privacy_inventory)},"
            f"\"PrivacyInventoryGifts\":{int(privacy_inventory_gifts)},"
            f"\"PrivacyOwnedGames\":{int(privacy_owned_games)},"
            f"\"PrivacyPlaytime\":{int(privacy_playtime)},"
            f"\"PrivacyFriendsList\":{int(privacy_friends_list)}"
            "}"
        )
        response = self.transport.request(
            "POST",
            f"{COMMUNITY_BASE_URL}/profiles/{validate_steam_id(steam_id)}/ajaxsetprivacy/",
            data={
                "sessionid": credentials.session_id,
                "Privacy": privacy_payload,
                "eCommentPermission": str(comment_permission),
            },
            cookies=self._community_cookies(),
        )
        return response

    def update_persona_name(self, steam_id, persona_name: str) -> dict:
        credentials = self.transport.require_community_credentials()
        return self.transport.request(
            "POST",
            f"{COMMUNITY_BASE_URL}/profiles/{validate_steam_id(steam_id)}/edit/",
            data={
                "sessionID": credentials.session_id,
                "type": "profileSave",
                "personaName": ensure_not_blank(persona_name, "persona_name"),
                "hide_profile_awards": 0,
                "json": 1,
            },
            cookies=self._community_cookies(),
        )

    def upload_avatar(self, steam_id, image_path: Union[str, Path]) -> dict:
        credentials = self.transport.require_community_credentials()
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        mime_type, _ = mimetypes.guess_type(path.name)
        with path.open("rb") as handle:
            response = self.transport.session.post(
                f"{COMMUNITY_BASE_URL}/actions/FileUploader/",
                data={
                    "type": "player_avatar_image",
                    "sId": validate_steam_id(steam_id),
                    "sessionid": credentials.session_id,
                    "doSub": "1",
                    "json": "1",
                },
                files={"avatar": (path.name, handle, mime_type or "application/octet-stream")},
                cookies=self._community_cookies(),
                timeout=self.transport.timeout,
            )
        if response.status_code >= 400:
            self.transport._raise_for_response(response)
        return response.json()
