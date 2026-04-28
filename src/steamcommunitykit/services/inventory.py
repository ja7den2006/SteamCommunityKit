from __future__ import annotations

from typing import Dict, List, Optional

from steamcommunitykit.constants import COMMUNITY_BASE_URL
from steamcommunitykit.exceptions import SteamResponseError
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import (
    validate_app_id,
    validate_steam_id,
    validate_uint32,
    validate_uint64,
)


class InventoryService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport

    def _community_cookies(self) -> Optional[Dict[str, str]]:
        credentials = self.transport.community_credentials
        if credentials is None:
            return None
        return {
            "steamLoginSecure": credentials.steam_login_secure_value,
            "sessionid": credentials.session_id,
        }

    def get_inventory(
        self,
        steam_id,
        app_id,
        context_id,
        *,
        language: Optional[str] = None,
        count: int = 2000,
        start_asset_id=None,
    ) -> dict:
        params = {
            "count": validate_uint32(count, "count"),
        }
        if language:
            params["l"] = language
        if start_asset_id is not None:
            params["start_assetid"] = validate_uint64(start_asset_id, "start_asset_id")
        response = self.transport.request(
            "GET",
            "{0}/inventory/{1}/{2}/{3}".format(
                COMMUNITY_BASE_URL,
                validate_steam_id(steam_id),
                validate_app_id(app_id),
                validate_uint64(context_id, "context_id"),
            ),
            params=params,
            cookies=self._community_cookies(),
            expected="raw",
        )
        try:
            return response.json()
        except ValueError as exc:
            raise SteamResponseError(
                "Steam returned a non-JSON inventory response: {0}".format(response.text[:500])
            ) from exc

    def get_inventory_items(
        self,
        steam_id,
        app_id,
        context_id,
        *,
        language: Optional[str] = None,
        count: int = 2000,
        start_asset_id=None,
    ) -> dict:
        payload = self.get_inventory(
            steam_id,
            app_id,
            context_id,
            language=language,
            count=count,
            start_asset_id=start_asset_id,
        )
        descriptions = {}
        for description in payload.get("descriptions", []):
            class_id = str(description.get("classid", ""))
            instance_id = str(description.get("instanceid", "0"))
            descriptions[(class_id, instance_id)] = description

        items = []
        for asset in payload.get("assets", []):
            class_id = str(asset.get("classid", ""))
            instance_id = str(asset.get("instanceid", "0"))
            item = dict(asset)
            item["description"] = descriptions.get((class_id, instance_id))
            items.append(item)

        return {
            "steamid": payload.get("steamid"),
            "app_id": payload.get("appid"),
            "context_id": payload.get("contextid"),
            "total_inventory_count": payload.get("total_inventory_count"),
            "more_items": payload.get("more_items", False),
            "last_assetid": payload.get("last_assetid"),
            "items": items,
            "assets": payload.get("assets", []),
            "descriptions": payload.get("descriptions", []),
            "raw": payload,
        }

    def get_full_inventory(
        self,
        steam_id,
        app_id,
        context_id,
        *,
        language: Optional[str] = None,
        count: int = 2000,
        start_asset_id=None,
        max_pages: Optional[int] = None,
    ) -> dict:
        pages: List[dict] = []
        all_assets = []
        all_descriptions = []
        seen_descriptions = set()
        next_asset_id = start_asset_id
        page_count = 0
        last_payload = None

        while True:
            payload = self.get_inventory(
                steam_id,
                app_id,
                context_id,
                language=language,
                count=count,
                start_asset_id=next_asset_id,
            )
            pages.append(payload)
            last_payload = payload
            page_count += 1

            for asset in payload.get("assets", []):
                all_assets.append(asset)
            for description in payload.get("descriptions", []):
                key = (
                    str(description.get("classid", "")),
                    str(description.get("instanceid", "0")),
                )
                if key in seen_descriptions:
                    continue
                seen_descriptions.add(key)
                all_descriptions.append(description)

            if max_pages is not None and page_count >= max_pages:
                break
            if not payload.get("more_items"):
                break

            next_asset_id = payload.get("last_assetid")
            if not next_asset_id:
                break

        if last_payload is None:
            raise SteamResponseError("Steam did not return any inventory payloads.")

        return {
            "steamid": last_payload.get("steamid"),
            "app_id": last_payload.get("appid"),
            "context_id": last_payload.get("contextid"),
            "total_inventory_count": last_payload.get("total_inventory_count"),
            "more_items": bool(last_payload.get("more_items", False)),
            "last_assetid": last_payload.get("last_assetid"),
            "pages_fetched": page_count,
            "pages": pages,
            "assets": all_assets,
            "descriptions": all_descriptions,
            "raw": last_payload,
        }

    def get_full_inventory_items(
        self,
        steam_id,
        app_id,
        context_id,
        *,
        language: Optional[str] = None,
        count: int = 2000,
        start_asset_id=None,
        max_pages: Optional[int] = None,
    ) -> dict:
        payload = self.get_full_inventory(
            steam_id,
            app_id,
            context_id,
            language=language,
            count=count,
            start_asset_id=start_asset_id,
            max_pages=max_pages,
        )
        descriptions = {}
        for description in payload.get("descriptions", []):
            class_id = str(description.get("classid", ""))
            instance_id = str(description.get("instanceid", "0"))
            descriptions[(class_id, instance_id)] = description

        items = []
        for asset in payload.get("assets", []):
            class_id = str(asset.get("classid", ""))
            instance_id = str(asset.get("instanceid", "0"))
            item = dict(asset)
            item["description"] = descriptions.get((class_id, instance_id))
            items.append(item)

        return {
            "steamid": payload.get("steamid"),
            "app_id": payload.get("app_id"),
            "context_id": payload.get("context_id"),
            "total_inventory_count": payload.get("total_inventory_count"),
            "more_items": payload.get("more_items", False),
            "last_assetid": payload.get("last_assetid"),
            "pages_fetched": payload.get("pages_fetched", 0),
            "items": items,
            "assets": payload.get("assets", []),
            "descriptions": payload.get("descriptions", []),
            "pages": payload.get("pages", []),
            "raw": payload.get("raw"),
        }
