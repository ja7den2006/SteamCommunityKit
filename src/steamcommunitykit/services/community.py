from __future__ import annotations

import html
import json
import mimetypes
import re
from pathlib import Path
from typing import Dict, Optional, Union

from steamcommunitykit.constants import COMMUNITY_BASE_URL
from steamcommunitykit.exceptions import SteamResponseError, SteamValidationError
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import ensure_not_blank, validate_steam_id


class CommunityService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport

    @staticmethod
    def _extract_json_data_attribute(html_text: str, attribute_name: str) -> dict:
        pattern = r'{0}="([^"]+)"'.format(re.escape(attribute_name))
        match = re.search(pattern, html_text)
        if not match:
            raise SteamResponseError(
                "Steam did not expose the expected {0} attribute.".format(attribute_name)
            )
        try:
            return json.loads(html.unescape(match.group(1)))
        except json.JSONDecodeError as exc:
            raise SteamResponseError(
                "Steam returned malformed JSON inside {0}.".format(attribute_name)
            ) from exc

    def _resolved_steam_id(self, steam_id=None) -> str:
        if steam_id is None:
            return self.transport.require_community_credentials().steam_id
        return validate_steam_id(steam_id)

    def _community_cookies(self) -> Dict[str, str]:
        credentials = self.transport.require_community_credentials()
        return {
            "steamLoginSecure": credentials.steam_login_secure_value,
            "sessionid": credentials.session_id,
        }

    @staticmethod
    def _headers(referer: str) -> Dict[str, str]:
        return {
            "Accept": "application/json, text/plain, */*",
            "Origin": COMMUNITY_BASE_URL,
            "Referer": referer,
            "X-Requested-With": "XMLHttpRequest",
        }

    def _fetch_edit_page_html(self, steam_id=None) -> str:
        normalized_steam_id = self._resolved_steam_id(steam_id)
        return self.transport.request(
            "GET",
            f"{COMMUNITY_BASE_URL}/profiles/{normalized_steam_id}/edit/",
            cookies=self._community_cookies(),
            expected="text",
        )

    def get_account_info(self, steam_id=None) -> dict:
        return self._extract_json_data_attribute(
            self._fetch_edit_page_html(steam_id),
            "data-userinfo",
        )

    def get_profile_edit_state(self, steam_id=None) -> dict:
        return self._extract_json_data_attribute(
            self._fetch_edit_page_html(steam_id),
            "data-profile-edit",
        )

    def get_profile_privacy(self, steam_id=None) -> dict:
        profile_state = self.get_profile_edit_state(steam_id)
        privacy = profile_state.get("Privacy")
        if not isinstance(privacy, dict):
            raise SteamResponseError("Steam did not include profile privacy data on the edit page.")
        return privacy

    def set_profile_privacy(
        self,
        steam_id=None,
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
        normalized_steam_id = self._resolved_steam_id(steam_id)
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
            f"{COMMUNITY_BASE_URL}/profiles/{normalized_steam_id}/ajaxsetprivacy/",
            data={
                "sessionid": credentials.session_id,
                "Privacy": privacy_payload,
                "eCommentPermission": str(comment_permission),
            },
            headers=self._headers(
                f"{COMMUNITY_BASE_URL}/profiles/{normalized_steam_id}/edit/settings"
            ),
            cookies=self._community_cookies(),
        )
        return response

    def update_persona_name(self, steam_id=None, persona_name: str = "") -> dict:
        return self.edit_profile(
            steam_id,
            persona_name=persona_name,
        )

    def edit_profile(
        self,
        steam_id=None,
        *,
        persona_name: Optional[str] = None,
        real_name: Optional[str] = None,
        summary: Optional[str] = None,
        custom_url: Optional[str] = None,
        country: Optional[str] = None,
        state: Optional[str] = None,
        city: Optional[Union[int, str]] = None,
        hide_profile_awards: bool = False,
    ) -> dict:
        credentials = self.transport.require_community_credentials()
        normalized_steam_id = self._resolved_steam_id(steam_id)
        data = {
            "sessionID": credentials.session_id,
            "type": "profileSave",
            "hide_profile_awards": int(hide_profile_awards),
            "json": 1,
        }
        if persona_name is not None:
            data["personaName"] = ensure_not_blank(persona_name, "persona_name")
        if real_name is not None:
            data["real_name"] = real_name
        if summary is not None:
            data["summary"] = summary
        if custom_url is not None:
            data["customURL"] = custom_url
        if country is not None:
            data["country"] = country
        if state is not None:
            data["state"] = state
        if city is not None:
            data["city"] = str(city)

        editable_fields = {
            "personaName",
            "real_name",
            "summary",
            "customURL",
            "country",
            "state",
            "city",
        }
        if not any(field in data for field in editable_fields):
            raise SteamValidationError("edit_profile requires at least one editable field.")

        return self.transport.request(
            "POST",
            f"{COMMUNITY_BASE_URL}/profiles/{normalized_steam_id}/edit/",
            data=data,
            headers=self._headers(f"{COMMUNITY_BASE_URL}/profiles/{normalized_steam_id}/edit/"),
            cookies=self._community_cookies(),
        )

    def upload_avatar(self, image_path: Union[str, Path], steam_id=None) -> dict:
        credentials = self.transport.require_community_credentials()
        normalized_steam_id = self._resolved_steam_id(steam_id)
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        mime_type, _ = mimetypes.guess_type(path.name)
        with path.open("rb") as handle:
            response = self.transport.session.post(
                f"{COMMUNITY_BASE_URL}/actions/FileUploader/",
                data={
                    "type": "player_avatar_image",
                    "sId": normalized_steam_id,
                    "sessionid": credentials.session_id,
                    "doSub": "1",
                    "json": "1",
                },
                files={"avatar": (path.name, handle, mime_type or "application/octet-stream")},
                cookies=self._community_cookies(),
                headers=self._headers(f"{COMMUNITY_BASE_URL}/profiles/{normalized_steam_id}/edit/avatar"),
                timeout=self.transport.timeout,
            )
        if response.status_code >= 400:
            self.transport._raise_for_response(response)
        return response.json()
