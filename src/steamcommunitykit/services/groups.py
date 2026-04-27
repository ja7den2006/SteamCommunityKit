from __future__ import annotations

import html
import re
import time
import xml.etree.ElementTree as ET
from typing import Dict

from steamcommunitykit.constants import COMMUNITY_BASE_URL
from steamcommunitykit.exceptions import (
    SteamAuthenticationError,
    SteamRateLimitError,
    SteamResponseError,
    SteamValidationError,
)
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.models import AvailabilityResult, CreatedGroup
from steamcommunitykit.utils import ensure_not_blank


class GroupsService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport

    def _community_cookies(self) -> Dict[str, str]:
        credentials = self.transport.require_community_credentials()
        return {
            "steamLoginSecure": credentials.steam_login_secure_value,
            "sessionid": credentials.session_id,
        }

    @staticmethod
    def _headers(referer: str) -> Dict[str, str]:
        return {
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": COMMUNITY_BASE_URL,
            "Referer": referer,
            "X-Requested-With": "XMLHttpRequest",
        }

    def _availability_check(self, check_type: str, value: str) -> AvailabilityResult:
        response_text = self.transport.request(
            "POST",
            f"{COMMUNITY_BASE_URL}/actions/AvailabilityCheck",
            data={"xml": "1", "type": check_type, "value": ensure_not_blank(value, "value")},
            headers=self._headers(f"{COMMUNITY_BASE_URL}/actions/GroupCreate"),
            cookies=self._community_cookies(),
            expected="text",
        )
        try:
            root = ET.fromstring(response_text)
        except ET.ParseError as exc:
            raise SteamResponseError(
                f"Unexpected XML returned from Steam group availability check: {response_text[:500]}"
            ) from exc
        field_id = root.findtext("fieldId")
        raw_available = root.findtext("bResults")
        message = (root.findtext("sResults") or root.findtext("results") or "").strip()
        if "too many requests" in message.lower():
            raise SteamRateLimitError(
                message,
                status_code=429,
                payload={"field_id": field_id, "message": message},
            )
        available = raw_available == "1"
        return AvailabilityResult(
            field_id=field_id,
            available=available,
            message=message,
            raw_text=response_text,
        )

    @staticmethod
    def _extract_error_page_message(text: str) -> str:
        match = re.search(r'<div id="message">.*?<h3>(.*?)</h3>', text, re.S | re.I)
        if not match:
            return ""
        cleaned = re.sub(r"<.*?>", "", match.group(1))
        return html.unescape(cleaned).strip()

    def check_name_availability(self, name: str) -> AvailabilityResult:
        return self._availability_check("groupName", name)

    def check_url_availability(self, group_url: str) -> AvailabilityResult:
        return self._availability_check("groupLink", group_url)

    def check_tag_availability(self, abbreviation: str) -> AvailabilityResult:
        return self._availability_check("abbreviation", abbreviation)

    def fetch_group_id64(self, group_url: str) -> str:
        response_text = self.transport.request(
            "GET",
            f"{COMMUNITY_BASE_URL}/groups/{ensure_not_blank(group_url, 'group_url')}/memberslistxml/",
            params={"xml": "1"},
            cookies=self._community_cookies(),
            expected="text",
        )
        try:
            root = ET.fromstring(response_text)
        except ET.ParseError as exc:
            raise SteamResponseError(
                f"Unexpected XML returned while fetching group id64: {response_text[:500]}"
            ) from exc
        group_id64 = root.findtext("groupID64")
        if not group_id64:
            raise SteamResponseError("Steam did not return groupID64 for the requested group.")
        return group_id64

    def fetch_group_id(self, group_url: str) -> str:
        response_text = self.transport.request(
            "GET",
            f"{COMMUNITY_BASE_URL}/groups/{ensure_not_blank(group_url, 'group_url')}/edit",
            cookies=self._community_cookies(),
            expected="text",
        )
        marker = 'class="group_content group_summary">'
        if marker not in response_text:
            raise SteamResponseError("Unable to locate the editable group summary section.")
        tail = response_text.split(marker, 1)[1]
        if "<div class=\"formRowFields\">" not in tail:
            raise SteamResponseError("Unable to locate the group id field in the edit page.")
        group_id = tail.split("<div class=\"formRowFields\">", 1)[1].split("</div>", 1)[0]
        return group_id.strip()

    def create_group(
        self,
        *,
        name: str,
        abbreviation: str,
        group_url: str,
        public: bool = True,
        wait_for_sync: float = 10.0,
        validate_availability: bool = True,
    ) -> CreatedGroup:
        credentials = self.transport.require_community_credentials()
        name = ensure_not_blank(name, "name")
        abbreviation = ensure_not_blank(abbreviation, "abbreviation")
        group_url = ensure_not_blank(group_url, "group_url")

        if validate_availability:
            name_check = self.check_name_availability(name)
            if not name_check.available:
                raise SteamValidationError(name_check.message or "Group name is not available.")

            tag_check = self.check_tag_availability(abbreviation)
            if not tag_check.available:
                raise SteamValidationError(
                    tag_check.message or "Group abbreviation is not available."
                )

            url_check = self.check_url_availability(group_url)
            if not url_check.available:
                raise SteamValidationError(url_check.message or "Group URL is not available.")

        payload = {
            "sessionID": credentials.session_id,
            "step": "2",
            "groupName": name,
            "abbreviation": abbreviation,
            "groupLink": group_url,
        }
        if public:
            payload["bIsPublic"] = "1"

        first_response = self.transport.request(
            "POST",
            f"{COMMUNITY_BASE_URL}/actions/GroupCreate",
            data=payload,
            headers=self._headers(f"{COMMUNITY_BASE_URL}/actions/GroupCreate"),
            cookies=self._community_cookies(),
            expected="raw",
        )
        error_message = self._extract_error_page_message(first_response.text)
        if error_message:
            if "does not meet the requirements" in error_message.lower():
                raise SteamAuthenticationError(error_message, status_code=403)
            raise SteamValidationError(error_message)

        second_response = self.transport.request(
            "POST",
            f"{COMMUNITY_BASE_URL}/actions/GroupCreate",
            data=payload,
            headers=self._headers(f"{COMMUNITY_BASE_URL}/actions/GroupCreate"),
            cookies=self._community_cookies(),
            expected="raw",
        )
        error_message = self._extract_error_page_message(second_response.text)
        if error_message:
            if "does not meet the requirements" in error_message.lower():
                raise SteamAuthenticationError(error_message, status_code=403)
            raise SteamValidationError(error_message)

        time.sleep(wait_for_sync)
        try:
            group_id = self.fetch_group_id(group_url)
            group_id64 = self.fetch_group_id64(group_url)
        except SteamResponseError as exc:
            raise SteamResponseError(
                "Steam did not confirm the group creation after sync delay."
            ) from exc

        return CreatedGroup(
            name=name,
            abbreviation=abbreviation,
            group_id=group_id,
            group_id64=group_id64,
            group_url=group_url,
            public=public,
        )
