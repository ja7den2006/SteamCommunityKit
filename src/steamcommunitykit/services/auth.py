from __future__ import annotations

import base64
import json
import time
import urllib.parse
from collections.abc import Mapping
from typing import Callable, Optional

import jwt
import requests
import rsa

from steamcommunitykit.constants import COMMUNITY_BASE_URL, QR_IMAGE_BASE_URL, WEB_API_BASE_URL
from steamcommunitykit.exceptions import SteamAuthenticationError
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.models import CommunityCredentials, CredentialLoginResult, QRAuthSession
from steamcommunitykit.utils import ensure_not_blank, parse_cookie_string, validate_steam_id


class AuthenticationService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/IAuthenticationService"

    def get_password_rsa_public_key(self, account_name: str) -> dict:
        return self.transport.request(
            "GET",
            f"{self.base_url}/GetPasswordRSAPublicKey/v1/",
            params={"account_name": ensure_not_blank(account_name, "account_name")},
        )

    def begin_auth_session_via_credentials(
        self, account_name: str, password: str, *, persistence: bool = True
    ) -> dict:
        rsa_data = self.get_password_rsa_public_key(account_name)
        rsa_key = rsa.PublicKey(
            int(rsa_data["publickey_mod"], 16),
            int(rsa_data["publickey_exp"], 16),
        )
        encrypted_password = base64.b64encode(
            rsa.encrypt(ensure_not_blank(password, "password").encode("utf-8"), rsa_key)
        ).decode("ascii")
        payload = {
            "persistence": int(persistence),
            "encrypted_password": encrypted_password,
            "account_name": ensure_not_blank(account_name, "account_name"),
            "encryption_timestamp": rsa_data["timestamp"],
        }
        return self.transport.request(
            "POST",
            f"{self.base_url}/BeginAuthSessionViaCredentials/v1/",
            data=payload,
        )

    def update_auth_session_with_steam_guard_code(
        self,
        client_id: int,
        steam_id,
        code_type: int,
        code: str,
    ) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/UpdateAuthSessionWithSteamGuardCode/v1/",
            data={
                "client_id": int(client_id),
                "steamid": validate_steam_id(steam_id),
                "code_type": int(code_type),
                "code": ensure_not_blank(code, "code"),
            },
        )

    def poll_auth_session_status(self, client_id: int, request_id: str) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/PollAuthSessionStatus/v1/",
            data={"client_id": int(client_id), "request_id": request_id},
            headers={
                "X-Requested-With": "com.valvesoftware.android.steam.community",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-User": "?1",
                "Sec-Fetch-Dest": "document",
                "Accept-Encoding": "gzip, deflate",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

    def begin_auth_session_via_qr(
        self, device_friendly_name: str = "steamlib QR login"
    ) -> QRAuthSession:
        response = self.transport.request(
            "POST",
            f"{self.base_url}/BeginAuthSessionViaQR/v1/",
            json_body={
                "device_details": {
                    "device_friendly_name": device_friendly_name,
                    "platform_type": 2,
                    "os_type": 20,
                }
            },
        )
        return QRAuthSession(
            client_id=int(response["client_id"]),
            request_id=str(response["request_id"]),
            interval=float(response.get("interval", 5.0)),
            challenge_url=str(response["challenge_url"]),
            version=int(response.get("version", 1)),
            allowed_confirmations=response.get("allowed_confirmations", []),
        )

    def build_qr_image_url(self, challenge_url: str) -> str:
        encoded = urllib.parse.quote(ensure_not_blank(challenge_url, "challenge_url"), safe="")
        return "{0}{1}".format(QR_IMAGE_BASE_URL, encoded)

    def wait_for_qr_approval(
        self,
        session: QRAuthSession,
        *,
        timeout: float = 300.0,
    ) -> dict:
        started = time.monotonic()
        while time.monotonic() - started <= timeout:
            response = self.poll_auth_session_status(session.client_id, session.request_id)
            if response.get("access_token") and response.get("refresh_token"):
                return response
            time.sleep(session.interval)
        raise TimeoutError("Timed out waiting for Steam mobile confirmation.")

    def finalize_login(self, refresh_token: str, session_id: str) -> dict:
        return self.transport.request(
            "POST",
            "https://login.steampowered.com/jwt/finalizelogin",
            data={
                "nonce": ensure_not_blank(refresh_token, "refresh_token"),
                "sessionid": ensure_not_blank(session_id, "session_id"),
                "redir": "https://store.steampowered.com/login/?redir=&redir_ssl=1",
            },
        )

    def set_community_login_cookie(
        self, *, refresh_token: str, session_id: str, steam_id
    ):
        finalized = self.finalize_login(refresh_token, session_id)
        transfer_info = finalized["transfer_info"]
        community_info = next(
            item for item in transfer_info if "steamcommunity.com/login/settoken" in item["url"]
        )
        return self.transport.request(
            "POST",
            f"{COMMUNITY_BASE_URL}/login/settoken",
            data={
                "nonce": community_info["params"]["nonce"],
                "auth": community_info["params"]["auth"],
                "steamID": validate_steam_id(steam_id),
            },
            expected="raw",
        )

    def create_session_id(self) -> str:
        response = self.transport.session.post(
            COMMUNITY_BASE_URL,
            timeout=self.transport.timeout,
        )
        session_id = response.cookies.get("sessionid")
        if not session_id:
            raise RuntimeError("Steam did not return a sessionid cookie.")
        return session_id

    def login_with_credentials(
        self,
        account_name: str,
        password: str,
        *,
        persistence: bool = True,
        steam_guard_code: Optional[str] = None,
        steam_guard_code_provider: Optional[Callable[[dict], str]] = None,
        prompt_for_steam_guard: bool = False,
        poll_interval: float = 1.5,
        poll_timeout: float = 60.0,
    ) -> CredentialLoginResult:
        started = self.begin_auth_session_via_credentials(
            account_name,
            password,
            persistence=persistence,
        )
        self._validate_begin_login_response(started)
        client_id = int(started["client_id"])
        request_id = str(started["request_id"])
        steam_id = str(started["steamid"])
        polled = self._poll_for_tokens(
            client_id,
            request_id,
            timeout=0.0,
            interval=poll_interval,
        )
        if not self._has_auth_tokens(polled):
            confirmation = self._select_steam_guard_confirmation(started)
            if confirmation is not None:
                code = steam_guard_code
                if code is None and steam_guard_code_provider is not None:
                    code = steam_guard_code_provider(started)
                if code is None and prompt_for_steam_guard:
                    code = self.prompt_for_steam_guard_code(confirmation)
                if code is None:
                    raise SteamAuthenticationError(
                        self._format_steam_guard_required_message(confirmation),
                        status_code=401,
                        payload=started,
                    )
                self.update_auth_session_with_steam_guard_code(
                    client_id,
                    steam_id,
                    int(confirmation["confirmation_type"]),
                    code,
                )
                polled = self._poll_for_tokens(
                    client_id,
                    request_id,
                    timeout=poll_timeout,
                    interval=poll_interval,
                )
        if not self._has_auth_tokens(polled):
            raise SteamAuthenticationError(
                self._extract_login_failure_message(polled),
                status_code=401,
                payload=polled,
            )
        return CredentialLoginResult(
            steam_id=steam_id,
            account_name=str(polled.get("account_name") or ensure_not_blank(account_name, "account_name")),
            client_id=client_id,
            request_id=request_id,
            access_token=str(polled["access_token"]),
            refresh_token=str(polled["refresh_token"]),
            had_remote_interaction=bool(polled.get("had_remote_interaction", False)),
        )

    @staticmethod
    def _has_auth_tokens(payload: dict) -> bool:
        return bool(payload.get("access_token") and payload.get("refresh_token"))

    @staticmethod
    def _validate_begin_login_response(payload: dict) -> None:
        required_fields = ("client_id", "request_id", "steamid")
        missing_fields = [field for field in required_fields if not payload.get(field)]
        if not missing_fields:
            return
        raise SteamAuthenticationError(
            AuthenticationService._extract_begin_login_failure_message(payload),
            status_code=401,
            payload=payload,
        )

    def _poll_for_tokens(
        self,
        client_id: int,
        request_id: str,
        *,
        timeout: float,
        interval: float,
    ) -> dict:
        deadline = time.monotonic() + max(timeout, 0.0)
        last_response = self.poll_auth_session_status(client_id, request_id)
        if self._has_auth_tokens(last_response) or time.monotonic() >= deadline:
            return last_response
        while time.monotonic() < deadline:
            time.sleep(max(interval, 0.1))
            last_response = self.poll_auth_session_status(client_id, request_id)
            if self._has_auth_tokens(last_response):
                return last_response
        return last_response

    @staticmethod
    def _select_steam_guard_confirmation(payload: dict) -> Optional[dict]:
        confirmations = payload.get("allowed_confirmations") or []
        for preferred_type in (3, 2):
            for confirmation in confirmations:
                if int(confirmation.get("confirmation_type", 0)) == preferred_type:
                    return confirmation
        for confirmation in confirmations:
            if confirmation.get("confirmation_type"):
                return confirmation
        return None

    @staticmethod
    def _format_steam_guard_required_message(confirmation: dict) -> str:
        confirmation_type = int(confirmation.get("confirmation_type", 0))
        associated_message = (confirmation.get("associated_message") or "").strip()
        if confirmation_type == 3:
            return "A Steam Guard mobile authenticator code is required for this login."
        if confirmation_type == 2 and associated_message:
            return "A Steam Guard email code is required for this login ({0}).".format(associated_message)
        if confirmation_type == 2:
            return "A Steam Guard email code is required for this login."
        return "A Steam Guard confirmation is required for this login."

    @staticmethod
    def prompt_for_steam_guard_code(confirmation: dict) -> str:
        confirmation_type = int(confirmation.get("confirmation_type", 0))
        associated_message = (confirmation.get("associated_message") or "").strip()
        if confirmation_type == 3:
            prompt = "Steam mobile authenticator code: "
        elif confirmation_type == 2 and associated_message:
            prompt = "Steam Guard email code ({0}): ".format(associated_message)
        elif confirmation_type == 2:
            prompt = "Steam Guard email code: "
        else:
            prompt = "Steam Guard code: "
        return ensure_not_blank(input(prompt), "steam_guard_code")

    @staticmethod
    def _extract_login_failure_message(payload: dict) -> str:
        for key in ("message", "error", "agreement_session_url", "extended_error_message"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        if payload.get("had_remote_interaction"):
            return "Steam login was not completed after remote interaction."
        return "Steam login did not return access tokens."

    @staticmethod
    def _extract_begin_login_failure_message(payload: dict) -> str:
        for key in ("message", "error", "extended_error_message"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return "Your credentials are incorrect or the Steam account is unable to login."

    def community_credentials_from_login(self, login_result: CredentialLoginResult) -> CommunityCredentials:
        session_id = self.create_session_id()
        response = self.set_community_login_cookie(
            refresh_token=login_result.refresh_token,
            session_id=session_id,
            steam_id=login_result.steam_id,
        )
        steam_login_secure = response.cookies.get("steamLoginSecure")
        if not steam_login_secure:
            raise RuntimeError("Steam did not return a steamLoginSecure cookie.")
        return CommunityCredentials(
            steam_id=login_result.steam_id,
            session_id=session_id,
            access_token=login_result.access_token,
            refresh_token=login_result.refresh_token,
            steam_login_secure=steam_login_secure,
        )

    def community_credentials_from_refresh_token(
        self,
        refresh_token: str,
        *,
        session_id: str = None,
    ) -> CommunityCredentials:
        normalized_refresh_token = ensure_not_blank(refresh_token, "refresh_token")
        claims = self.decode_jwt(normalized_refresh_token)
        steam_id = validate_steam_id(claims.get("sub"), "steam_id")
        resolved_session_id = ensure_not_blank(session_id, "session_id") if session_id else self.create_session_id()
        response = self.set_community_login_cookie(
            refresh_token=normalized_refresh_token,
            session_id=resolved_session_id,
            steam_id=steam_id,
        )
        steam_login_secure = response.cookies.get("steamLoginSecure")
        if not steam_login_secure:
            raise RuntimeError("Steam did not return a steamLoginSecure cookie.")
        return CommunityCredentials(
            steam_id=steam_id,
            session_id=resolved_session_id,
            refresh_token=normalized_refresh_token,
            steam_login_secure=steam_login_secure,
        )

    def community_credentials_from_cookie_string(self, cookie_string: str) -> CommunityCredentials:
        cookies = parse_cookie_string(cookie_string)
        return self.community_credentials_from_cookie_mapping(cookies)

    def community_credentials_from_cookie_mapping(
        self,
        cookies: Mapping[str, str],
    ) -> CommunityCredentials:
        if not isinstance(cookies, Mapping):
            raise SteamAuthenticationError("community cookies must be a mapping.", status_code=400)
        session_id = cookies.get("sessionid")
        steam_login_secure = cookies.get("steamLoginSecure")
        if not session_id:
            raise RuntimeError("community cookies must contain a sessionid cookie.")
        if not steam_login_secure:
            raise RuntimeError("community cookies must contain a steamLoginSecure cookie.")
        return CommunityCredentials.from_cookie_pair(
            session_id=session_id,
            steam_login_secure=steam_login_secure,
        )

    def community_credentials_from_bundle(self, bundle: dict) -> CommunityCredentials:
        if not isinstance(bundle, dict):
            raise SteamAuthenticationError("community bundle must be a dictionary.", status_code=400)

        session_id = bundle.get("session_id") or bundle.get("sessionid")
        steam_login_secure = bundle.get("steam_login_secure") or bundle.get("steamLoginSecure")
        refresh_token = bundle.get("refresh_token")
        access_token = bundle.get("access_token")
        steam_id = bundle.get("steam_id") or bundle.get("steamid")

        if steam_login_secure and session_id:
            credentials = CommunityCredentials.from_cookie_pair(
                session_id=str(session_id),
                steam_login_secure=str(steam_login_secure),
            )
            if steam_id is not None and str(steam_id) != credentials.steam_id:
                raise SteamAuthenticationError(
                    "community bundle steam_id does not match steamLoginSecure.",
                    status_code=400,
                )
            credentials.refresh_token = str(refresh_token) if refresh_token else None
            if access_token:
                credentials.access_token = str(access_token)
            return credentials

        if refresh_token:
            return self.community_credentials_from_refresh_token(
                str(refresh_token),
                session_id=str(session_id) if session_id else None,
            )

        if session_id and steam_id and access_token:
            return CommunityCredentials(
                steam_id=validate_steam_id(steam_id, "steam_id"),
                session_id=ensure_not_blank(str(session_id), "session_id"),
                access_token=ensure_not_blank(str(access_token), "access_token"),
                refresh_token=str(refresh_token) if refresh_token else None,
            )

        raise SteamAuthenticationError(
            "community bundle must include either session_id + steamLoginSecure, refresh_token, or session_id + steam_id + access_token.",
            status_code=400,
        )

    def community_credentials_from_bundle_json(self, bundle_json: str) -> CommunityCredentials:
        try:
            bundle = json.loads(ensure_not_blank(bundle_json, "bundle_json"))
        except json.JSONDecodeError as exc:
            raise SteamAuthenticationError(
                "community bundle JSON is not valid JSON.",
                status_code=400,
            ) from exc
        return self.community_credentials_from_bundle(bundle)

    @staticmethod
    def export_cookie_string(credentials: CommunityCredentials) -> str:
        cookies = AuthenticationService.export_cookie_mapping(credentials)
        return "sessionid={0}; steamLoginSecure={1}".format(
            cookies["sessionid"],
            cookies["steamLoginSecure"],
        )

    @staticmethod
    def export_cookie_mapping(credentials: CommunityCredentials) -> dict:
        return {
            "sessionid": credentials.session_id,
            "steamLoginSecure": credentials.steam_login_secure_value,
        }

    @staticmethod
    def export_credentials_bundle(credentials: CommunityCredentials) -> dict:
        bundle = {
            "steam_id": credentials.steam_id,
            "session_id": credentials.session_id,
            "has_access_token": bool(credentials.access_token),
            "has_refresh_token": bool(credentials.refresh_token),
            "has_steam_login_secure": bool(credentials.steam_login_secure or credentials.access_token),
        }
        if credentials.access_token:
            bundle["access_token"] = credentials.access_token
        if credentials.refresh_token:
            bundle["refresh_token"] = credentials.refresh_token
        if credentials.steam_login_secure:
            bundle["steam_login_secure"] = credentials.steam_login_secure
        return bundle

    @staticmethod
    def export_credentials_bundle_json(
        credentials: CommunityCredentials,
        *,
        indent: Optional[int] = None,
    ) -> str:
        return json.dumps(
            AuthenticationService.export_credentials_bundle(credentials),
            indent=indent,
            sort_keys=True,
        )

    @staticmethod
    def apply_community_credentials_to_session(
        session: requests.Session,
        credentials: CommunityCredentials,
    ) -> requests.Session:
        session.cookies.set(
            "sessionid",
            credentials.session_id,
            domain=".steamcommunity.com",
            path="/",
        )
        session.cookies.set(
            "steamLoginSecure",
            credentials.steam_login_secure_value,
            domain=".steamcommunity.com",
            path="/",
        )
        return session

    @staticmethod
    def decode_jwt(token: str) -> dict:
        return jwt.decode(token, options={"verify_signature": False})
