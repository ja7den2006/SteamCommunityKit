from __future__ import annotations

import json
import re
from urllib.parse import quote

from steamcommunitykit.constants import COMMUNITY_BASE_URL
from steamcommunitykit.exceptions import SteamResponseError
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import ensure_not_blank, validate_app_id, validate_uint32


class MarketService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport

    def get_price_overview(
        self,
        app_id,
        market_hash_name: str,
        *,
        currency: int = 1,
    ) -> dict:
        return self.transport.request(
            "GET",
            f"{COMMUNITY_BASE_URL}/market/priceoverview/",
            params={
                "appid": validate_app_id(app_id),
                "market_hash_name": ensure_not_blank(market_hash_name, "market_hash_name"),
                "currency": validate_uint32(currency, "currency"),
            },
        )

    def search_items(
        self,
        *,
        query: str = "",
        app_id=None,
        start: int = 0,
        count: int = 10,
        search_descriptions: bool = False,
        sort_column: str = "default",
        sort_dir: str = "desc",
    ) -> dict:
        params = {
            "query": query.strip(),
            "start": validate_uint32(start, "start", allow_zero=True),
            "count": validate_uint32(count, "count"),
            "search_descriptions": int(search_descriptions),
            "sort_column": ensure_not_blank(sort_column, "sort_column"),
            "sort_dir": ensure_not_blank(sort_dir, "sort_dir"),
            "norender": 1,
        }
        if app_id is not None:
            params["appid"] = validate_app_id(app_id)
        return self.transport.request(
            "GET",
            f"{COMMUNITY_BASE_URL}/market/search/render/",
            params=params,
        )

    def get_item_listings(
        self,
        app_id,
        market_hash_name: str,
        *,
        start: int = 0,
        count: int = 10,
        country: str = "US",
        language: str = "english",
        currency: int = 1,
    ) -> dict:
        return self.transport.request(
            "GET",
            "{0}/market/listings/{1}/{2}/render/".format(
                COMMUNITY_BASE_URL,
                validate_app_id(app_id),
                quote(ensure_not_blank(market_hash_name, "market_hash_name"), safe=""),
            ),
            params={
                "start": validate_uint32(start, "start", allow_zero=True),
                "count": validate_uint32(count, "count"),
                "country": ensure_not_blank(country, "country"),
                "language": ensure_not_blank(language, "language"),
                "currency": validate_uint32(currency, "currency"),
            },
        )

    def get_item_listings_page_html(self, app_id, market_hash_name: str) -> str:
        return self.transport.request(
            "GET",
            "{0}/market/listings/{1}/{2}".format(
                COMMUNITY_BASE_URL,
                validate_app_id(app_id),
                quote(ensure_not_blank(market_hash_name, "market_hash_name"), safe=""),
            ),
            expected="text",
        )

    def get_item_name_id(self, app_id, market_hash_name: str) -> int:
        html_text = self.get_item_listings_page_html(app_id, market_hash_name)
        match = re.search(r"Market_LoadOrderSpread\(\s*(\d+)\s*\)", html_text)
        if not match:
            raise SteamResponseError("Steam did not expose an item_nameid for the requested market item.")
        return int(match.group(1))

    def get_item_orders_histogram(
        self,
        *,
        item_name_id=None,
        app_id=None,
        market_hash_name: str = None,
        country: str = "US",
        language: str = "english",
        currency: int = 1,
    ) -> dict:
        if item_name_id is None:
            if app_id is None or market_hash_name is None:
                raise SteamResponseError(
                    "get_item_orders_histogram requires item_name_id or both app_id and market_hash_name."
                )
            item_name_id = self.get_item_name_id(app_id, market_hash_name)
        return self.transport.request(
            "GET",
            f"{COMMUNITY_BASE_URL}/market/itemordershistogram",
            params={
                "item_nameid": validate_uint32(item_name_id, "item_name_id"),
                "country": ensure_not_blank(country, "country"),
                "language": ensure_not_blank(language, "language"),
                "currency": validate_uint32(currency, "currency"),
            },
        )

    def get_price_history(self, app_id, market_hash_name: str) -> dict:
        html_text = self.get_item_listings_page_html(app_id, market_hash_name)
        line_match = re.search(r"var\s+line1=(\[.*?\]);", html_text, re.S)
        if not line_match:
            raise SteamResponseError("Steam did not expose price history for the requested market item.")
        try:
            prices = json.loads(line_match.group(1))
        except json.JSONDecodeError as exc:
            raise SteamResponseError("Steam returned malformed price history data.") from exc
        prefix_match = re.search(r"var\s+strFormatPrefix\s*=\s*'([^']*)';", html_text)
        suffix_match = re.search(r"var\s+strFormatSuffix\s*=\s*'([^']*)';", html_text)
        return {
            "success": True,
            "price_prefix": prefix_match.group(1) if prefix_match else "",
            "price_suffix": suffix_match.group(1) if suffix_match else "",
            "prices": prices,
        }
