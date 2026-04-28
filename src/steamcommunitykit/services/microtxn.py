from __future__ import annotations

from typing import Optional

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.exceptions import SteamValidationError
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import ensure_not_blank, validate_app_id, validate_steam_id, validate_uint32, validate_uint64


class MicroTxnService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/ISteamMicroTxn"

    def get_user_info(self, app_id, *, steam_id=None, ip_address: Optional[str] = None) -> dict:
        params = {"appid": validate_app_id(app_id)}
        if steam_id is not None:
            params["steamid"] = validate_steam_id(steam_id)
        if ip_address is not None:
            params["ipaddress"] = ensure_not_blank(ip_address, "ip_address")
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetUserInfo/v2/",
            params=params,
            require_api_key=True,
        )

    def get_user_agreement_info(self, steam_id, app_id) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetUserAgreementInfo/v2/",
            params={
                "steamid": validate_steam_id(steam_id),
                "appid": validate_app_id(app_id),
            },
            require_api_key=True,
        )

    def query_txn(self, app_id, *, order_id=None, trans_id=None) -> dict:
        if order_id is None and trans_id is None:
            raise SteamValidationError("query_txn requires either order_id or trans_id.")
        params = {"appid": validate_app_id(app_id)}
        if order_id is not None:
            params["orderid"] = validate_uint64(order_id, "order_id", allow_zero=True)
        if trans_id is not None:
            params["transid"] = validate_uint64(trans_id, "trans_id", allow_zero=True)
        return self.transport.request(
            "GET",
            f"{self.base_url}/QueryTxn/v3/",
            params=params,
            require_api_key=True,
        )

    def get_report(
        self,
        app_id,
        time: str,
        *,
        report_type: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> dict:
        params = {
            "appid": validate_app_id(app_id),
            "time": ensure_not_blank(time, "time"),
        }
        if report_type is not None:
            params["type"] = ensure_not_blank(report_type, "report_type")
        if max_results is not None:
            params["maxresults"] = validate_uint32(max_results, "max_results")
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetReport/v5/",
            params=params,
            require_api_key=True,
        )
