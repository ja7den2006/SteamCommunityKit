from __future__ import annotations

from typing import Optional

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import ensure_not_blank, validate_uint32, validate_uint64


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

    @staticmethod
    def _normalize_trade_asset(asset: dict) -> dict:
        return {
            "appid": asset.get("appid"),
            "contextid": asset.get("contextid"),
            "assetid": asset.get("assetid"),
            "amount": asset.get("amount"),
            "classid": asset.get("classid"),
            "instanceid": asset.get("instanceid"),
            "missing": asset.get("missing"),
            "est_usd": asset.get("est_usd"),
            "raw": asset,
        }

    @classmethod
    def _normalize_trade_offer(cls, offer: dict) -> dict:
        items_to_give = [cls._normalize_trade_asset(item) for item in offer.get("items_to_give", [])]
        items_to_receive = [cls._normalize_trade_asset(item) for item in offer.get("items_to_receive", [])]
        return {
            "trade_offer_id": offer.get("tradeofferid"),
            "account_id_other": offer.get("accountid_other"),
            "message": offer.get("message"),
            "expiration_time": offer.get("expiration_time"),
            "trade_offer_state": offer.get("trade_offer_state"),
            "is_our_offer": offer.get("is_our_offer"),
            "time_created": offer.get("time_created"),
            "time_updated": offer.get("time_updated"),
            "from_real_time_trade": offer.get("from_real_time_trade"),
            "escrow_end_date": offer.get("escrow_end_date"),
            "confirmation_method": offer.get("confirmation_method"),
            "items_to_give": items_to_give,
            "items_to_receive": items_to_receive,
            "items_to_give_count": len(items_to_give),
            "items_to_receive_count": len(items_to_receive),
            "raw": offer,
        }

    @classmethod
    def _normalize_trade_history_entry(cls, trade: dict) -> dict:
        assets_given = [cls._normalize_trade_asset(item) for item in trade.get("assets_given", [])]
        assets_received = [cls._normalize_trade_asset(item) for item in trade.get("assets_received", [])]
        return {
            "trade_id": trade.get("tradeid"),
            "steamid_other": trade.get("steamid_other"),
            "time_init": trade.get("time_init"),
            "status": trade.get("status"),
            "assets_given": assets_given,
            "assets_received": assets_received,
            "assets_given_count": len(assets_given),
            "assets_received_count": len(assets_received),
            "raw": trade,
        }

    def get_trade_offers_summary_view(
        self,
        *,
        get_sent_offers: bool = True,
        get_received_offers: bool = True,
        get_descriptions: bool = False,
        language: str = "english",
        active_only: bool = True,
        historical_only: bool = False,
        time_historical_cutoff: int = 0,
    ) -> dict:
        payload = self.get_trade_offers(
            get_sent_offers=get_sent_offers,
            get_received_offers=get_received_offers,
            get_descriptions=get_descriptions,
            language=language,
            active_only=active_only,
            historical_only=historical_only,
            time_historical_cutoff=time_historical_cutoff,
        )
        sent = [self._normalize_trade_offer(offer) for offer in payload.get("trade_offers_sent", [])]
        received = [self._normalize_trade_offer(offer) for offer in payload.get("trade_offers_received", [])]
        descriptions = payload.get("descriptions", []) or []
        return {
            "sent": sent,
            "received": received,
            "sent_count": len(sent),
            "received_count": len(received),
            "description_count": len(descriptions),
            "next_cursor": payload.get("next_cursor"),
            "raw": payload,
        }

    def get_trade_history_summary(
        self,
        *,
        max_trades: int = 100,
        start_after_time: int = 0,
        start_after_trade_id=1,
        navigating_back: bool = False,
        get_descriptions: bool = False,
        language: str = "english",
        include_failed: bool = True,
        include_total: bool = True,
    ) -> dict:
        payload = self.get_trade_history(
            max_trades=max_trades,
            start_after_time=start_after_time,
            start_after_trade_id=start_after_trade_id,
            navigating_back=navigating_back,
            get_descriptions=get_descriptions,
            language=language,
            include_failed=include_failed,
            include_total=include_total,
        )
        trades = [self._normalize_trade_history_entry(trade) for trade in payload.get("trades", [])]
        descriptions = payload.get("descriptions", []) or []
        return {
            "trades": trades,
            "trade_count": len(trades),
            "total_trades": payload.get("total_trades"),
            "more": payload.get("more"),
            "description_count": len(descriptions),
            "raw": payload,
        }

    def get_trade_offer_summary(self, trade_offer_id, *, language: str = "english") -> dict:
        payload = self.get_trade_offer(trade_offer_id, language=language)
        offer = payload.get("offer", {}) if isinstance(payload.get("offer"), dict) else payload.get("trade_offer", {})
        descriptions = payload.get("descriptions", []) or []
        normalized = self._normalize_trade_offer(offer) if offer else {}
        normalized["description_count"] = len(descriptions)
        normalized["raw"] = payload
        return normalized

    def get_trade_offer_totals(self, *, time_last_visit: Optional[int] = None) -> dict:
        payload = self.get_trade_offers_summary(time_last_visit=time_last_visit)
        return {
            "pending_received_count": payload.get("pending_received_count", 0),
            "new_received_count": payload.get("new_received_count", 0),
            "updated_received_count": payload.get("updated_received_count", 0),
            "historical_received_count": payload.get("historical_received_count", 0),
            "historical_sent_count": payload.get("historical_sent_count", 0),
            "escrow_received_count": payload.get("escrow_received_count", 0),
            "escrow_sent_count": payload.get("escrow_sent_count", 0),
            "raw": payload,
        }
