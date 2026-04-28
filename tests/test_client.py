import pytest

from steamcommunitykit import (
    CommunityCredentials,
    CredentialLoginResult,
    SteamAuthenticationError,
    SteamClient,
    SteamNotFoundError,
    SteamRateLimitError,
    SteamResponseError,
    SteamValidationError,
    account_id_to_steam_id,
    build_trade_offer_url,
    parse_trade_offer_url,
    steam_id_to_account_id,
)
from steamcommunitykit.http import SteamHTTPTransport


class DummyResponse:
    def __init__(self, *, status_code=200, json_data=None, text="", headers=None):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.headers = headers or {}
        self.content = text.encode("utf-8") if text else b"{}"
        self.cookies = {}

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

    def post(self, url, timeout=None):
        self.calls.append({"method": "POST", "url": url, "timeout": timeout})
        return self._response


class SequenceSession:
    def __init__(self, responses):
        self.headers = {}
        self._responses = list(responses)
        self.calls = []

    def request(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)

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


def test_transport_retries_rate_limited_response_until_success() -> None:
    session = SequenceSession(
        [
            DummyResponse(status_code=429, json_data={"error": "slow down"}, headers={"Retry-After": "0"}),
            DummyResponse(json_data={"response": {"ok": True}}, text="{}"),
        ]
    )
    transport = SteamHTTPTransport(api_key="test", session=session, backoff_factor=0, max_retries=1)

    result = transport.request("GET", "https://example.com", require_api_key=True)

    assert result == {"ok": True}
    assert len(session.calls) == 2


def test_transport_raises_rate_limit_error_after_exhausting_retries() -> None:
    session = SequenceSession(
        [
            DummyResponse(status_code=429, json_data={"error": "slow down"}, headers={"Retry-After": "0"}),
            DummyResponse(status_code=429, json_data={"error": "slow down"}, headers={"Retry-After": "0"}),
        ]
    )
    transport = SteamHTTPTransport(api_key="test", session=session, backoff_factor=0, max_retries=1)

    with pytest.raises(SteamRateLimitError):
        transport.request("GET", "https://example.com", require_api_key=True)


def test_transport_maps_family_view_html_to_clear_auth_error() -> None:
    html = "<html><head><title>Family View</title></head><body>blocked</body></html>"
    transport = SteamHTTPTransport(session=DummySession(DummyResponse(status_code=403, text=html)))

    with pytest.raises(SteamAuthenticationError, match="Family View is blocking this action"):
        transport.request("GET", "https://example.com")


def test_client_exposes_expected_services() -> None:
    client = SteamClient(api_key="test")
    assert client.users is not None
    assert client.players is not None
    assert client.apps is not None
    assert client.news is not None
    assert client.user_stats is not None
    assert client.auth is not None
    assert client.econ is not None
    assert client.community is not None
    assert client.groups is not None
    assert client.inventory is not None
    assert client.market is not None
    assert client.store is not None
    assert client.published_files is not None
    assert client.remote_storage is not None
    assert client.webapi_util is not None
    assert not hasattr(client, "community_api")
    assert not hasattr(client, "published_item_search")
    assert not hasattr(client, "published_item_voting")
    assert not hasattr(client, "broadcast")
    assert not hasattr(client, "cheat_reporting")
    assert not hasattr(client, "cloud")
    assert not hasattr(client, "econ_market")
    assert not hasattr(client, "game_notifications")
    assert not hasattr(client, "leaderboards")
    assert not hasattr(client, "microtxn")
    assert not hasattr(client, "user_auth")
    assert not hasattr(client, "workshop")
    client.close()


def test_client_does_not_require_api_key_at_construction() -> None:
    client = SteamClient()

    assert client.api_key is None
    assert client.community is not None
    assert client.groups is not None

    client.close()


def test_client_can_get_community_profile_bundle() -> None:
    client = SteamClient()
    expected = {"account_info": {"steamid": "1"}, "profile_edit_state": {"strPersonaName": "x"}, "privacy": {}}

    original_method = client.community.get_profile_bundle
    client.community.get_profile_bundle = lambda steam_id=None: expected

    result = client.get_community_profile_bundle()

    client.community.get_profile_bundle = original_method

    assert result == expected
    client.close()


def test_community_credentials_build_cookie_from_access_token() -> None:
    credentials = CommunityCredentials(
        steam_id="76561197960435530",
        session_id="session123",
        access_token="token123",
    )
    assert credentials.steam_login_secure_value == "76561197960435530%7C%7Ctoken123"


def test_community_credentials_can_be_created_from_cookie_pair() -> None:
    credentials = CommunityCredentials.from_cookie_pair(
        session_id="session123",
        steam_login_secure="76561197960435530%7C%7Ctoken123",
    )

    assert credentials.steam_id == "76561197960435530"
    assert credentials.session_id == "session123"
    assert credentials.access_token == "token123"
    assert credentials.steam_login_secure == "76561197960435530%7C%7Ctoken123"


def test_steam_id_account_id_conversion_helpers_round_trip() -> None:
    steam_id = "76561199149579604"
    account_id = steam_id_to_account_id(steam_id)

    assert account_id == 1189313876
    assert account_id_to_steam_id(account_id) == steam_id


def test_trade_offer_url_helpers_parse_and_build() -> None:
    trade_url = build_trade_offer_url(
        partner_account_id=1189313876,
        token="vrJtfrV_",
    )
    parsed = parse_trade_offer_url(trade_url)

    assert trade_url == "https://steamcommunity.com/tradeoffer/new/?partner=1189313876&token=vrJtfrV_"
    assert parsed["partner_id"] == "1189313876"
    assert parsed["partner_account_id"] == 1189313876
    assert parsed["partner_steam_id"] == "76561199149579604"
    assert parsed["token"] == "vrJtfrV_"


def test_users_service_uses_public_player_summaries_endpoint() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"players": []}}))
    client = SteamClient(api_key="test", session=session)

    client.users.get_player_summaries("76561197960435530")

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
    assert call["params"]["steamids"] == "76561197960435530"
    assert call["params"]["key"] == "test"
    client.close()


def test_users_resolve_steam_id_accepts_profile_url() -> None:
    client = SteamClient(api_key="test")

    resolved = client.users.resolve_steam_id("https://steamcommunity.com/profiles/76561197960435530/")

    assert resolved == "76561197960435530"
    client.close()


