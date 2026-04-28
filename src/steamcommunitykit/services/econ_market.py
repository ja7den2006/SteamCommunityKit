from __future__ import annotations

from typing import Optional

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import ensure_not_blank, validate_app_id, validate_steam_id, validate_uint32, validate_uint64


class EconMarketService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/IEconMarketService"

    def get_market_eligibility(self, steam_id) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetMarketEligibility/v1/",
            require_api_key=True,
            service_payload={
                "steamid": validate_steam_id(steam_id),
            },
        )

    def cancel_app_listings_for_user(self, app_id, steam_id, *, synchronous: bool) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/CancelAppListingsForUser/v1/",
            require_api_key=True,
            service_payload={
                "appid": validate_app_id(app_id),
                "steamid": validate_steam_id(steam_id),
                "synchronous": bool(synchronous),
            },
        )

    def get_asset_id(self, app_id, listing_id) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetAssetID/v1/",
            require_api_key=True,
            service_payload={
                "appid": validate_app_id(app_id),
                "listingid": validate_uint64(listing_id, "listing_id"),
            },
        )

    def get_popular(
        self,
        language: str,
        *,
        rows: Optional[int] = None,
        start: Optional[int] = None,
        filter_app_id: Optional[int] = None,
        ecurrency: Optional[int] = None,
    ) -> dict:
        payload = {
            "language": ensure_not_blank(language, "language"),
        }
        if rows is not None:
            payload["rows"] = validate_uint32(rows, "rows")
        if start is not None:
            payload["start"] = validate_uint32(start, "start", allow_zero=True)
        if filter_app_id is not None:
            payload["filter_appid"] = validate_app_id(filter_app_id, "filter_app_id")
        if ecurrency is not None:
            payload["ecurrency"] = validate_uint32(ecurrency, "ecurrency")
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetPopular/v1/",
            require_api_key=True,
            service_payload=payload,
        )
