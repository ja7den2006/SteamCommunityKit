from __future__ import annotations

from typing import Optional

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import (
    ensure_not_blank,
    validate_app_id,
    validate_steam_id,
    validate_uint32,
    validate_uint64,
)


class CheatReportingService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/ICheatReportingService"

    def report_player_cheating(
        self,
        steam_id,
        app_id,
        *,
        reporter_steam_id=None,
        app_data=None,
        heuristic: Optional[bool] = None,
        detection: Optional[bool] = None,
        player_report: Optional[bool] = None,
        no_report_id: Optional[bool] = None,
        game_mode: Optional[int] = None,
        suspicion_start_time: Optional[int] = None,
        severity: Optional[int] = None,
    ) -> dict:
        payload = {
            "steamid": validate_steam_id(steam_id),
            "appid": validate_app_id(app_id),
        }
        if reporter_steam_id is not None:
            payload["steamidreporter"] = validate_steam_id(reporter_steam_id, "reporter_steam_id")
        if app_data is not None:
            payload["appdata"] = validate_uint64(app_data, "app_data")
        if heuristic is not None:
            payload["heuristic"] = bool(heuristic)
        if detection is not None:
            payload["detection"] = bool(detection)
        if player_report is not None:
            payload["playerreport"] = bool(player_report)
        if no_report_id is not None:
            payload["noreportid"] = bool(no_report_id)
        if game_mode is not None:
            payload["gamemode"] = validate_uint32(game_mode, "game_mode", allow_zero=True)
        if suspicion_start_time is not None:
            payload["suspicionstarttime"] = validate_uint32(
                suspicion_start_time,
                "suspicion_start_time",
                allow_zero=True,
            )
        if severity is not None:
            payload["severity"] = validate_uint32(severity, "severity", allow_zero=True)
        return self.transport.request(
            "POST",
            f"{self.base_url}/ReportPlayerCheating/v1/",
            require_api_key=True,
            service_payload=payload,
        )

    def request_player_game_ban(
        self,
        steam_id,
        app_id,
        report_id,
        cheat_description: str,
        duration: int,
        delay_ban: bool,
        flags: int,
    ) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/RequestPlayerGameBan/v1/",
            require_api_key=True,
            service_payload={
                "steamid": validate_steam_id(steam_id),
                "appid": validate_app_id(app_id),
                "reportid": validate_uint64(report_id, "report_id"),
                "cheatdescription": ensure_not_blank(cheat_description, "cheat_description"),
                "duration": validate_uint32(duration, "duration", allow_zero=True),
                "delayban": bool(delay_ban),
                "flags": validate_uint32(flags, "flags", allow_zero=True),
            },
        )

    def remove_player_game_ban(self, steam_id, app_id) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/RemovePlayerGameBan/v1/",
            require_api_key=True,
            service_payload={
                "steamid": validate_steam_id(steam_id),
                "appid": validate_app_id(app_id),
            },
        )

    def get_cheating_reports(
        self,
        app_id,
        time_end: int,
        time_begin: int,
        report_id_min,
        *,
        include_reports: bool,
        include_bans: bool,
        steam_id=None,
    ) -> dict:
        params = {
            "appid": validate_app_id(app_id),
            "timeend": validate_uint32(time_end, "time_end", allow_zero=True),
            "timebegin": validate_uint32(time_begin, "time_begin", allow_zero=True),
            "reportidmin": validate_uint64(report_id_min, "report_id_min", allow_zero=True),
            "includereports": int(include_reports),
            "includebans": int(include_bans),
        }
        if steam_id is not None:
            params["steamid"] = validate_steam_id(steam_id)
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetCheatingReports/v1/",
            params=params,
            require_api_key=True,
        )

    def request_vac_status_for_user(self, steam_id, app_id, *, session_id=None) -> dict:
        payload = {
            "steamid": validate_steam_id(steam_id),
            "appid": validate_app_id(app_id),
        }
        if session_id is not None:
            payload["session_id"] = validate_uint64(session_id, "session_id")
        return self.transport.request(
            "POST",
            f"{self.base_url}/RequestVacStatusForUser/v1/",
            require_api_key=True,
            service_payload=payload,
        )

    def start_secure_multiplayer_session(self, steam_id, app_id) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/StartSecureMultiplayerSession/v1/",
            require_api_key=True,
            service_payload={
                "steamid": validate_steam_id(steam_id),
                "appid": validate_app_id(app_id),
            },
        )

    def end_secure_multiplayer_session(self, steam_id, app_id, session_id) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/EndSecureMultiplayerSession/v1/",
            require_api_key=True,
            service_payload={
                "steamid": validate_steam_id(steam_id),
                "appid": validate_app_id(app_id),
                "session_id": validate_uint64(session_id, "session_id"),
            },
        )