def test_users_resolve_steam_id_accepts_vanity_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"steamid": "76561197968052866", "success": 1}}))
    client = SteamClient(api_key="test", session=session)

    resolved = client.users.resolve_steam_id("https://steamcommunity.com/id/gaben/")

    assert resolved == "76561197968052866"
    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/"
    assert call["params"]["vanityurl"] == "gaben"
    client.close()


def test_users_resolve_steam_id_accepts_plain_vanity_name() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"steamid": "76561197968052866", "success": 1}}))
    client = SteamClient(api_key="test", session=session)

    resolved = client.users.resolve_steam_id("gaben")

    assert resolved == "76561197968052866"
    client.close()


def test_users_resolve_steam_id_falls_back_to_community_xml_without_api_key() -> None:
    xml = """
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <profile>
      <steamID64>76561197968052866</steamID64>
      <steamID><![CDATA[Gaben]]></steamID>
      <customURL><![CDATA[gaben]]></customURL>
      <profileURL><![CDATA[https://steamcommunity.com/id/gaben/]]></profileURL>
    </profile>
    """
    session = RecordingSession(DummyResponse(text=xml))
    client = SteamClient(session=session)

    resolved = client.users.resolve_steam_id("gaben")

    assert resolved == "76561197968052866"
    call = session.calls[0]
    assert call["url"] == "https://steamcommunity.com/id/gaben/"
    assert call["params"]["xml"] == "1"
    client.close()


def test_users_resolve_community_profile_xml_returns_profile_fields() -> None:
    xml = """
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <profile>
      <steamID64>76561197968052866</steamID64>
      <steamID><![CDATA[Gaben]]></steamID>
      <customURL><![CDATA[gaben]]></customURL>
      <profileURL><![CDATA[https://steamcommunity.com/id/gaben/]]></profileURL>
      <avatarIcon><![CDATA[icon.jpg]]></avatarIcon>
      <avatarMedium><![CDATA[medium.jpg]]></avatarMedium>
      <avatarFull><![CDATA[full.jpg]]></avatarFull>
      <privacyState>public</privacyState>
      <visibilityState>3</visibilityState>
      <stateMessage><![CDATA[Offline]]></stateMessage>
      <onlineState>offline</onlineState>
    </profile>
    """
    session = RecordingSession(DummyResponse(text=xml))
    client = SteamClient(session=session)

    profile = client.users.resolve_community_profile_xml("https://steamcommunity.com/id/gaben/")

    assert profile["steamid"] == "76561197968052866"
    assert profile["personaname"] == "Gaben"
    assert profile["custom_url"] == "gaben"
    assert profile["profile_url"] == "https://steamcommunity.com/id/gaben/"
    assert profile["privacy_state"] == "public"
    client.close()


def test_users_resolve_steam_id_raises_not_found_for_missing_vanity() -> None:
    session = RecordingSession(
        DummyResponse(json_data={"response": {"success": 42, "message": "No match"}})
    )
    client = SteamClient(api_key="test", session=session)

    with pytest.raises(SteamNotFoundError):
        client.users.resolve_steam_id("definitely-not-a-real-vanity-name")

    client.close()


def test_users_get_player_summary_resolves_identifier_before_fetch() -> None:
    session = SequenceSession(
        [
            DummyResponse(json_data={"response": {"steamid": "76561197968052866", "success": 1}}),
            DummyResponse(json_data={"response": {"players": [{"steamid": "76561197968052866", "personaname": "gaben"}]}}),
        ]
    )
    client = SteamClient(api_key="test", session=session)

    summary = client.users.get_player_summary("https://steamcommunity.com/id/gaben/")

    assert summary["steamid"] == "76561197968052866"
    assert summary["personaname"] == "gaben"
    assert len(session.calls) == 2
    client.close()


def test_users_get_player_summary_falls_back_to_community_xml_without_api_key() -> None:
    xml = """
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <profile>
      <steamID64>76561197968052866</steamID64>
      <steamID><![CDATA[Gaben]]></steamID>
      <customURL><![CDATA[gaben]]></customURL>
      <profileURL><![CDATA[https://steamcommunity.com/id/gaben/]]></profileURL>
      <avatarIcon><![CDATA[icon.jpg]]></avatarIcon>
      <avatarMedium><![CDATA[medium.jpg]]></avatarMedium>
      <avatarFull><![CDATA[full.jpg]]></avatarFull>
      <privacyState>public</privacyState>
      <visibilityState>3</visibilityState>
      <stateMessage><![CDATA[Offline]]></stateMessage>
      <onlineState>offline</onlineState>
    </profile>
    """
    session = RecordingSession(DummyResponse(text=xml))
    client = SteamClient(session=session)

    summary = client.get_player_summary("gaben")

    assert summary["steamid"] == "76561197968052866"
    assert summary["personaname"] == "Gaben"
    assert summary["profileurl"] == "https://steamcommunity.com/id/gaben/"
    assert summary["avatar"] == "icon.jpg"
    assert summary["communityvisibilitystate"] == 3
    assert summary["personastate"] == 0
    client.close()


def test_users_get_player_summaries_fall_back_to_community_xml_without_api_key() -> None:
    xml_one = """
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <profile><steamID64>76561197960435530</steamID64><steamID><![CDATA[Robin]]></steamID><profileURL><![CDATA[https://steamcommunity.com/profiles/76561197960435530/]]></profileURL></profile>
    """
    xml_two = """
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <profile><steamID64>76561197960287930</steamID64><steamID><![CDATA[John]]></steamID><profileURL><![CDATA[https://steamcommunity.com/profiles/76561197960287930/]]></profileURL></profile>
    """
    session = SequenceSession([DummyResponse(text=xml_one), DummyResponse(text=xml_two)])
    client = SteamClient(session=session)

    summaries = client.users.get_player_summaries(["76561197960435530", "76561197960287930"])

    assert len(summaries) == 2
    assert summaries[0]["personaname"] == "Robin"
    assert summaries[1]["personaname"] == "John"
    client.close()


def test_apps_service_uses_public_servers_at_address_endpoint() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"servers": []}}))
    client = SteamClient(api_key="test", session=session)

    client.apps.get_servers_at_address("208.64.200.0")

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamApps/GetServersAtAddress/v1/"
    assert call["params"]["addr"] == "208.64.200.0"
    assert "key" not in call["params"]
    client.close()


def test_news_service_authed_method_uses_public_api_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"appnews": {}}))
    client = SteamClient(api_key="test", session=session)

    client.news.get_news_for_app_authed(440, count=1)

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamNews/GetNewsForAppAuthed/v2/"
    assert call["params"]["appid"] == 440
    assert call["params"]["count"] == 1
    assert call["params"]["key"] == "test"
    client.close()


