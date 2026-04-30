from __future__ import annotations

import html
import re
import time
import xml.etree.ElementTree as ET
from typing import Dict, Optional

from steamcommunitykit.constants import COMMUNITY_BASE_URL
from steamcommunitykit.exceptions import (
    SteamAuthenticationError,
    SteamRateLimitError,
    SteamResponseError,
    SteamValidationError,
)
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.models import AvailabilityResult, CreatedGroup
from steamcommunitykit.utils import ensure_not_blank, normalize_group_slug


class GroupsService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport

    @staticmethod
    def _normalize_group_url_value(group_url: str) -> str:
        return normalize_group_slug(group_url)

    def _community_cookies(self) -> Dict[str, str]:
        credentials = self.transport.require_community_credentials()
        return {
            "steamLoginSecure": credentials.steam_login_secure_value,
            "sessionid": credentials.session_id,
        }

    def _optional_community_cookies(self) -> Optional[Dict[str, str]]:
        credentials = self.transport.community_credentials
        if credentials is None:
            return None
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

    @staticmethod
    def _parse_xml(text: str, error_prefix: str):
        try:
            return ET.fromstring(text.lstrip())
        except ET.ParseError as exc:
            raise SteamResponseError(
                f"{error_prefix}: {text[:500]}"
            ) from exc

    def _availability_check(self, check_type: str, value: str) -> AvailabilityResult:
        response_text = self.transport.request(
            "POST",
            f"{COMMUNITY_BASE_URL}/actions/AvailabilityCheck",
            data={"xml": "1", "type": check_type, "value": ensure_not_blank(value, "value")},
            headers=self._headers(f"{COMMUNITY_BASE_URL}/actions/GroupCreate"),
            cookies=self._community_cookies(),
            expected="text",
        )
        root = self._parse_xml(
            response_text,
            "Unexpected XML returned from Steam group availability check",
        )
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
        normalized_group_url = self._normalize_group_url_value(group_url)
        response_text = self.transport.request(
            "GET",
            f"{COMMUNITY_BASE_URL}/groups/{normalized_group_url}/memberslistxml/",
            params={"xml": "1"},
            cookies=self._optional_community_cookies(),
            expected="text",
        )
        root = self._parse_xml(
            response_text,
            "Unexpected XML returned while fetching group id64",
        )
        group_id64 = root.findtext("groupID64")
        if not group_id64:
            raise SteamResponseError("Steam did not return groupID64 for the requested group.")
        return group_id64

    def fetch_group_id(self, group_url: str) -> str:
        normalized_group_url = self._normalize_group_url_value(group_url)
        response_text = self.transport.request(
            "GET",
            f"{COMMUNITY_BASE_URL}/groups/{normalized_group_url}/edit",
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

    def get_group_details(self, group_url: str, page: int = 1) -> dict:
        normalized_group_url = self._normalize_group_url_value(group_url)
        response_text = self.transport.request(
            "GET",
            f"{COMMUNITY_BASE_URL}/groups/{normalized_group_url}/memberslistxml/",
            params={"xml": "1", "p": int(page)},
            expected="text",
        )
        root = self._parse_xml(
            response_text,
            "Unexpected XML returned while fetching group details",
        )
        details = root.find("groupDetails")
        if details is None:
            raise SteamResponseError("Steam did not return groupDetails for the requested group.")
        return {
            "group_id64": root.findtext("groupID64"),
            "group_name": details.findtext("groupName"),
            "group_url": details.findtext("groupURL"),
            "headline": details.findtext("headline"),
            "summary": details.findtext("summary"),
            "avatar_icon": details.findtext("avatarIcon"),
            "avatar_medium": details.findtext("avatarMedium"),
            "avatar_full": details.findtext("avatarFull"),
            "member_count": int(details.findtext("memberCount") or 0),
            "members_in_chat": int(details.findtext("membersInChat") or 0),
            "members_in_game": int(details.findtext("membersInGame") or 0),
            "members_online": int(details.findtext("membersOnline") or 0),
            "total_pages": int(root.findtext("totalPages") or 0),
            "current_page": int(root.findtext("currentPage") or page),
        }

    def get_group_members(self, group_url: str, page: int = 1) -> dict:
        normalized_group_url = self._normalize_group_url_value(group_url)
        response_text = self.transport.request(
            "GET",
            f"{COMMUNITY_BASE_URL}/groups/{normalized_group_url}/memberslistxml/",
            params={"xml": "1", "p": int(page)},
            expected="text",
        )
        root = self._parse_xml(
            response_text,
            "Unexpected XML returned while fetching group members",
        )
        member_nodes = root.findall("./members/steamID64")
        return {
            "group_id64": root.findtext("groupID64"),
            "group_url": normalized_group_url,
            "current_page": int(root.findtext("currentPage") or page),
            "total_pages": int(root.findtext("totalPages") or 0),
            "member_count": int(root.findtext("memberCount") or 0),
            "members": [member.text for member in member_nodes if member.text],
        }

    def get_all_group_members(self, group_url: str, *, start_page: int = 1, max_pages: Optional[int] = None) -> dict:
        current_page = int(start_page)
        if current_page <= 0:
            raise SteamValidationError("start_page must be greater than zero.")
        if max_pages is not None and int(max_pages) <= 0:
            raise SteamValidationError("max_pages must be greater than zero.")

        pages = []
        members = []
        seen_members = set()
        page_count = 0
        total_pages = None
        group_id64 = None
        member_count = None

        while True:
            page = self.get_group_members(group_url, page=current_page)
            pages.append(page)
            page_count += 1
            total_pages = page.get("total_pages", total_pages)
            group_id64 = page.get("group_id64", group_id64)
            member_count = page.get("member_count", member_count)

            for member in page.get("members", []):
                if member in seen_members:
                    continue
                seen_members.add(member)
                members.append(member)

            if max_pages is not None and page_count >= int(max_pages):
                break
            if total_pages is None or current_page >= int(total_pages):
                break
            current_page += 1

        return {
            "group_id64": group_id64,
            "group_url": group_url,
            "member_count": member_count,
            "pages_fetched": page_count,
            "start_page": start_page,
            "total_pages": total_pages or 0,
            "members": members,
            "pages": pages,
            "raw": pages[-1] if pages else {},
        }

    def get_group_member_summaries(self, group_url: str, *, page: int = 1, limit: Optional[int] = None) -> dict:
        from steamcommunitykit.services.users import UsersService

        payload = self.get_group_members(group_url, page=page)
        member_ids = payload.get("members", [])
        if limit is not None:
            member_ids = member_ids[: int(limit)]
        users = UsersService(self.transport)
        return {
            "group_id64": payload.get("group_id64"),
            "group_url": payload.get("group_url"),
            "current_page": payload.get("current_page"),
            "total_pages": payload.get("total_pages"),
            "member_count": payload.get("member_count"),
            "member_ids": member_ids,
            "members": users.get_player_summaries(member_ids) if member_ids else [],
            "raw": payload,
        }

    def get_group_member_summaries_map(self, group_url: str, *, page: int = 1, limit: Optional[int] = None) -> dict:
        payload = self.get_group_member_summaries(group_url, page=page, limit=limit)
        payload["members_by_steam_id"] = {
            str(member.get("steamid")): member
            for member in payload.get("members", [])
            if member.get("steamid")
        }
        return payload

    def get_all_group_member_summaries(
        self,
        group_url: str,
        *,
        start_page: int = 1,
        max_pages: Optional[int] = None,
        max_members: Optional[int] = None,
    ) -> dict:
        from steamcommunitykit.services.users import UsersService

        payload = self.get_all_group_members(group_url, start_page=start_page, max_pages=max_pages)
        member_ids = payload.get("members", [])
        if max_members is not None:
            member_ids = member_ids[: int(max_members)]
        users = UsersService(self.transport)
        return {
            "group_id64": payload.get("group_id64"),
            "group_url": payload.get("group_url"),
            "member_count": payload.get("member_count"),
            "pages_fetched": payload.get("pages_fetched"),
            "total_pages": payload.get("total_pages"),
            "member_ids": member_ids,
            "members": users.get_player_summaries(member_ids) if member_ids else [],
            "raw": payload,
        }

    def get_all_group_member_summaries_map(
        self,
        group_url: str,
        *,
        start_page: int = 1,
        max_pages: Optional[int] = None,
        max_members: Optional[int] = None,
    ) -> dict:
        payload = self.get_all_group_member_summaries(
            group_url,
            start_page=start_page,
            max_pages=max_pages,
            max_members=max_members,
        )
        payload["members_by_steam_id"] = {
            str(member.get("steamid")): member
            for member in payload.get("members", [])
            if member.get("steamid")
        }
        return payload

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
