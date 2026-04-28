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

    @staticmethod
    def _normalize_description(description: Optional[dict]) -> Optional[dict]:
        if not description:
            return None
        return {
            "app_id": description.get("appid"),
            "class_id": description.get("classid"),
            "instance_id": description.get("instanceid"),
            "name": description.get("name") or "",
            "market_name": description.get("market_name") or "",
            "market_hash_name": description.get("market_hash_name") or "",
            "type": description.get("type") or "",
            "icon_url": description.get("icon_url") or "",
            "icon_url_large": description.get("icon_url_large") or "",
            "tradable": description.get("tradable"),
            "marketable": description.get("marketable"),
            "commodity": description.get("commodity"),
            "name_color": description.get("name_color") or "",
            "background_color": description.get("background_color") or "",
            "tags": description.get("tags", []),
            "descriptions": description.get("descriptions", []),
            "owner_descriptions": description.get("owner_descriptions", []),
            "actions": description.get("actions", []),
            "market_actions": description.get("market_actions", []),
            "owner_actions": description.get("owner_actions", []),
            "fraudwarnings": description.get("fraudwarnings", []),
            "raw": description,
        }

    def _attach_descriptions(self, payload: dict) -> dict:
        descriptions = {}
        normalized_descriptions = {}
        for description in payload.get("descriptions", []):
            class_id = str(description.get("classid", ""))
            instance_id = str(description.get("instanceid", "0"))
            descriptions[(class_id, instance_id)] = description
            normalized_descriptions[(class_id, instance_id)] = self._normalize_description(description)

        items = []
        for asset in payload.get("assets", []):
            class_id = str(asset.get("classid", ""))
            instance_id = str(asset.get("instanceid", "0"))
            item = dict(asset)
            item["description"] = descriptions.get((class_id, instance_id))
            item["normalized_description"] = normalized_descriptions.get((class_id, instance_id))
            items.append(item)
        return {
            "items": items,
            "normalized_descriptions": list(normalized_descriptions.values()),
        }

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
        attached = self._attach_descriptions(payload)

        return {
            "steamid": payload.get("steamid"),
            "app_id": payload.get("appid"),
            "context_id": payload.get("contextid"),
            "total_inventory_count": payload.get("total_inventory_count"),
            "more_items": payload.get("more_items", False),
            "last_assetid": payload.get("last_assetid"),
            "items": attached["items"],
            "assets": payload.get("assets", []),
            "descriptions": payload.get("descriptions", []),
            "normalized_descriptions": attached["normalized_descriptions"],
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
        attached = self._attach_descriptions(payload)

        return {
            "steamid": payload.get("steamid"),
            "app_id": payload.get("app_id"),
            "context_id": payload.get("context_id"),
            "total_inventory_count": payload.get("total_inventory_count"),
            "more_items": payload.get("more_items", False),
            "last_assetid": payload.get("last_assetid"),
            "pages_fetched": payload.get("pages_fetched", 0),
            "items": attached["items"],
            "assets": payload.get("assets", []),
            "descriptions": payload.get("descriptions", []),
            "normalized_descriptions": attached["normalized_descriptions"],
            "pages": payload.get("pages", []),
            "raw": payload.get("raw"),
        }

    @staticmethod
    def _normalize_inventory_item(item: dict) -> dict:
        description = item.get("normalized_description")
        if description is None:
            description = InventoryService._normalize_description(item.get("description"))
        return {
            "asset_id": item.get("assetid") or item.get("asset_id"),
            "class_id": item.get("classid"),
            "instance_id": item.get("instanceid"),
            "amount": item.get("amount"),
            "app_id": item.get("appid") or (description or {}).get("app_id"),
            "context_id": item.get("contextid"),
            "name": (description or {}).get("name", ""),
            "market_name": (description or {}).get("market_name", ""),
            "market_hash_name": (description or {}).get("market_hash_name", ""),
            "type": (description or {}).get("type", ""),
            "tradable": (description or {}).get("tradable"),
            "marketable": (description or {}).get("marketable"),
            "commodity": (description or {}).get("commodity"),
            "icon_url": (description or {}).get("icon_url", ""),
            "name_color": (description or {}).get("name_color", ""),
            "description": description,
            "raw": item,
        }

    def get_inventory_items_summary(
        self,
        steam_id,
        app_id,
        context_id,
        *,
        language: Optional[str] = None,
        count: int = 2000,
        start_asset_id=None,
    ) -> dict:
        payload = self.get_inventory_items(
            steam_id,
            app_id,
            context_id,
            language=language,
            count=count,
            start_asset_id=start_asset_id,
        )
        items = [self._normalize_inventory_item(item) for item in payload.get("items", [])]
        items_by_asset_id = {
            str(item["asset_id"]): item
            for item in items
            if item.get("asset_id") is not None
        }
        return {
            "steamid": payload.get("steamid"),
            "app_id": payload.get("app_id"),
            "context_id": payload.get("context_id"),
            "total_inventory_count": payload.get("total_inventory_count"),
            "more_items": payload.get("more_items", False),
            "last_assetid": payload.get("last_assetid"),
            "items": items,
            "items_by_asset_id": items_by_asset_id,
            "raw": payload,
        }

    def find_inventory_items(
        self,
        steam_id,
        app_id,
        context_id,
        *,
        language: Optional[str] = None,
        count: int = 2000,
        start_asset_id=None,
        name_query: Optional[str] = None,
        market_hash_name: Optional[str] = None,
        tradable: Optional[bool] = None,
        marketable: Optional[bool] = None,
    ) -> dict:
        payload = self.get_inventory_items_summary(
            steam_id,
            app_id,
            context_id,
            language=language,
            count=count,
            start_asset_id=start_asset_id,
        )
        query = (name_query or "").strip().lower()
        exact_hash = (market_hash_name or "").strip().lower()
        matches = []
        for item in payload.get("items", []):
            if query:
                haystack = " ".join(
                    part for part in [item.get("name"), item.get("market_name"), item.get("market_hash_name")] if part
                ).lower()
                if query not in haystack:
                    continue
            if exact_hash and (item.get("market_hash_name") or "").lower() != exact_hash:
                continue
            if tradable is not None and bool(item.get("tradable")) is not bool(tradable):
                continue
            if marketable is not None and bool(item.get("marketable")) is not bool(marketable):
                continue
            matches.append(item)
        return {
            "steamid": payload.get("steamid"),
            "app_id": payload.get("app_id"),
            "context_id": payload.get("context_id"),
            "count": len(matches),
            "items": matches,
            "raw": payload,
        }

    def get_full_inventory_items_summary(
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
        payload = self.get_full_inventory_items(
            steam_id,
            app_id,
            context_id,
            language=language,
            count=count,
            start_asset_id=start_asset_id,
            max_pages=max_pages,
        )
        items = [self._normalize_inventory_item(item) for item in payload.get("items", [])]
        items_by_asset_id = {
            str(item["asset_id"]): item
            for item in items
            if item.get("asset_id") is not None
        }
        return {
            "steamid": payload.get("steamid"),
            "app_id": payload.get("app_id"),
            "context_id": payload.get("context_id"),
            "total_inventory_count": payload.get("total_inventory_count"),
            "more_items": payload.get("more_items", False),
            "last_assetid": payload.get("last_assetid"),
            "pages_fetched": payload.get("pages_fetched", 0),
            "items": items,
            "items_by_asset_id": items_by_asset_id,
            "pages": payload.get("pages", []),
            "raw": payload,
        }

    def find_full_inventory_items(
        self,
        steam_id,
        app_id,
        context_id,
        *,
        language: Optional[str] = None,
        count: int = 2000,
        start_asset_id=None,
        max_pages: Optional[int] = None,
        name_query: Optional[str] = None,
        market_hash_name: Optional[str] = None,
        tradable: Optional[bool] = None,
        marketable: Optional[bool] = None,
    ) -> dict:
        payload = self.get_full_inventory_items_summary(
            steam_id,
            app_id,
            context_id,
            language=language,
            count=count,
            start_asset_id=start_asset_id,
            max_pages=max_pages,
        )
        query = (name_query or "").strip().lower()
        exact_hash = (market_hash_name or "").strip().lower()
        matches = []
        for item in payload.get("items", []):
            if query:
                haystack = " ".join(
                    part for part in [item.get("name"), item.get("market_name"), item.get("market_hash_name")] if part
                ).lower()
                if query not in haystack:
                    continue
            if exact_hash and (item.get("market_hash_name") or "").lower() != exact_hash:
                continue
            if tradable is not None and bool(item.get("tradable")) is not bool(tradable):
                continue
            if marketable is not None and bool(item.get("marketable")) is not bool(marketable):
                continue
            matches.append(item)
        return {
            "steamid": payload.get("steamid"),
            "app_id": payload.get("app_id"),
            "context_id": payload.get("context_id"),
            "pages_fetched": payload.get("pages_fetched", 0),
            "count": len(matches),
            "items": matches,
            "raw": payload,
        }