def test_store_service_uses_public_api_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"items": []}}))
    client = SteamClient(api_key="test", session=session)

    client.store.get_app_list(if_modified_since=1234567890, include_games=True)

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/IStoreService/GetAppList/v1/"
    assert call["params"]["if_modified_since"] == 1234567890
    assert call["params"]["include_games"] == 1
    assert call["params"]["key"] == "test"
    client.close()


def test_published_files_query_uses_public_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"total": 0}}))
    client = SteamClient(api_key="test", session=session)

    client.published_files.query_files(
        query_type=0,
        cursor="*",
        app_id=570,
        total_only=True,
        required_kv_tags=[{"key": "mode", "value": "ranked"}],
        return_metadata=True,
        return_playtime_stats=7,
    )

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/IPublishedFileService/QueryFiles/v1/"
    assert call["params"]["appid"] == 570
    assert call["params"]["totalonly"] == 1
    assert call["params"]["return_metadata"] == 1
    assert call["params"]["return_playtime_stats"] == 7
    assert '"required_kv_tags":[{"key":"mode","value":"ranked"}]' in call["params"]["input_json"]
    assert call["params"]["key"] == "test"
    assert not hasattr(client.published_files, "set_developer_metadata")
    client.close()


def test_remote_storage_public_details_use_public_base_url() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"publishedfiledetails": []}}))
    client = SteamClient(api_key="test", session=session)

    client.remote_storage.get_published_file_details(["123456", "789012"])

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
    assert call["data"]["itemcount"] == 2
    assert call["data"]["publishedfileids[0]"] == "123456"
    assert call["data"]["publishedfileids[1]"] == "789012"
    client.close()


def test_remote_storage_get_ugc_file_details_requires_app_id() -> None:
    session = RecordingSession(DummyResponse(json_data={"data": {"filename": "example"}}))
    client = SteamClient(api_key="test", session=session)

    client.remote_storage.get_ugc_file_details("123456", 570, "76561197960435530")

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamRemoteStorage/GetUGCFileDetails/v1/"
    assert call["params"]["ugcid"] == "123456"
    assert call["params"]["appid"] == 570
    assert call["params"]["steamid"] == "76561197960435530"
    assert call["params"]["key"] == "test"
    client.close()


def test_econ_get_trade_history_uses_user_key_endpoint() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"trades": []}}))
    client = SteamClient(api_key="test", session=session)

    client.econ.get_trade_history(
        max_trades=50,
        start_after_time=0,
        start_after_trade_id="1234567890",
        navigating_back=False,
        get_descriptions=True,
        language="en",
        include_failed=False,
        include_total=True,
    )

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/IEconService/GetTradeHistory/v1/"
    assert call["params"]["max_trades"] == 50
    assert call["params"]["start_after_time"] == 0
    assert call["params"]["start_after_tradeid"] == "1234567890"
    assert call["params"]["navigating_back"] == 0
    assert call["params"]["get_descriptions"] == 1
    assert call["params"]["language"] == "en"
    assert call["params"]["include_failed"] == 0
    assert call["params"]["include_total"] == 1
    assert call["params"]["key"] == "test"
    client.close()


def test_econ_get_trade_offers_uses_user_key_endpoint() -> None:
    session = RecordingSession(DummyResponse(json_data={"response": {"trade_offers_sent": []}}))
    client = SteamClient(api_key="test", session=session)

    client.econ.get_trade_offers(
        get_sent_offers=True,
        get_received_offers=False,
        get_descriptions=True,
        language="en",
        active_only=True,
        historical_only=False,
        time_historical_cutoff=0,
    )

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/IEconService/GetTradeOffers/v1/"
    assert call["params"]["get_sent_offers"] == 1
    assert call["params"]["get_received_offers"] == 0
    assert call["params"]["get_descriptions"] == 1
    assert call["params"]["language"] == "en"
    assert call["params"]["active_only"] == 1
    assert call["params"]["historical_only"] == 0
    assert call["params"]["time_historical_cutoff"] == 0
    assert call["params"]["key"] == "test"
    assert not hasattr(client.econ, "flush_inventory_cache")
    client.close()


def test_webapi_util_get_supported_api_list_can_use_public_mode() -> None:
    session = RecordingSession(DummyResponse(json_data={"apilist": {"interfaces": []}}))
    client = SteamClient(api_key="test", session=session)

    client.webapi_util.get_supported_api_list()

    call = session.calls[0]
    assert call["url"] == "https://api.steampowered.com/ISteamWebAPIUtil/GetSupportedAPIList/v1/"
    assert call["params"]["format"] == "json"
    assert "key" not in call["params"]
    client.close()


def test_auth_build_qr_image_url_encodes_challenge_url() -> None:
    client = SteamClient(api_key="test")

    result = client.auth.build_qr_image_url("https://example.com/path?a=1&b=two")

    assert result.startswith("https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=")
    assert "https%3A%2F%2Fexample.com%2Fpath%3Fa%3D1%26b%3Dtwo" in result
    client.close()


def test_auth_community_credentials_from_login_uses_cookie_response() -> None:
    response = DummyResponse(json_data={"response": {"ok": True}})
    response.cookies = {"sessionid": "session123", "steamLoginSecure": "securecookie123"}
    session = RecordingSession(response)
    client = SteamClient(api_key="test", session=session)

    login_result = CredentialLoginResult(
        steam_id="76561197960435530",
        account_name="tester",
        client_id=1,
        request_id="req",
        access_token="access123",
        refresh_token="refresh123",
    )

    original_set_cookie = client.auth.set_community_login_cookie

    def fake_set_cookie(**kwargs):
        return response

    client.auth.set_community_login_cookie = fake_set_cookie
    credentials = client.auth.community_credentials_from_login(login_result)
    client.auth.set_community_login_cookie = original_set_cookie

    assert credentials.session_id == "session123"
    assert credentials.steam_login_secure == "securecookie123"
    assert credentials.access_token == "access123"
    client.close()


