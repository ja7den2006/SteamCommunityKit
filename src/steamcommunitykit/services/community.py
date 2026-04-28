from __future__ import annotations

import html
import json
import mimetypes
import re
from pathlib import Path
from typing import Dict, Optional, Union
from urllib.parse import parse_qs, urlparse

from steamcommunitykit.constants import COMMUNITY_BASE_URL
from steamcommunitykit.exceptions import SteamResponseError, SteamValidationError
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import (
    build_trade_offer_url,
    ensure_not_blank,
    parse_trade_offer_url,
    validate_steam_id,
)


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

    @staticmethod
    def _ensure_ajax_success(response: dict, action: str) -> dict:
        success = response.get("success")
        error_message = html.unescape(str(response.get("errmsg", "")).replace("<br />", " ").strip())
        if success == 1:
            return response
        if error_message:
            raise SteamResponseError("{0} failed: {1}".format(action, error_message))
        raise SteamResponseError("{0} failed.".format(action))

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

    def _fetch_trade_privacy_page_html(self, steam_id=None) -> str:
        normalized_steam_id = self._resolved_steam_id(steam_id)
        return self.transport.request(
            "GET",
            f"{COMMUNITY_BASE_URL}/profiles/{normalized_steam_id}/tradeoffers/privacy",
            cookies=self._community_cookies(),
            expected="text",
        )

    def get_profile_bundle(self, steam_id=None) -> dict:
        html_text = self._fetch_edit_page_html(steam_id)
        account_info = self._extract_json_data_attribute(html_text, "data-userinfo")
        profile_edit_state = self._extract_json_data_attribute(html_text, "data-profile-edit")
        privacy = profile_edit_state.get("Privacy")
        if not isinstance(privacy, dict):
            raise SteamResponseError("Steam did not include profile privacy data on the edit page.")
        return {
            "account_info": account_info,
            "profile_edit_state": profile_edit_state,
            "privacy": privacy,
        }

    def get_account_info(self, steam_id=None) -> dict:
        return self._extract_json_data_attribute(
            self._fetch_edit_page_html(steam_id),
            "data-userinfo",
        )

    def get_profile_edit_state(self, steam_id=None) -> dict:
        return self.get_profile_bundle(steam_id)["profile_edit_state"]

    def get_profile_privacy(self, steam_id=None) -> dict:
        return self.get_profile_bundle(steam_id)["privacy"]

    def get_trade_offer_url(self, steam_id=None) -> dict:
        html_text = self._fetch_trade_privacy_page_html(steam_id)
        match = re.search(
            r'id="trade_offer_access_url"[^>]*value="([^"]+)"',
            html_text,
        )
        if not match:
            raise SteamResponseError("Steam did not expose a trade offer URL on the privacy page.")
        return parse_trade_offer_url(html.unescape(match.group(1)))

    def rotate_trade_offer_url(self, steam_id=None) -> dict:
        credentials = self.transport.require_community_credentials()
        normalized_steam_id = self._resolved_steam_id(steam_id)
        token = ensure_not_blank(
            self.transport.request(
                "POST",
                f"{COMMUNITY_BASE_URL}/profiles/{normalized_steam_id}/tradeoffers/newtradeurl",
                data={"sessionid": credentials.session_id},
                headers=self._headers(
                    f"{COMMUNITY_BASE_URL}/profiles/{normalized_steam_id}/tradeoffers/privacy"
                ),
                cookies=self._community_cookies(),
                expected="text",
            ),
            "token",
        )
        token = token.strip().strip('"')
        account_info = self.get_account_info(normalized_steam_id)
        partner_id = str(account_info["accountid"])
        return parse_trade_offer_url(
            build_trade_offer_url(
                partner_account_id=partner_id,
                token=token,
            )
        )

    def get_web_api_key_status(self) -> dict:
        html_text = self.transport.request(
            "GET",
            f"{COMMUNITY_BASE_URL}/dev/apikey",
            cookies=self._community_cookies(),
            expected="text",
        )
        if "<h2>Access Denied</h2>" in html_text:
            reason_match = re.search(r"<div id=\"bodyContents_lo\">\s*<p>(.*?)</p>", html_text, re.S | re.I)
            reason = ""
            if reason_match:
                reason = re.sub(r"<.*?>", "", reason_match.group(1)).strip()
                reason = html.unescape(reason)
            return {
                "has_access": False,
                "api_key": None,
                "domain": None,
                "reason": reason,
            }

        key_match = re.search(r"Key:\s*([A-F0-9]{32})", html_text, re.I)
        domain_match = re.search(
            r'name="domain"[^>]*value="([^"]*)"',
            html_text,
            re.I,
        )
        return {
            "has_access": True,
            "api_key": key_match.group(1) if key_match else None,
            "domain": html.unescape(domain_match.group(1)).strip() if domain_match else None,
            "reason": "",
        }

    def get_web_api_key_page_state(self) -> dict:
        html_text = self.transport.request(
            "GET",
            f"{COMMUNITY_BASE_URL}/dev/apikey",
            cookies=self._community_cookies(),
            expected="text",
        )
        status = self.get_web_api_key_status()
        registration_form_visible = (
            'Register for a new Steam Web API Key' in html_text
            or 'Register Steam Web API Key' in html_text
            or 'name="domain"' in html_text
        )
        revoke_available = "Revoke My Steam Web API Key" in html_text or "Revoke my Steam Web API Key" in html_text
        terms_required = "Steam Web API Terms of Use" in html_text
        confirmation_hint = "Steam Guard confirmation" in html_text or "confirmation" in html_text.lower()
        return {
            "has_access": status.get("has_access", False),
            "api_key": status.get("api_key"),
            "domain": status.get("domain"),
            "reason": status.get("reason", ""),
            "registration_form_visible": registration_form_visible,
            "revoke_available": revoke_available,
            "terms_required": terms_required,
            "confirmation_hint": confirmation_hint,
            "raw_html": html_text,
        }

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
        return self._ensure_ajax_success(response, "Profile privacy update")

    def update_persona_name(self, steam_id=None, persona_name: str = "") -> dict:
        return self.edit_profile(
            steam_id,
            persona_name=persona_name,
        )

    def update_custom_url(self, custom_url: str, steam_id=None) -> dict:
        return self.edit_profile(
            steam_id,
            custom_url=custom_url,
        )

    def update_real_name(self, real_name: str, steam_id=None) -> dict:
        return self.edit_profile(
            steam_id,
            real_name=real_name,
        )

    def update_summary(self, summary: str, steam_id=None) -> dict:
        return self.edit_profile(
            steam_id,
            summary=summary,
        )

    def update_location(
        self,
        *,
        country: str,
        steam_id=None,
        state: Optional[str] = None,
        city: Optional[Union[int, str]] = None,
    ) -> dict:
        return self.edit_profile(
            steam_id,
            country=country,
            state=state,
            city=city,
        )

    def set_profile_public(self, steam_id=None) -> dict:
        return self.set_profile_privacy(
            steam_id,
            privacy_profile=3,
            privacy_inventory=3,
            privacy_inventory_gifts=3,
            privacy_owned_games=3,
            privacy_playtime=3,
            privacy_friends_list=3,
            comment_permission=0,
        )

    def set_profile_private(self, steam_id=None) -> dict:
        return self.set_profile_privacy(
            steam_id,
            privacy_profile=1,
            privacy_inventory=1,
            privacy_inventory_gifts=1,
            privacy_owned_games=1,
            privacy_playtime=1,
            privacy_friends_list=1,
            comment_permission=0,
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

        response = self.transport.request(
            "POST",
            f"{COMMUNITY_BASE_URL}/profiles/{normalized_steam_id}/edit/",
            data=data,
            headers=self._headers(f"{COMMUNITY_BASE_URL}/profiles/{normalized_steam_id}/edit/"),
            cookies=self._community_cookies(),
        )
        return self._ensure_ajax_success(response, "Profile update")

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
