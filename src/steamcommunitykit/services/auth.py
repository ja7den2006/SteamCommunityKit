from __future__ import annotations

import base64
import time

import jwt
import rsa

from steamcommunitykit.constants import COMMUNITY_BASE_URL, WEB_API_BASE_URL
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.models import CommunityCredentials, CredentialLoginResult, QRAuthSession
from steamcommunitykit.utils import ensure_not_blank, validate_steam_id


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
    ) -> CredentialLoginResult:
        started = self.begin_auth_session_via_credentials(
            account_name,
            password,
            persistence=persistence,
        )
        polled = self.poll_auth_session_status(int(started["client_id"]), started["request_id"])
        return CredentialLoginResult(
            steam_id=str(started["steamid"]),
            account_name=str(polled.get("account_name") or ensure_not_blank(account_name, "account_name")),
            client_id=int(started["client_id"]),
            request_id=str(started["request_id"]),
            access_token=str(polled["access_token"]),
            refresh_token=str(polled["refresh_token"]),
            had_remote_interaction=bool(polled.get("had_remote_interaction", False)),
        )

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
            steam_login_secure=steam_login_secure,
        )

    @staticmethod
    def decode_jwt(token: str) -> dict:
        return jwt.decode(token, options={"verify_signature": False})