def test_client_login_to_community_sets_credentials() -> None:
    client = SteamClient(api_key="test")

    login_result = CredentialLoginResult(
        steam_id="76561197960435530",
        account_name="tester",
        client_id=1,
        request_id="req",
        access_token="access123",
        refresh_token="refresh123",
    )
    expected_credentials = CommunityCredentials(
        steam_id="76561197960435530",
        session_id="session123",
        steam_login_secure="securecookie123",
        access_token="access123",
    )

    original_login = client.auth.login_with_credentials
    original_build = client.auth.community_credentials_from_login

    client.auth.login_with_credentials = lambda *args, **kwargs: login_result
    client.auth.community_credentials_from_login = lambda result: expected_credentials

    returned = client.login_to_community("tester", "secret")

    client.auth.login_with_credentials = original_login
    client.auth.community_credentials_from_login = original_build

    assert returned is login_result
    assert client._transport.community_credentials == expected_credentials
    client.close()


def test_client_login_to_community_forwards_steam_guard_options() -> None:
    client = SteamClient(api_key="test")

    captured = {}
    login_result = CredentialLoginResult(
        steam_id="76561197960435530",
        account_name="tester",
        client_id=1,
        request_id="req",
        access_token="access123",
        refresh_token="refresh123",
    )
    expected_credentials = CommunityCredentials(
        steam_id="76561197960435530",
        session_id="session123",
        steam_login_secure="securecookie123",
    )

    original_login = client.auth.login_with_credentials
    original_build = client.auth.community_credentials_from_login

    def fake_login(*args, **kwargs):
        captured.update(kwargs)
        return login_result

    client.auth.login_with_credentials = fake_login
    client.auth.community_credentials_from_login = lambda result: expected_credentials

    client.login_to_community(
        "tester",
        "secret",
        steam_guard_code="123456",
        prompt_for_steam_guard=True,
        poll_interval=2.0,
        poll_timeout=90.0,
    )

    client.auth.login_with_credentials = original_login
    client.auth.community_credentials_from_login = original_build

    assert captured["steam_guard_code"] == "123456"
    assert captured["prompt_for_steam_guard"] is True
    assert captured["poll_interval"] == 2.0
    assert captured["poll_timeout"] == 90.0
    client.close()


def test_client_can_set_community_credentials_from_cookie_string() -> None:
    client = SteamClient(api_key="test")

    credentials = client.set_community_credentials_from_cookie_string(
        "sessionid=session123; steamLoginSecure=76561197960435530%7C%7Ctoken123"
    )

    assert credentials.steam_id == "76561197960435530"
    assert credentials.session_id == "session123"
    assert credentials.access_token == "token123"
    assert client._transport.community_credentials == credentials
    client.close()


def test_client_can_export_community_cookie_string() -> None:
    client = SteamClient(api_key="test")
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="76561197960435530%7C%7Ctoken123",
        )
    )

    cookie_string = client.export_community_cookie_string()

    assert cookie_string == "sessionid=session123; steamLoginSecure=76561197960435530%7C%7Ctoken123"
    client.close()


def test_client_can_login_with_refresh_token() -> None:
    client = SteamClient(api_key="test")
    expected_credentials = CommunityCredentials(
        steam_id="76561197960435530",
        session_id="session123",
        steam_login_secure="76561197960435530%7C%7Ctoken123",
    )

    original_method = client.auth.community_credentials_from_refresh_token
    client.auth.community_credentials_from_refresh_token = lambda token: expected_credentials

    returned = client.login_to_community_with_refresh_token("refresh123")

    client.auth.community_credentials_from_refresh_token = original_method

    assert returned == expected_credentials
    assert client._transport.community_credentials == expected_credentials
    client.close()


def test_client_can_get_owned_games_for_user_from_vanity_identifier() -> None:
    session = SequenceSession(
        [
            DummyResponse(json_data={"response": {"steamid": "76561197968052866", "success": 1}}),
            DummyResponse(json_data={"response": {"game_count": 1, "games": [{"appid": 570}]}}),
        ]
    )
    client = SteamClient(api_key="test", session=session)

    owned_games = client.get_owned_games_for_user("gaben", include_appinfo=False)

    assert owned_games["game_count"] == 1
    assert owned_games["games"][0]["appid"] == 570
    assert len(session.calls) == 2
    client.close()


def test_inventory_service_uses_community_inventory_endpoint() -> None:
    session = RecordingSession(DummyResponse(json_data={"assets": [], "descriptions": [], "total_inventory_count": 0}))
    client = SteamClient(session=session)

    client.inventory.get_inventory("76561197960435530", 730, 2, language="english", count=5000, start_asset_id="123")

    call = session.calls[0]
    assert call["url"] == "https://steamcommunity.com/inventory/76561197960435530/730/2"
    assert call["params"]["l"] == "english"
    assert call["params"]["count"] == 5000
    assert call["params"]["start_assetid"] == "123"
    client.close()


def test_inventory_service_combines_assets_with_descriptions() -> None:
    payload = {
        "assets": [{"assetid": "1", "classid": "10", "instanceid": "0"}],
        "descriptions": [{"classid": "10", "instanceid": "0", "market_hash_name": "Example Item"}],
        "total_inventory_count": 1,
        "more_items": False,
    }
    session = RecordingSession(DummyResponse(json_data=payload))
    client = SteamClient(session=session)

    result = client.inventory.get_inventory_items("76561197960435530", 730, 2)

    assert result["total_inventory_count"] == 1
    assert result["items"][0]["assetid"] == "1"
    assert result["items"][0]["description"]["market_hash_name"] == "Example Item"
    client.close()


def test_inventory_service_can_fetch_full_inventory_across_pages() -> None:
    session = SequenceSession(
        [
            DummyResponse(
                json_data={
                    "assets": [{"assetid": "1", "classid": "10", "instanceid": "0"}],
                    "descriptions": [{"classid": "10", "instanceid": "0", "market_hash_name": "One"}],
                    "total_inventory_count": 2,
                    "more_items": True,
                    "last_assetid": "1",
                }
            ),
            DummyResponse(
                json_data={
                    "assets": [{"assetid": "2", "classid": "11", "instanceid": "0"}],
                    "descriptions": [{"classid": "11", "instanceid": "0", "market_hash_name": "Two"}],
                    "total_inventory_count": 2,
                    "more_items": False,
                }
            ),
        ]
    )
    client = SteamClient(session=session)

    result = client.inventory.get_full_inventory("76561197960435530", 730, 2, count=1)

    assert result["pages_fetched"] == 2
    assert len(result["assets"]) == 2
    assert len(result["descriptions"]) == 2
    assert session.calls[1]["params"]["start_assetid"] == "1"
    client.close()


