import pytest

from steamcommunitykit import CommunityCredentials, SteamAuthenticationError, SteamClient
from steamcommunitykit.http import SteamHTTPTransport


class DummyResponse:
    def __init__(self, *, status_code=200, json_data=None, text="", headers=None):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.headers = headers or {}
        self.content = text.encode("utf-8") if text else b"{}"

    def json(self):
        if self._json_data is None:
            raise ValueError("No JSON data configured")
        return self._json_data


class DummySession:
    def __init__(self, response):
        self.headers = {}
        self._response = response

    def request(self, **kwargs):
        return self._response

    def close(self):
        return None


class RecordingSession:
    def __init__(self, response):
        self.headers = {}
        self._response = response
        self.calls = []

    def request(self, **kwargs):
        self.calls.append(kwargs)
        return self._response

    def close(self):
        return None


def test_transport_requires_api_key_for_protected_endpoint() -> None:
    transport = SteamHTTPTransport(session=DummySession(DummyResponse(json_data={"ok": True})))
    with pytest.raises(SteamAuthenticationError):
        transport.request("GET", "https://example.com", require_api_key=True)


def test_transport_unwraps_response_payload() -> None:
    transport = SteamHTTPTransport(
        api_key="test",
        session=DummySession(DummyResponse(json_data={"response": {"players": []}})),
    )
    assert transport.request("GET", "https://example.com", require_api_key=True) == {"players": []}


def test_client_exposes_expected_services() -> None:
    client = SteamClient(api_key="test")
    assert client.users is not None
    assert client.players is not None
    assert client.apps is not None
    client.close()


def test_community_credentials_build_cookie_from_access_token() -> None:
    credentials = CommunityCredentials(
        steam_id="76561197960435530",
        session_id="session123",
        access_token="token123",
    )
    assert credentials.steam_login_secure_value == "76561197960435530%7C%7Ctoken123"


def test_users_service_publisher_endpoint_uses_partner_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"ownsapp": True}))
    client = SteamClient(api_key="test", session=session)

    client.users.check_app_ownership("76561197960435530", 440)

    call = session.calls[0]
    assert call["url"] == "https://partner.steam-api.com/ISteamUser/CheckAppOwnership/v4/"
    assert call["params"]["steamid"] == "76561197960435530"
    assert call["params"]["appid"] == 440
    assert call["params"]["key"] == "test"
    client.close()


def test_apps_service_partner_list_method_uses_partner_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"applist": {}}))
    client = SteamClient(api_key="test", session=session)

    client.apps.get_partner_app_list_for_web_api_key("game,tool")

    call = session.calls[0]
    assert call["url"] == "https://partner.steam-api.com/ISteamApps/GetPartnerAppListForWebAPIKey/v2/"
    assert call["params"]["type_filter"] == "game,tool"
    assert call["params"]["key"] == "test"
    client.close()


def test_news_service_authed_method_uses_partner_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"appnews": {}}))
    client = SteamClient(api_key="test", session=session)

    client.news.get_news_for_app_authed(440, count=1)

    call = session.calls[0]
    assert call["url"] == "https://partner.steam-api.com/ISteamNews/GetNewsForAppAuthed/v2/"
    assert call["params"]["appid"] == 440
    assert call["params"]["count"] == 1
    assert call["params"]["key"] == "test"
    client.close()
