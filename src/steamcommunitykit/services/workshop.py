from __future__ import annotations

from typing import Any, Sequence

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import validate_app_id, validate_uint32


class WorkshopService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/IWorkshopService"

    def set_item_payment_rules(
        self,
        app_id,
        game_item_id,
        *,
        associated_workshop_files: Sequence[Any],
        partner_accounts: Sequence[Any],
        make_workshop_files_subscribable: bool,
        validate_only: bool = False,
    ) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/SetItemPaymentRules/v1/",
            require_api_key=True,
            service_payload={
                "appid": validate_app_id(app_id),
                "gameitemid": validate_uint32(game_item_id, "game_item_id"),
                "associated_workshop_files": list(associated_workshop_files),
                "partner_accounts": list(partner_accounts),
                "validate_only": bool(validate_only),
                "make_workshop_files_subscribable": bool(make_workshop_files_subscribable),
            },
        )

    def get_finalized_contributors(self, app_id, game_item_id) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetFinalizedContributors/v1/",
            params={
                "appid": validate_app_id(app_id),
                "gameitemid": validate_uint32(game_item_id, "game_item_id"),
            },
            require_api_key=True,
        )

    def get_item_daily_revenue(self, app_id, item_id, date_start: int, date_end: int) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetItemDailyRevenue/v1/",
            params={
                "appid": validate_app_id(app_id),
                "item_id": validate_uint32(item_id, "item_id"),
                "date_start": validate_uint32(date_start, "date_start", allow_zero=True),
                "date_end": validate_uint32(date_end, "date_end", allow_zero=True),
            },
            require_api_key=True,
        )

    def populate_item_descriptions(self, app_id, *, languages: Sequence[Any]) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/PopulateItemDescriptions/v1/",
            require_api_key=True,
            service_payload={
                "appid": validate_app_id(app_id),
                "languages": list(languages),
            },
        )