def test_inventory_service_can_fetch_full_inventory_items_across_pages() -> None:
    session = SequenceSession(
        [
            DummyResponse(
                json_data={
                    "assets": [{"assetid": "1", "classid": "10", "instanceid": "0"}],
                    "descriptions": [{"classid": "10", "instanceid": "0", "market_hash_name": "One"}],
                    "total_inventory_count": 2,
                    "more_items": True,
                    "last_assetid": "1",
                }
            ),
            DummyResponse(
                json_data={
                    "assets": [{"assetid": "2", "classid": "11", "instanceid": "0"}],
                    "descriptions": [{"classid": "11", "instanceid": "0", "market_hash_name": "Two"}],
                    "total_inventory_count": 2,
                    "more_items": False,
                }
            ),
        ]
    )
    client = SteamClient(session=session)

    result = client.inventory.get_full_inventory_items("76561197960435530", 730, 2, count=1)

    assert result["pages_fetched"] == 2
    assert result["items"][0]["description"]["market_hash_name"] == "One"
    assert result["items"][1]["description"]["market_hash_name"] == "Two"
    client.close()


def test_client_can_get_inventory_for_user_without_api_key_via_vanity_resolution() -> None:
    xml = """
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <profile><steamID64>76561197968052866</steamID64></profile>
    """
    inventory_payload = {"assets": [], "descriptions": [], "total_inventory_count": 0}
    session = SequenceSession(
        [
            DummyResponse(text=xml),
            DummyResponse(json_data=inventory_payload),
        ]
    )
    client = SteamClient(session=session)

    result = client.get_inventory_for_user("gaben", 730, 2)

    assert result["total_inventory_count"] == 0
    assert session.calls[0]["url"] == "https://steamcommunity.com/id/gaben/"
    assert session.calls[1]["url"] == "https://steamcommunity.com/inventory/76561197968052866/730/2"
    client.close()


def test_client_can_get_full_inventory_for_user_without_api_key_via_vanity_resolution() -> None:
    xml = """
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <profile><steamID64>76561197968052866</steamID64></profile>
    """
    session = SequenceSession(
        [
            DummyResponse(text=xml),
            DummyResponse(
                json_data={
                    "assets": [{"assetid": "1", "classid": "10", "instanceid": "0"}],
                    "descriptions": [{"classid": "10", "instanceid": "0"}],
                    "total_inventory_count": 1,
                    "more_items": False,
                }
            ),
        ]
    )
    client = SteamClient(session=session)

    result = client.get_full_inventory_for_user("gaben", 730, 2)

    assert result["pages_fetched"] == 1
    assert len(result["assets"]) == 1
    assert session.calls[0]["url"] == "https://steamcommunity.com/id/gaben/"
    client.close()


def test_market_price_overview_uses_community_market_endpoint() -> None:
    session = RecordingSession(DummyResponse(json_data={"success": True, "lowest_price": "$12.34"}))
    client = SteamClient(session=session)

    result = client.market.get_price_overview(730, "AK-47 | Redline (Field-Tested)", currency=1)

    call = session.calls[0]
    assert call["url"] == "https://steamcommunity.com/market/priceoverview/"
    assert call["params"]["appid"] == 730
    assert call["params"]["market_hash_name"] == "AK-47 | Redline (Field-Tested)"
    assert call["params"]["currency"] == 1
    assert result["lowest_price"] == "$12.34"
    client.close()


def test_market_search_uses_render_endpoint() -> None:
    session = RecordingSession(DummyResponse(json_data={"success": True, "total_count": 123}))
    client = SteamClient(session=session)

    result = client.market.search_items(query="AK-47", app_id=730, count=5)

    call = session.calls[0]
    assert call["url"] == "https://steamcommunity.com/market/search/render/"
    assert call["params"]["query"] == "AK-47"
    assert call["params"]["appid"] == 730
    assert call["params"]["count"] == 5
    assert call["params"]["norender"] == 1
    assert result["total_count"] == 123
    client.close()


def test_market_item_listings_uses_listings_render_endpoint() -> None:
    session = RecordingSession(DummyResponse(json_data={"success": True, "listinginfo": {}}))
    client = SteamClient(session=session)

    result = client.market.get_item_listings(730, "AK-47 | Redline (Field-Tested)", count=10)

    call = session.calls[0]
    assert call["url"] == "https://steamcommunity.com/market/listings/730/AK-47%20%7C%20Redline%20%28Field-Tested%29/render/"
    assert call["params"]["count"] == 10
    assert call["params"]["country"] == "US"
    assert call["params"]["language"] == "english"
    assert call["params"]["currency"] == 1
    assert result["success"] is True
    client.close()


def test_market_get_item_name_id_parses_listings_page_html() -> None:
    html = "<script>Market_LoadOrderSpread( 7178002 );</script>"
    session = RecordingSession(DummyResponse(text=html))
    client = SteamClient(session=session)

    item_name_id = client.market.get_item_name_id(730, "AK-47 | Redline (Field-Tested)")

    assert item_name_id == 7178002
    assert session.calls[0]["url"] == "https://steamcommunity.com/market/listings/730/AK-47%20%7C%20Redline%20%28Field-Tested%29"
    client.close()


def test_market_get_item_orders_histogram_uses_item_name_id_lookup() -> None:
    session = SequenceSession(
        [
            DummyResponse(text="<script>Market_LoadOrderSpread( 7178002 );</script>"),
            DummyResponse(json_data={"success": 1, "sell_order_count": "10"}),
        ]
    )
    client = SteamClient(session=session)

    result = client.market.get_item_orders_histogram(app_id=730, market_hash_name="AK-47 | Redline (Field-Tested)")

    assert result["success"] == 1
    assert session.calls[1]["url"] == "https://steamcommunity.com/market/itemordershistogram"
    assert session.calls[1]["params"]["item_nameid"] == 7178002
    client.close()


def test_market_get_item_orders_summary_parses_tables() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "success": 1,
                "buy_order_count": "123",
                "buy_order_price": "$1.23",
                "buy_order_summary": '<span class="market_commodity_orders_header_promote">123</span> buyers at <span class="market_commodity_orders_header_promote">$1.23</span> or lower',
                "buy_order_table": "<table><tr><td>$1.23</td><td>2</td></tr><tr><td>$1.22</td><td>5</td></tr></table>",
                "sell_order_count": "456",
                "sell_order_price": "$1.25",
                "sell_order_summary": '<span class="market_commodity_orders_header_promote">456</span> sellers at <span class="market_commodity_orders_header_promote">$1.25</span> or higher',
                "sell_order_table": "<table><tr><td>$1.25</td><td>3</td></tr></table>",
                "highest_buy_order": "123",
                "lowest_sell_order": "125",
            }
        )
    )
    client = SteamClient(session=session)

    result = client.market.get_item_orders_summary(item_name_id=7178002)

    assert result["item_name_id"] == 7178002
    assert result["buy_order_summary"] == "123 buyers at $1.23 or lower"
    assert result["sell_order_summary"] == "456 sellers at $1.25 or higher"
    assert result["buy_orders"][0]["price_text"] == "$1.23"
    assert result["buy_orders"][1]["quantity_text"] == "5"
    assert result["sell_orders"][0]["price_text"] == "$1.25"
    client.close()


