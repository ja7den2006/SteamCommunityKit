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

    @staticmethod
    def _normalize_search_item(item: dict) -> dict:
        asset_description = item.get("asset_description") or {}
        app_id = asset_description.get("appid")
        market_hash_name = asset_description.get("market_hash_name") or item.get("hash_name") or ""
        return {
            "name": item.get("name") or asset_description.get("name") or market_hash_name,
            "hash_name": item.get("hash_name") or market_hash_name,
            "market_hash_name": market_hash_name,
            "market_name": asset_description.get("market_name") or item.get("name"),
            "sell_listings": item.get("sell_listings"),
            "sell_price": item.get("sell_price"),
            "sell_price_text": item.get("sell_price_text"),
            "sale_price_text": item.get("sale_price_text"),
            "app_name": item.get("app_name"),
            "app_icon": item.get("app_icon"),
            "app_id": app_id,
            "commodity": asset_description.get("commodity"),
            "tradable": asset_description.get("tradable"),
            "type": asset_description.get("type"),
            "name_color": asset_description.get("name_color"),
            "icon_url": asset_description.get("icon_url"),
            "background_color": asset_description.get("background_color"),
            "market_url": (
                "{0}/market/listings/{1}/{2}".format(
                    COMMUNITY_BASE_URL,
                    app_id,
                    quote(market_hash_name, safe=""),
                )
                if app_id and market_hash_name
                else None
            ),
            "asset_description": asset_description,
            "raw": item,
        }

    @staticmethod
    def _coerce_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_int(value):
        try:
            return int(str(value).replace(",", ""))
        except (TypeError, ValueError):
            return None

    def search_items_summary(
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
        payload = self.search_items(
            query=query,
            app_id=app_id,
            start=start,
            count=count,
            search_descriptions=search_descriptions,
            sort_column=sort_column,
            sort_dir=sort_dir,
        )
        results = payload.get("results", [])
        return {
            "success": payload.get("success"),
            "start": payload.get("start", start),
            "pagesize": payload.get("pagesize", len(results)),
            "total_count": payload.get("total_count", len(results)),
            "searchdata": payload.get("searchdata", {}),
            "items": [self._normalize_search_item(item) for item in results],
            "raw": payload,
        }

    def search_all_items(
        self,
        *,
        query: str = "",
        app_id=None,
        start: int = 0,
        count: int = 10,
        search_descriptions: bool = False,
        sort_column: str = "default",
        sort_dir: str = "desc",
        max_pages=None,
        max_results=None,
    ) -> dict:
        current_start = validate_uint32(start, "start", allow_zero=True)
        page_limit = None if max_pages is None else validate_uint32(max_pages, "max_pages")
        result_limit = None if max_results is None else validate_uint32(max_results, "max_results")
        page_count = 0
        pages = []
        items = []
        total_count = None

        while True:
            page = self.search_items_summary(
                query=query,
                app_id=app_id,
                start=current_start,
                count=count,
                search_descriptions=search_descriptions,
                sort_column=sort_column,
                sort_dir=sort_dir,
            )
            pages.append(page)
            page_count += 1
            total_count = page.get("total_count", total_count)

            page_items = page.get("items", [])
            items.extend(page_items)

            if result_limit is not None and len(items) >= result_limit:
                items = items[:result_limit]
                break
            if page_limit is not None and page_count >= page_limit:
                break

            page_size = page.get("pagesize", len(page_items)) or len(page_items)
            if page_size <= 0 or not page_items:
                break

            current_start += page_size
            if total_count is not None and current_start >= int(total_count):
                break

        return {
            "success": pages[-1].get("success") if pages else True,
            "start": start,
            "pages_fetched": page_count,
            "total_count": total_count if total_count is not None else len(items),
            "items": items,
            "pages": pages,
            "raw": pages[-1].get("raw") if pages else {},
        }

    def find_search_item(
        self,
        query: str,
        *,
        app_id=None,
        count: int = 10,
        search_descriptions: bool = False,
        sort_column: str = "default",
        sort_dir: str = "desc",
        max_pages=None,
        max_results=None,
        market_hash_name: Optional[str] = None,
        name: Optional[str] = None,
        prefer_exact: bool = True,
    ) -> dict:
        payload = self.search_all_items(
            query=query,
            app_id=app_id,
            count=count,
            search_descriptions=search_descriptions,
            sort_column=sort_column,
            sort_dir=sort_dir,
            max_pages=max_pages,
            max_results=max_results,
        )
        normalized_hash = (market_hash_name or "").strip().lower()
        normalized_name = (name or "").strip().lower()

        exact_matches = []
        partial_matches = []
        for item in payload.get("items", []):
            item_hash = (item.get("market_hash_name") or item.get("hash_name") or "").lower()
            item_name = (item.get("name") or "").lower()
            if normalized_hash and item_hash == normalized_hash:
                exact_matches.append(item)
                continue
            if normalized_name and item_name == normalized_name:
                exact_matches.append(item)
                continue
            if normalized_hash and normalized_hash in item_hash:
                partial_matches.append(item)
                continue
            if normalized_name and normalized_name in item_name:
                partial_matches.append(item)

        if not normalized_hash and not normalized_name:
            exact_matches = payload.get("items", [])[:1]

        matches = exact_matches if prefer_exact and exact_matches else exact_matches + partial_matches
        return {
            "query": query,
            "match": matches[0] if matches else None,
            "matches": matches,
            "count": len(matches),
            "matched_exactly": bool(matches and matches[0] in exact_matches),
            "raw": payload,
        }

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

    def get_item_listings_summary(
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
        payload = self.get_item_listings(
            app_id,
            market_hash_name,
            start=start,
            count=count,
            country=country,
            language=language,
            currency=currency,
        )
        assets = payload.get("assets") or {}
        listinginfo = payload.get("listinginfo") or {}

        asset_map = {}
        for app_assets in assets.values():
            for context_assets in app_assets.values():
                for asset_id, asset in context_assets.items():
                    item = dict(asset)
                    item["asset_id"] = asset_id
                    asset_map[str(asset_id)] = item

        listings = []
        for listing_id, listing in listinginfo.items():
            asset = None
            asset_ref = listing.get("asset") or {}
            if asset_ref.get("id") is not None:
                asset = asset_map.get(str(asset_ref.get("id")))
            listings.append(
                {
                    "listing_id": listing_id,
                    "price": listing.get("price"),
                    "fee": listing.get("fee"),
                    "converted_price": listing.get("converted_price"),
                    "converted_fee": listing.get("converted_fee"),
                    "publisher_fee_app": listing.get("publisher_fee_app"),
                    "publisher_fee_percent": listing.get("publisher_fee_percent"),
                    "asset_id": asset_ref.get("id"),
                    "currencyid": listing.get("currencyid"),
                    "asset": asset,
                    "raw": listing,
                }
            )
        listings.sort(key=lambda item: (item.get("converted_price") or item.get("price") or 0, item.get("listing_id") or ""))
        cheapest = listings[0] if listings else None
        return {
            "success": payload.get("success"),
            "total_count": payload.get("total_count", len(listings)),
            "start": payload.get("start", start),
            "pagesize": payload.get("pagesize", len(listings)),
            "hover_prefix": payload.get("hover_prefix", ""),
            "hover_suffix": payload.get("hover_suffix", ""),
            "listings": listings,
            "assets": asset_map,
            "cheapest_listing": cheapest,
            "raw": payload,
        }

    def get_all_item_listings_summary(
        self,
        app_id,
        market_hash_name: str,
        *,
        start: int = 0,
        count: int = 10,
        country: str = "US",
        language: str = "english",
        currency: int = 1,
        max_pages=None,
        max_listings=None,
    ) -> dict:
        current_start = validate_uint32(start, "start", allow_zero=True)
        page_limit = None if max_pages is None else validate_uint32(max_pages, "max_pages")
        listing_limit = None if max_listings is None else validate_uint32(max_listings, "max_listings")
        page_count = 0
        pages = []
        listings = []
        seen_listing_ids = set()
        total_count = None
        assets = {}

        while True:
            page = self.get_item_listings_summary(
                app_id,
                market_hash_name,
                start=current_start,
                count=count,
                country=country,
                language=language,
                currency=currency,
            )
            pages.append(page)
            page_count += 1
            total_count = page.get("total_count", total_count)
            assets.update(page.get("assets", {}))

            page_listings = page.get("listings", [])
            for listing in page_listings:
                listing_id = listing.get("listing_id")
                if listing_id and listing_id in seen_listing_ids:
                    continue
                if listing_id:
                    seen_listing_ids.add(listing_id)
                listings.append(listing)
                if listing_limit is not None and len(listings) >= listing_limit:
                    listings = listings[:listing_limit]
                    break

            if listing_limit is not None and len(listings) >= listing_limit:
                break
            if page_limit is not None and page_count >= page_limit:
                break

            page_size = page.get("pagesize", len(page_listings)) or len(page_listings)
            if page_size <= 0 or not page_listings:
                break

            current_start += page_size
            if total_count is not None and current_start >= int(total_count):
                break

        cheapest = listings[0] if listings else None
        return {
            "success": pages[-1].get("success") if pages else True,
            "start": start,
            "pages_fetched": page_count,
            "total_count": total_count if total_count is not None else len(listings),
            "listings": listings,
            "assets": assets,
            "cheapest_listing": cheapest,
            "pages": pages,
            "raw": pages[-1].get("raw") if pages else {},
        }

    def find_item_listings(
        self,
        app_id,
        market_hash_name: str,
        *,
        start: int = 0,
        count: int = 10,
        country: str = "US",
        language: str = "english",
        currency: int = 1,
        max_pages=None,
        max_listings=None,
        max_price=None,
    ) -> dict:
        payload = self.get_all_item_listings_summary(
            app_id,
            market_hash_name,
            start=start,
            count=count,
            country=country,
            language=language,
            currency=currency,
            max_pages=max_pages,
            max_listings=max_listings,
        )
        matches = []
        ceiling = None if max_price is None else int(max_price)
        for listing in payload.get("listings", []):
            price = listing.get("converted_price") or listing.get("price")
            if ceiling is not None and (price is None or int(price) > ceiling):
                continue
            matches.append(listing)
        return {
            "count": len(matches),
            "listings": matches,
            "pages_fetched": payload.get("pages_fetched", 0),
            "raw": payload,
        }

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
        two_factor: int = 0,
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
                "two_factor": validate_uint32(two_factor, "two_factor", allow_zero=True),
            },
        )

    @staticmethod
    def _strip_html(value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"<.*?>", "", value or "")).strip()

    def _parse_order_rows(self, table_html: str) -> list:
        rows = []
        for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", table_html or "", re.I | re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.I | re.S)
            if len(cells) < 2:
                continue
            price_text = self._strip_html(cells[0])
            quantity_text = self._strip_html(cells[1])
            rows.append(
                {
                    "price_text": price_text,
                    "quantity_text": quantity_text,
                }
            )
        return rows

    def get_item_orders_summary(
        self,
        *,
        item_name_id=None,
        app_id=None,
        market_hash_name: str = None,
        country: str = "US",
        language: str = "english",
        currency: int = 1,
        two_factor: int = 0,
    ) -> dict:
        if item_name_id is None:
            if app_id is None or market_hash_name is None:
                raise SteamResponseError(
                    "get_item_orders_summary requires item_name_id or both app_id and market_hash_name."
                )
            item_name_id = self.get_item_name_id(app_id, market_hash_name)
        histogram = self.get_item_orders_histogram(
            item_name_id=item_name_id,
            country=country,
            language=language,
            currency=currency,
            two_factor=two_factor,
        )
        return {
            "success": histogram.get("success"),
            "item_name_id": validate_uint32(item_name_id, "item_name_id"),
            "buy_order_count": histogram.get("buy_order_count"),
            "buy_order_price": histogram.get("buy_order_price"),
            "buy_order_summary": self._strip_html(histogram.get("buy_order_summary", "")),
            "buy_orders": self._parse_order_rows(histogram.get("buy_order_table", "")),
            "sell_order_count": histogram.get("sell_order_count"),
            "sell_order_price": histogram.get("sell_order_price"),
            "sell_order_summary": self._strip_html(histogram.get("sell_order_summary", "")),
            "sell_orders": self._parse_order_rows(histogram.get("sell_order_table", "")),
            "highest_buy_order": histogram.get("highest_buy_order"),
            "lowest_sell_order": histogram.get("lowest_sell_order"),
            "graph_max_y": histogram.get("graph_max_y"),
            "graph_min_x": histogram.get("graph_min_x"),
            "graph_max_x": histogram.get("graph_max_x"),
            "price_prefix": histogram.get("price_prefix", ""),
            "price_suffix": histogram.get("price_suffix", ""),
            "raw": histogram,
        }

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

    def get_price_history_summary(self, app_id, market_hash_name: str) -> dict:
        payload = self.get_price_history(app_id, market_hash_name)
        rows = payload.get("prices", [])
        parsed_rows = []
        numeric_prices = []
        numeric_volumes = []

        for row in rows:
            if len(row) < 3:
                continue
            price = self._coerce_float(row[1])
            volume = self._coerce_int(row[2])
            parsed = {
                "date": row[0],
                "price": price,
                "volume": volume,
                "raw": row,
            }
            parsed_rows.append(parsed)
            if price is not None:
                numeric_prices.append(price)
            if volume is not None:
                numeric_volumes.append(volume)

        latest = parsed_rows[-1] if parsed_rows else {}
        average_price = round(sum(numeric_prices) / len(numeric_prices), 4) if numeric_prices else None
        average_volume = round(sum(numeric_volumes) / len(numeric_volumes), 2) if numeric_volumes else None

        return {
            "app_id": validate_app_id(app_id),
            "market_hash_name": ensure_not_blank(market_hash_name, "market_hash_name"),
            "point_count": len(parsed_rows),
            "latest_date": latest.get("date"),
            "latest_price": latest.get("price"),
            "latest_volume": latest.get("volume"),
            "min_price": min(numeric_prices) if numeric_prices else None,
            "max_price": max(numeric_prices) if numeric_prices else None,
            "average_price": average_price,
            "average_volume": average_volume,
            "price_prefix": payload.get("price_prefix", ""),
            "price_suffix": payload.get("price_suffix", ""),
            "points": parsed_rows,
            "raw": payload,
        }

    def get_market_price_snapshot(
        self,
        app_id,
        market_hash_name: str,
        *,
        currency: int = 1,
        country: str = "US",
        language: str = "english",
        listings_count: int = 10,
    ) -> dict:
        item_name_id = self.get_item_name_id(app_id, market_hash_name)
        price_overview = self.get_price_overview(app_id, market_hash_name, currency=currency)
        orders = self.get_item_orders_summary(
            item_name_id=item_name_id,
            country=country,
            language=language,
            currency=currency,
        )
        listings = self.get_item_listings_summary(
            app_id,
            market_hash_name,
            count=listings_count,
            country=country,
            language=language,
            currency=currency,
        )
        cheapest_listing = listings.get("cheapest_listing") or {}
        return {
            "app_id": validate_app_id(app_id),
            "market_hash_name": ensure_not_blank(market_hash_name, "market_hash_name"),
            "item_name_id": item_name_id,
            "lowest_price_text": price_overview.get("lowest_price"),
            "median_price_text": price_overview.get("median_price"),
            "volume_text": price_overview.get("volume"),
            "highest_buy_order": orders.get("highest_buy_order"),
            "lowest_sell_order": orders.get("lowest_sell_order"),
            "buy_order_count": orders.get("buy_order_count"),
            "sell_order_count": orders.get("sell_order_count"),
            "listing_count": listings.get("total_count"),
            "cheapest_listing_price": cheapest_listing.get("converted_price") or cheapest_listing.get("price"),
            "cheapest_listing_fee": cheapest_listing.get("converted_fee") or cheapest_listing.get("fee"),
            "price_overview": price_overview,
            "orders": orders,
            "listings": listings,
        }
