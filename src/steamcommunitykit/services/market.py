from __future__ import annotations

from urllib.parse import quote

from steamcommunitykit.constants import COMMUNITY_BASE_URL
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