def test_market_get_price_history_parses_listings_page_html() -> None:
    html = """
    <script>
    var strFormatPrefix = '$';
    var strFormatSuffix = '';
    var line1=[["Feb 21 2014 01: +0",41.405,"198"],["Feb 22 2014 01: +0",35.08,"225"]];
    </script>
    """
    session = RecordingSession(DummyResponse(text=html))
    client = SteamClient(session=session)

    result = client.market.get_price_history(730, "AK-47 | Redline (Field-Tested)")

    assert result["success"] is True
    assert result["price_prefix"] == "$"
    assert result["price_suffix"] == ""
    assert len(result["prices"]) == 2
    assert result["prices"][0][0] == "Feb 21 2014 01: +0"
    client.close()


def test_client_can_get_friend_list_for_user_from_profile_url() -> None:
    session = RecordingSession(
        DummyResponse(json_data={"friendslist": {"friends": [{"steamid": "76561197960435530"}]}})
    )
    client = SteamClient(api_key="test", session=session)

    friends = client.get_friend_list_for_user("https://steamcommunity.com/profiles/76561197960434622/")

    assert friends["friendslist"]["friends"][0]["steamid"] == "76561197960435530"
    call = session.calls[0]
    assert call["params"]["steamid"] == "76561197960434622"
    client.close()


def test_auth_can_build_community_credentials_from_refresh_token() -> None:
    response = DummyResponse(json_data={"response": {"ok": True}})
    response.cookies = {"steamLoginSecure": "76561197960435530%7C%7Ctoken123"}
    client = SteamClient(api_key="test")

    original_decode = client.auth.decode_jwt
    original_create_session = client.auth.create_session_id
    original_set_cookie = client.auth.set_community_login_cookie

    client.auth.decode_jwt = lambda token: {"sub": "76561197960435530"}
    client.auth.create_session_id = lambda: "session123"
    client.auth.set_community_login_cookie = lambda **kwargs: response

    credentials = client.auth.community_credentials_from_refresh_token("refresh123")

    client.auth.decode_jwt = original_decode
    client.auth.create_session_id = original_create_session
    client.auth.set_community_login_cookie = original_set_cookie

    assert credentials.steam_id == "76561197960435530"
    assert credentials.session_id == "session123"
    assert credentials.refresh_token == "refresh123"
    assert credentials.steam_login_secure == "76561197960435530%7C%7Ctoken123"
    client.close()


def test_auth_login_with_credentials_uses_steam_guard_code_when_required() -> None:
    client = SteamClient(api_key="test")
    started = {
        "client_id": 1,
        "request_id": "req",
        "steamid": "76561197960435530",
        "allowed_confirmations": [{"confirmation_type": 3}],
    }
    polls = [
        {"had_remote_interaction": False},
        {
            "account_name": "tester",
            "access_token": "access123",
            "refresh_token": "refresh123",
            "had_remote_interaction": True,
        },
    ]
    updates = []

    original_begin = client.auth.begin_auth_session_via_credentials
    original_poll = client.auth.poll_auth_session_status
    original_update = client.auth.update_auth_session_with_steam_guard_code

    client.auth.begin_auth_session_via_credentials = lambda *args, **kwargs: started
    client.auth.poll_auth_session_status = lambda *args, **kwargs: polls.pop(0)
    client.auth.update_auth_session_with_steam_guard_code = (
        lambda client_id, steam_id, code_type, code: updates.append((client_id, steam_id, code_type, code))
    )

    result = client.auth.login_with_credentials(
        "tester",
        "secret",
        steam_guard_code="654321",
        poll_interval=0.01,
        poll_timeout=0.02,
    )

    client.auth.begin_auth_session_via_credentials = original_begin
    client.auth.poll_auth_session_status = original_poll
    client.auth.update_auth_session_with_steam_guard_code = original_update

    assert result.access_token == "access123"
    assert result.refresh_token == "refresh123"
    assert updates == [(1, "76561197960435530", 3, "654321")]
    client.close()


def test_auth_login_with_credentials_raises_clear_error_when_guard_code_missing() -> None:
    client = SteamClient(api_key="test")
    started = {
        "client_id": 1,
        "request_id": "req",
        "steamid": "76561197960435530",
        "allowed_confirmations": [{"confirmation_type": 3}],
    }

    original_begin = client.auth.begin_auth_session_via_credentials
    original_poll = client.auth.poll_auth_session_status

    client.auth.begin_auth_session_via_credentials = lambda *args, **kwargs: started
    client.auth.poll_auth_session_status = lambda *args, **kwargs: {"had_remote_interaction": False}

    with pytest.raises(SteamAuthenticationError, match="Steam Guard mobile authenticator code is required"):
        client.auth.login_with_credentials(
            "tester",
            "secret",
            poll_interval=0.01,
            poll_timeout=0.02,
        )

    client.auth.begin_auth_session_via_credentials = original_begin
    client.auth.poll_auth_session_status = original_poll
    client.close()


def test_auth_login_with_credentials_raises_clear_error_when_begin_response_is_incomplete() -> None:
    client = SteamClient(api_key="test")

    original_begin = client.auth.begin_auth_session_via_credentials
    client.auth.begin_auth_session_via_credentials = lambda *args, **kwargs: {"interval": 1}

    with pytest.raises(
        SteamAuthenticationError,
        match="Your credentials are incorrect or the Steam account is unable to login",
    ):
        client.auth.login_with_credentials("tester", "secret")

    client.auth.begin_auth_session_via_credentials = original_begin
    client.close()


def test_community_edit_profile_posts_profile_save_payload() -> None:
    session = RecordingSession(DummyResponse(json_data={"success": 1}))
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    client.community.edit_profile(
        persona_name="Example Name",
        summary="Example summary",
        custom_url="example-custom-url",
        country="US",
        state="FL",
        city=12345,
    )

    call = session.calls[0]
    assert call["url"] == "https://steamcommunity.com/profiles/76561197960435530/edit/"
    assert call["data"]["sessionID"] == "session123"
    assert call["data"]["type"] == "profileSave"
    assert call["data"]["personaName"] == "Example Name"
    assert call["data"]["summary"] == "Example summary"
    assert call["data"]["customURL"] == "example-custom-url"
    assert call["data"]["country"] == "US"
    assert call["data"]["state"] == "FL"
    assert call["data"]["city"] == "12345"
    assert call["data"]["json"] == 1
    client.close()


