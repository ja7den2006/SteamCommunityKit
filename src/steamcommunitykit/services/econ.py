from __future__ import annotations

from typing import Optional

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import ensure_not_blank, validate_app_id, validate_steam_id, validate_uint32, validate_uint64


class EconService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/IEconService"

    def get_trade_history(
        self,
        *,
        max_trades: int,
        start_after_time: int,
        start_after_trade_id,
        navigating_back: bool,
        get_descriptions: bool,
        language: str,
        include_failed: bool,
        include_total: bool,
    ) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetTradeHistory/v1/",
            params={
                "max_trades": validate_uint32(max_trades, "max_trades"),
                "start_after_time": validate_uint32(start_after_time, "start_after_time", allow_zero=True),
                "start_after_tradeid": validate_uint64(start_after_trade_id, "start_after_trade_id"),
                "navigating_back": int(navigating_back),
                "get_descriptions": int(get_descriptions),
                "language": ensure_not_blank(language, "language"),
                "include_failed": int(include_failed),
                "include_total": int(include_total),
            },
            require_api_key=True,
        )

    def get_trade_offers(
        self,
        *,
        get_sent_offers: bool,
        get_received_offers: bool,
        get_descriptions: bool,
        language: str,
        active_only: bool,
        historical_only: bool,
        time_historical_cutoff: int,
    ) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetTradeOffers/v1/",
            params={
                "get_sent_offers": int(get_sent_offers),
                "get_received_offers": int(get_received_offers),
                "get_descriptions": int(get_descriptions),
                "language": ensure_not_blank(language, "language"),
                "active_only": int(active_only),
                "historical_only": int(historical_only),
                "time_historical_cutoff": validate_uint32(
                    time_historical_cutoff,
                    "time_historical_cutoff",
                    allow_zero=True,
                ),
            },
            require_api_key=True,
        )

    def get_trade_offer(self, trade_offer_id, *, language: Optional[str] = None) -> dict:
        params = {
            "tradeofferid": validate_uint64(trade_offer_id, "trade_offer_id"),
        }
        if language is not None:
            params["language"] = ensure_not_blank(language, "language")
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetTradeOffer/v1/",
            params=params,
            require_api_key=True,
        )

    def get_trade_offers_summary(self, *, time_last_visit: Optional[int] = None) -> dict:
        params = {}
        if time_last_visit is not None:
            params["time_last_visit"] = validate_uint32(
                time_last_visit,
                "time_last_visit",
                allow_zero=True,
            )
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetTradeOffersSummary/v1/",
            params=params,
            require_api_key=True,
        )

    def flush_inventory_cache(self, steam_id, app_id, context_id) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/FlushInventoryCache/v1/",
            data={
                "steamid": validate_steam_id(steam_id),
                "appid": validate_app_id(app_id),
                "contextid": validate_uint64(context_id, "context_id"),
            },
            require_api_key=True,
        )

    def flush_asset_appearance_cache(self, app_id) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/FlushAssetAppearanceCache/v1/",
            data={"appid": validate_app_id(app_id)},
            require_api_key=True,
        )

    def flush_context_cache(self, app_id) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/FlushContextCache/v1/",
            data={"appid": validate_app_id(app_id)},
            require_api_key=True,
        )