def test_community_edit_profile_raises_on_error_payload() -> None:
    session = RecordingSession(DummyResponse(json_data={"success": 2, "errmsg": "Bad value<br />"}))
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    with pytest.raises(SteamResponseError, match="Profile update failed: Bad value"):
        client.community.edit_profile(persona_name="bad")

    client.close()


def test_community_get_account_info_parses_embedded_json() -> None:
    html = """
    <div id="profile_edit_config"
         data-userinfo="{&quot;logged_in&quot;:true,&quot;steamid&quot;:&quot;76561197960435530&quot;,&quot;account_name&quot;:&quot;tester&quot;,&quot;is_limited&quot;:false}"
         data-profile-edit="{&quot;strPersonaName&quot;:&quot;Example&quot;,&quot;Privacy&quot;:{&quot;PrivacySettings&quot;:{&quot;PrivacyProfile&quot;:1},&quot;eCommentPermission&quot;:0}}"></div>
    """
    session = RecordingSession(DummyResponse(text=html))
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    info = client.community.get_account_info()

    assert info["logged_in"] is True
    assert info["steamid"] == "76561197960435530"
    assert info["account_name"] == "tester"
    assert info["is_limited"] is False
    client.close()


def test_community_get_profile_privacy_parses_embedded_json() -> None:
    html = """
    <div id="profile_edit_config"
         data-userinfo="{&quot;logged_in&quot;:true}"
         data-profile-edit="{&quot;strPersonaName&quot;:&quot;Example&quot;,&quot;Privacy&quot;:{&quot;PrivacySettings&quot;:{&quot;PrivacyProfile&quot;:1,&quot;PrivacyInventory&quot;:2},&quot;eCommentPermission&quot;:0}}"></div>
    """
    session = RecordingSession(DummyResponse(text=html))
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    privacy = client.community.get_profile_privacy()

    assert privacy["PrivacySettings"]["PrivacyProfile"] == 1
    assert privacy["PrivacySettings"]["PrivacyInventory"] == 2
    assert privacy["eCommentPermission"] == 0
    client.close()


def test_community_get_profile_bundle_parses_embedded_json_once() -> None:
    html = """
    <div id="profile_edit_config"
         data-userinfo="{&quot;logged_in&quot;:true,&quot;steamid&quot;:&quot;76561197960435530&quot;,&quot;account_name&quot;:&quot;tester&quot;}"
         data-profile-edit="{&quot;strPersonaName&quot;:&quot;Example&quot;,&quot;Privacy&quot;:{&quot;PrivacySettings&quot;:{&quot;PrivacyProfile&quot;:1,&quot;PrivacyInventory&quot;:2},&quot;eCommentPermission&quot;:0}}"></div>
    """
    session = RecordingSession(DummyResponse(text=html))
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    bundle = client.community.get_profile_bundle()

    assert bundle["account_info"]["account_name"] == "tester"
    assert bundle["profile_edit_state"]["strPersonaName"] == "Example"
    assert bundle["privacy"]["PrivacySettings"]["PrivacyInventory"] == 2
    assert len(session.calls) == 1
    client.close()


def test_community_get_trade_offer_url_parses_partner_and_token() -> None:
    html = """
    <input size="45" type="text" class="trade_offer_access_url" id="trade_offer_access_url"
           value="https://steamcommunity.com/tradeoffer/new/?partner=1189313876&amp;token=vrJtfrV_" readonly>
    """
    session = RecordingSession(DummyResponse(text=html))
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    trade_url = client.community.get_trade_offer_url()

    assert trade_url["trade_url"] == "https://steamcommunity.com/tradeoffer/new/?partner=1189313876&token=vrJtfrV_"
    assert trade_url["partner_id"] == "1189313876"
    assert trade_url["token"] == "vrJtfrV_"
    client.close()


def test_community_rotate_trade_offer_url_posts_expected_request() -> None:
    session = SequenceSession(
        [
            DummyResponse(text="newtoken123"),
            DummyResponse(
                text='<div id="profile_edit_config" data-userinfo="{&quot;accountid&quot;:1189313876}"></div>'
            ),
        ]
    )
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    rotated = client.community.rotate_trade_offer_url()

    first_call = session.calls[0]
    assert first_call["url"] == "https://steamcommunity.com/profiles/76561197960435530/tradeoffers/newtradeurl"
    assert first_call["data"]["sessionid"] == "session123"
    assert first_call["headers"]["Referer"] == "https://steamcommunity.com/profiles/76561197960435530/tradeoffers/privacy"
    assert rotated["partner_id"] == "1189313876"
    assert rotated["token"] == "newtoken123"
    assert rotated["trade_url"] == "https://steamcommunity.com/tradeoffer/new/?partner=1189313876&token=newtoken123"
    client.close()


def test_community_get_web_api_key_status_parses_access_denied_reason() -> None:
    html = """
    <div id="mainContents"><h2>Access Denied</h2></div>
    <div id="bodyContents_lo">
        <p>You will be granted access to Steam Web API keys when you have games in your Steam account.</p>
    </div>
    """
    session = RecordingSession(DummyResponse(text=html))
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    status = client.community.get_web_api_key_status()

    assert status["has_access"] is False
    assert status["api_key"] is None
    assert status["domain"] is None
    assert "have games in your Steam account" in status["reason"]
    client.close()


def test_community_edit_profile_requires_at_least_one_field() -> None:
    client = SteamClient(api_key="test")
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    with pytest.raises(SteamValidationError):
        client.community.edit_profile()

    client.close()


def test_community_update_custom_url_calls_edit_profile() -> None:
    session = RecordingSession(DummyResponse(json_data={"success": 1}))
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    client.community.update_custom_url("example-url")

    call = session.calls[0]
    assert call["data"]["customURL"] == "example-url"
    client.close()


def test_community_set_profile_private_uses_private_values() -> None:
    session = RecordingSession(DummyResponse(json_data={"success": 1}))
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    client.community.set_profile_private()

    call = session.calls[0]
    assert '"PrivacyProfile":1' in call["data"]["Privacy"]
    assert '"PrivacyOwnedGames":1' in call["data"]["Privacy"]
    client.close()


def test_community_set_profile_privacy_raises_on_error_payload() -> None:
    session = RecordingSession(DummyResponse(json_data={"success": 2, "errmsg": "Denied<br />"}))
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    with pytest.raises(SteamResponseError, match="Profile privacy update failed: Denied"):
        client.community.set_profile_private()

    client.close()


def test_community_set_profile_public_uses_public_values() -> None:
    session = RecordingSession(DummyResponse(json_data={"success": 1}))
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    client.community.set_profile_public()

    call = session.calls[0]
    assert '"PrivacyProfile":3' in call["data"]["Privacy"]
    assert '"PrivacyFriendsList":3' in call["data"]["Privacy"]
    client.close()


def test_groups_get_group_details_parses_memberslist_xml() -> None:
    xml = """
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <memberList>
      <groupID64>103582791429521412</groupID64>
      <groupDetails>
        <groupName><![CDATA[Valve]]></groupName>
        <groupURL><![CDATA[Valve]]></groupURL>
        <headline><![CDATA[VALVE]]></headline>
        <summary><![CDATA[Test summary]]></summary>
        <avatarIcon><![CDATA[https://example.com/icon.jpg]]></avatarIcon>
        <avatarMedium><![CDATA[https://example.com/medium.jpg]]></avatarMedium>
        <avatarFull><![CDATA[https://example.com/full.jpg]]></avatarFull>
        <memberCount>152</memberCount>
        <membersInChat>53</membersInChat>
        <membersInGame>0</membersInGame>
        <membersOnline>67</membersOnline>
      </groupDetails>
      <memberCount>152</memberCount>
      <totalPages>3</totalPages>
      <currentPage>2</currentPage>
    </memberList>
    """
    session = RecordingSession(DummyResponse(text=xml))
    client = SteamClient(api_key="test", session=session)

    details = client.groups.get_group_details("Valve", page=2)

    assert details["group_id64"] == "103582791429521412"
    assert details["group_name"] == "Valve"
    assert details["group_url"] == "Valve"
    assert details["headline"] == "VALVE"
    assert details["summary"] == "Test summary"
    assert details["member_count"] == 152
    assert details["members_in_chat"] == 53
    assert details["members_in_game"] == 0
    assert details["members_online"] == 67
    assert details["total_pages"] == 3
    assert details["current_page"] == 2
    client.close()


def test_groups_get_group_members_parses_member_ids() -> None:
    xml = """
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <memberList>
      <groupID64>103582791429521412</groupID64>
      <memberCount>152</memberCount>
      <totalPages>3</totalPages>
      <currentPage>1</currentPage>
      <members>
        <steamID64>76561197985607672</steamID64>
        <steamID64>76561197960435530</steamID64>
      </members>
    </memberList>
    """
    session = RecordingSession(DummyResponse(text=xml))
    client = SteamClient(api_key="test", session=session)

    members = client.groups.get_group_members("Valve", page=1)

    assert members["group_id64"] == "103582791429521412"
    assert members["member_count"] == 152
    assert members["total_pages"] == 3
    assert members["current_page"] == 1
    assert members["members"] == ["76561197985607672", "76561197960435530"]
    client.close()


def test_group_availability_uses_form_data_and_browser_headers() -> None:
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        "<response><fieldId><![CDATA[groupName]]></fieldId>"
        "<bResults><![CDATA[1]]></bResults>"
        "<sResults><![CDATA[available]]></sResults></response>"
    )
    session = RecordingSession(DummyResponse(text=xml))
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    result = client.groups.check_name_availability("examplegroupname")

    call = session.calls[0]
    assert result.available is True
    assert call["data"]["xml"] == "1"
    assert call["data"]["type"] == "groupName"
    assert call["headers"]["Content-Type"] == "application/x-www-form-urlencoded; charset=UTF-8"
    assert call["headers"]["Origin"] == "https://steamcommunity.com"
    assert call["headers"]["Referer"] == "https://steamcommunity.com/actions/GroupCreate"
    assert call["json"] is None
    client.close()


def test_group_availability_rate_limit_raises_specific_error() -> None:
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        "<response><fieldId><![CDATA[groupName]]></fieldId>"
        "<bResults><![CDATA[]]></bResults>"
        "<sResults><![CDATA[You've made too many requests recently. Please wait and try your request again later.]]></sResults></response>"
    )
    session = RecordingSession(DummyResponse(text=xml))
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    with pytest.raises(SteamRateLimitError):
        client.groups.check_name_availability("examplegroupname")

    client.close()


def test_create_group_raises_clear_error_for_account_restriction_page() -> None:
    error_html = """
    <html><body><div id="message"><h3>Your account does not meet the requirements to use this feature.</h3></div></body></html>
    """
    session = SequenceSession(
        [
            DummyResponse(text=error_html),
        ]
    )
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    with pytest.raises(SteamAuthenticationError):
        client.groups.create_group(
            name="examplegroup",
            abbreviation="abc12",
            group_url="examplegroup",
            public=False,
            wait_for_sync=0,
            validate_availability=False,
        )

    client.close()


def test_create_group_can_skip_availability_checks() -> None:
    session = SequenceSession(
        [
            DummyResponse(json_data={}),
            DummyResponse(json_data={}),
        ]
    )
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    original_name = client.groups.check_name_availability
    original_tag = client.groups.check_tag_availability
    original_url = client.groups.check_url_availability
    original_fetch_id = client.groups.fetch_group_id
    original_fetch_id64 = client.groups.fetch_group_id64

    client.groups.check_name_availability = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("name availability should not be called")
    )
    client.groups.check_tag_availability = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("tag availability should not be called")
    )
    client.groups.check_url_availability = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("url availability should not be called")
    )
    client.groups.fetch_group_id = lambda _group_url: "1234"
    client.groups.fetch_group_id64 = lambda _group_url: "76561198000000000"

    created = client.groups.create_group(
        name="examplegroup",
        abbreviation="abc12",
        group_url="examplegroup",
        public=False,
        wait_for_sync=0,
        validate_availability=False,
    )

    client.groups.check_name_availability = original_name
    client.groups.check_tag_availability = original_tag
    client.groups.check_url_availability = original_url
    client.groups.fetch_group_id = original_fetch_id
    client.groups.fetch_group_id64 = original_fetch_id64

    assert created.group_id == "1234"
    assert created.group_id64 == "76561198000000000"
    assert len(session.calls) == 2
    client.close()
