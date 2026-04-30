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
    build_group_url,
    build_inventory_url,
    build_market_listing_url,
    build_steam_profile_url,
    build_trade_offer_url,
    build_workshop_file_url,
    normalize_group_slug,
    normalize_published_file_id,
    parse_group_url,
    parse_inventory_url,
    parse_market_listing_url,
    parse_steam_profile_url,
    parse_trade_offer_url,
    parse_workshop_file_url,
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


def test_client_community_helpers_delegate_to_community_service() -> None:
    client = SteamClient()

    original_get_account_info = client.community.get_account_info
    original_get_profile_edit_state = client.community.get_profile_edit_state
    original_get_profile_privacy = client.community.get_profile_privacy
    original_get_trade_offer_url = client.community.get_trade_offer_url
    original_rotate_trade_offer_url = client.community.rotate_trade_offer_url
    original_get_web_api_key_status = client.community.get_web_api_key_status
    original_get_web_api_key_page_state = client.community.get_web_api_key_page_state
    original_set_profile_privacy = client.community.set_profile_privacy
    original_edit_profile = client.community.edit_profile
    original_update_persona_name = client.community.update_persona_name
    original_update_custom_url = client.community.update_custom_url
    original_update_real_name = client.community.update_real_name
    original_update_summary = client.community.update_summary
    original_update_location = client.community.update_location
    original_set_profile_public = client.community.set_profile_public
    original_set_profile_private = client.community.set_profile_private
    original_upload_avatar = client.community.upload_avatar

    client.community.get_account_info = lambda steam_id=None: {"steamid": steam_id or "self"}
    client.community.get_profile_edit_state = lambda steam_id=None: {"steamid": steam_id or "self", "strPersonaName": "Example"}
    client.community.get_profile_privacy = lambda steam_id=None: {"steamid": steam_id or "self", "PrivacySettings": {}}
    client.community.get_trade_offer_url = lambda steam_id=None: {"steamid": steam_id or "self", "token": "abc"}
    client.community.rotate_trade_offer_url = lambda steam_id=None: {"steamid": steam_id or "self", "token": "rotated"}
    client.community.get_web_api_key_status = lambda: {"has_access": False}
    client.community.get_web_api_key_page_state = lambda: {"registration_form_visible": True}
    client.community.set_profile_privacy = lambda steam_id=None, **kwargs: {"steamid": steam_id or "self", "kwargs": kwargs}
    client.community.edit_profile = lambda steam_id=None, **kwargs: {"steamid": steam_id or "self", "kwargs": kwargs}
    client.community.update_persona_name = lambda steam_id=None, persona_name="": {"steamid": steam_id or "self", "persona_name": persona_name}
    client.community.update_custom_url = lambda custom_url, steam_id=None: {"steamid": steam_id or "self", "custom_url": custom_url}
    client.community.update_real_name = lambda real_name, steam_id=None: {"steamid": steam_id or "self", "real_name": real_name}
    client.community.update_summary = lambda summary, steam_id=None: {"steamid": steam_id or "self", "summary": summary}
    client.community.update_location = lambda country=None, state=None, city=None, steam_id=None: {
        "steamid": steam_id or "self",
        "country": country,
        "state": state,
        "city": city,
    }
    client.community.set_profile_public = lambda steam_id=None: {"steamid": steam_id or "self", "visibility": "public"}
    client.community.set_profile_private = lambda steam_id=None: {"steamid": steam_id or "self", "visibility": "private"}
    client.community.upload_avatar = lambda image_path, steam_id=None: {"steamid": steam_id or "self", "image_path": str(image_path)}

    assert client.get_account_info()["steamid"] == "self"
    assert client.get_profile_edit_state()["strPersonaName"] == "Example"
    assert client.get_profile_privacy()["steamid"] == "self"
    assert client.get_trade_offer_url()["token"] == "abc"
    assert client.rotate_trade_offer_url()["token"] == "rotated"
    assert client.get_web_api_key_status()["has_access"] is False
    assert client.get_web_api_key_page_state()["registration_form_visible"] is True
    assert client.set_profile_privacy(privacy_profile=1)["kwargs"]["privacy_profile"] == 1
    assert client.edit_profile(persona_name="Name")["kwargs"]["persona_name"] == "Name"
    assert client.update_persona_name("Name")["persona_name"] == "Name"
    assert client.update_custom_url("example")["custom_url"] == "example"
    assert client.update_real_name("Real")["real_name"] == "Real"
    assert client.update_summary("Summary")["summary"] == "Summary"
    assert client.update_location(country="US", state="WA", city="Seattle")["city"] == "Seattle"
    assert client.set_profile_public()["visibility"] == "public"
    assert client.set_profile_private()["visibility"] == "private"
    assert client.upload_avatar("avatar.png")["image_path"] == "avatar.png"

    client.community.get_account_info = original_get_account_info
    client.community.get_profile_edit_state = original_get_profile_edit_state
    client.community.get_profile_privacy = original_get_profile_privacy
    client.community.get_trade_offer_url = original_get_trade_offer_url
    client.community.rotate_trade_offer_url = original_rotate_trade_offer_url
    client.community.get_web_api_key_status = original_get_web_api_key_status
    client.community.get_web_api_key_page_state = original_get_web_api_key_page_state
    client.community.set_profile_privacy = original_set_profile_privacy
    client.community.edit_profile = original_edit_profile
    client.community.update_persona_name = original_update_persona_name
    client.community.update_custom_url = original_update_custom_url
    client.community.update_real_name = original_update_real_name
    client.community.update_summary = original_update_summary
    client.community.update_location = original_update_location
    client.community.set_profile_public = original_set_profile_public
    client.community.set_profile_private = original_set_profile_private
    client.community.upload_avatar = original_upload_avatar
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


def test_profile_url_helpers_build_and_parse() -> None:
    profile_url = build_steam_profile_url(vanity="gaben")
    parsed = parse_steam_profile_url(profile_url)

    assert profile_url == "https://steamcommunity.com/id/gaben/"
    assert parsed["profile_type"] == "vanity"
    assert parsed["vanity"] == "gaben"
    assert parsed["profile_url"] == profile_url


def test_group_url_helpers_build_and_parse() -> None:
    group_url = build_group_url("steamdb")
    parsed = parse_group_url(group_url)

    assert group_url == "https://steamcommunity.com/groups/steamdb/"
    assert parsed["group_slug"] == "steamdb"
    assert parsed["group_url"] == group_url


def test_workshop_url_helpers_build_and_parse() -> None:
    workshop_url = build_workshop_file_url("3210489689")
    parsed = parse_workshop_file_url(workshop_url)

    assert workshop_url == "https://steamcommunity.com/sharedfiles/filedetails/?id=3210489689"
    assert parsed["published_file_id"] == "3210489689"
    assert parsed["workshop_url"] == workshop_url


def test_inventory_url_helpers_build_and_parse() -> None:
    inventory_url = build_inventory_url("76561197960435530", 753, 6)
    parsed = parse_inventory_url(inventory_url)

    assert inventory_url == "https://steamcommunity.com/inventory/76561197960435530/753/6"
    assert parsed["steam_id"] == "76561197960435530"
    assert parsed["app_id"] == 753
    assert parsed["context_id"] == "6"
    assert parsed["inventory_url"] == inventory_url


def test_market_listing_url_helpers_build_and_parse() -> None:
    market_url = build_market_listing_url(730, "AK-47 | Redline (Field-Tested)")
    parsed = parse_market_listing_url(market_url)

    assert market_url == "https://steamcommunity.com/market/listings/730/AK-47%20%7C%20Redline%20%28Field-Tested%29"
    assert parsed["app_id"] == 730
    assert parsed["market_hash_name"] == "AK-47 | Redline (Field-Tested)"
    assert parsed["market_url"] == market_url


def test_group_slug_normalizer_accepts_full_group_url() -> None:
    assert normalize_group_slug("https://steamcommunity.com/groups/steamdb/") == "steamdb"


def test_published_file_id_normalizer_accepts_full_workshop_url() -> None:
    assert normalize_published_file_id("https://steamcommunity.com/sharedfiles/filedetails/?id=3210489689") == "3210489689"


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


def test_users_get_player_summaries_map_returns_steamid_keyed_mapping() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "players": [
                        {"steamid": "76561197960435530", "personaname": "Robin"},
                        {"steamid": "76561197960287930", "personaname": "John"},
                    ]
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.users.get_player_summaries_map(["76561197960435530", "76561197960287930"])

    assert result["76561197960435530"]["personaname"] == "Robin"
    assert result["76561197960287930"]["personaname"] == "John"
    client.close()


def test_users_get_friend_summaries_returns_limited_player_summaries() -> None:
    session = SequenceSession(
        [
            DummyResponse(
                json_data={
                    "friendslist": {
                        "friends": [
                            {"steamid": "76561197960435530"},
                            {"steamid": "76561197960287930"},
                        ]
                    }
                }
            ),
            DummyResponse(
                json_data={
                    "response": {
                        "players": [
                            {"steamid": "76561197960435530", "personaname": "Robin"},
                        ]
                    }
                }
            ),
        ]
    )
    client = SteamClient(api_key="test", session=session)

    result = client.users.get_friend_summaries("76561197960434622", limit=1)

    assert result["friend_ids"] == ["76561197960435530"]
    assert result["friends"][0]["personaname"] == "Robin"
    client.close()


def test_users_get_player_bans_summary_and_map_normalize_fields() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "players": [
                        {
                            "SteamId": "76561197960435530",
                            "CommunityBanned": False,
                            "VACBanned": True,
                            "NumberOfVACBans": 1,
                            "DaysSinceLastBan": 25,
                            "NumberOfGameBans": 0,
                            "EconomyBan": "none",
                        }
                    ]
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    summary = client.users.get_player_bans_summary(["76561197960435530"])
    mapping = client.users.get_player_bans_map(["76561197960435530"])

    assert summary[0]["steamid"] == "76561197960435530"
    assert summary[0]["vac_banned"] is True
    assert mapping["76561197960435530"]["days_since_last_ban"] == 25
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


def test_apps_get_app_list_raises_clear_error() -> None:
    client = SteamClient()

    with pytest.raises(SteamResponseError, match="no longer exposes a working public ISteamApps/GetAppList"):
        client.apps.get_app_list()

    client.close()


def test_apps_get_app_details_uses_store_appdetails_endpoint() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "570": {
                    "success": True,
                    "data": {
                        "steam_appid": 570,
                        "name": "Dota 2",
                        "type": "game",
                        "is_free": True,
                        "required_age": 0,
                        "developers": ["Valve"],
                        "publishers": ["Valve"],
                        "genres": [{"description": "Action"}],
                        "categories": [{"description": "Multi-player"}],
                        "short_description": "Example",
                        "header_image": "header.jpg",
                        "website": "https://www.dota2.com",
                        "screenshots": [{"path_full": "shot1.jpg"}],
                        "movies": [{"mp4": {"max": "movie1.mp4"}}],
                        "release_date": {"date": "Jul 9, 2013", "coming_soon": False},
                        "supported_languages": "English",
                    },
                }
            }
        )
    )
    client = SteamClient(session=session)

    result = client.apps.get_app_details(570)

    call = session.calls[0]
    assert call["url"].startswith("https://store.steampowered.com/api/appdetails?")
    assert result["app_id"] == 570
    assert result["name"] == "Dota 2"
    assert result["genres"] == ["Action"]
    assert result["movies"] == ["movie1.mp4"]
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


def test_news_service_summary_normalizes_news_items() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "appnews": {
                    "appid": 570,
                    "newsitems": [
                        {
                            "gid": "1",
                            "title": "Patch Notes",
                            "url": "https://example.com",
                            "author": "Valve",
                            "contents": "<p>Hello <b>world</b></p>",
                            "feedlabel": "Community Announcements",
                            "date": 1234567890,
                            "is_external_url": False,
                        }
                    ],
                }
            }
        )
    )
    client = SteamClient(session=session)

    result = client.news.get_news_summary(570)

    assert result["app_id"] == 570
    assert result["count"] == 1
    assert result["items"][0]["contents"] == "Hello world"
    assert result["items"][0]["feed"] == "Community Announcements"
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


def test_store_service_get_app_list_summary_normalizes_entries() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "apps": [
                        {"appid": 10, "name": "Counter-Strike", "last_modified": 1, "price_change_number": 2}
                    ]
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.store.get_app_list_summary(include_games=True)

    assert result["apps"][0]["app_id"] == 10
    assert result["apps"][0]["name"] == "Counter-Strike"
    client.close()


def test_store_service_search_apps_filters_results() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "apps": [
                        {"appid": 10, "name": "Counter-Strike"},
                        {"appid": 570, "name": "Dota 2"},
                        {"appid": 730, "name": "Counter-Strike 2"},
                    ]
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.store.search_apps("counter", max_results=5)

    assert result["count"] == 2
    assert [item["app_id"] for item in result["matches"]] == [10, 730]
    client.close()


def test_store_service_get_app_list_map_indexes_by_id_and_name() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "apps": [
                        {"appid": 10, "name": "Counter-Strike"},
                        {"appid": 730, "name": "Counter-Strike 2"},
                    ]
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.get_store_app_list_map(include_games=True)

    assert result["count"] == 2
    assert result["apps_by_id"]["10"]["name"] == "Counter-Strike"
    assert result["apps_by_name"]["Counter-Strike 2"]["app_id"] == 730
    client.close()


def test_store_service_find_app_prefers_exact_match() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "apps": [
                        {"appid": 10, "name": "Counter-Strike"},
                        {"appid": 730, "name": "Counter-Strike 2"},
                    ]
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.find_store_app("Counter-Strike 2", include_games=True)

    assert result["matched_exactly"] is True
    assert result["match"]["app_id"] == 730
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


def test_published_files_query_summary_normalizes_valid_items_only() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "total": 2,
                    "next_cursor": "cursor123",
                    "publishedfiledetails": [
                        {
                            "publishedfileid": "123",
                            "result": 1,
                            "title": "Example Mod",
                            "short_description": "Short description",
                            "creator": "76561197960435530",
                            "consumer_appid": 570,
                            "app_name": "Dota 2",
                            "file_type": 0,
                            "visibility": 0,
                            "subscriptions": 12,
                            "favorited": 3,
                            "followers": 1,
                            "views": 50,
                            "lifetime_subscriptions": 20,
                            "lifetime_favorited": 4,
                            "lifetime_followers": 2,
                            "time_created": 100,
                            "time_updated": 200,
                            "preview_url": "https://example.com/preview.jpg",
                            "previews": [{"url": "https://example.com/p1.jpg"}],
                            "tags": [{"tag": "Other", "display_name": "Other"}],
                            "num_children": 0,
                            "children": [],
                            "can_subscribe": True,
                            "can_be_deleted": False,
                            "banned": False,
                        },
                        {
                            "publishedfileid": "999",
                            "result": 9,
                        },
                    ],
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.published_files.query_files_summary(query_type=0, cursor="*", app_id=570)

    assert result["total"] == 2
    assert result["next_cursor"] == "cursor123"
    assert result["item_ids"] == ["123"]
    assert result["items"][0]["title"] == "Example Mod"
    assert result["items"][0]["workshop_url"] == "https://steamcommunity.com/sharedfiles/filedetails/?id=123"
    client.close()


def test_published_files_query_all_files_summary_paginates_with_cursor() -> None:
    session = SequenceSession(
        [
            DummyResponse(
                json_data={
                    "response": {
                        "total": 3,
                        "next_cursor": "cursor123",
                        "publishedfiledetails": [
                            {
                                "publishedfileid": "123",
                                "result": 1,
                                "title": "One",
                                "consumer_appid": 570,
                            },
                            {
                                "publishedfileid": "456",
                                "result": 1,
                                "title": "Two",
                                "consumer_appid": 570,
                            },
                        ],
                    }
                }
            ),
            DummyResponse(
                json_data={
                    "response": {
                        "total": 3,
                        "next_cursor": "cursor456",
                        "publishedfiledetails": [
                            {
                                "publishedfileid": "456",
                                "result": 1,
                                "title": "Two",
                                "consumer_appid": 570,
                            },
                            {
                                "publishedfileid": "789",
                                "result": 1,
                                "title": "Three",
                                "consumer_appid": 570,
                            },
                        ],
                    }
                }
            ),
        ]
    )
    client = SteamClient(api_key="test", session=session)

    result = client.published_files.query_all_files_summary(query_type=0, app_id=570, cursor="*", max_pages=2)

    assert result["total"] == 3
    assert result["pages_fetched"] == 2
    assert result["item_ids"] == ["123", "456", "789"]
    assert result["items"][2]["title"] == "Three"
    assert session.calls[1]["params"]["cursor"] == "cursor123"
    client.close()


def test_client_query_all_published_files_uses_summary_helper() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "total": 1,
                    "next_cursor": "",
                    "publishedfiledetails": [
                        {
                            "publishedfileid": "123",
                            "result": 1,
                            "title": "One",
                            "consumer_appid": 570,
                        }
                    ],
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.query_all_published_files(query_type=0, app_id=570, cursor="*", max_pages=1)

    assert result["item_ids"] == ["123"]
    assert result["pages_fetched"] == 1
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


def test_remote_storage_get_published_file_detail_normalizes_result() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "publishedfiledetails": [
                        {
                            "publishedfileid": "123",
                            "result": 1,
                            "title": "Example Mod",
                            "short_description": "Short description",
                            "creator": "76561197960435530",
                            "consumer_appid": 570,
                            "app_name": "Dota 2",
                            "file_type": 0,
                            "visibility": 0,
                            "subscriptions": 12,
                            "favorited": 3,
                            "followers": 1,
                            "views": 50,
                            "lifetime_subscriptions": 20,
                            "lifetime_favorited": 4,
                            "lifetime_followers": 2,
                            "time_created": 100,
                            "time_updated": 200,
                            "preview_url": "https://example.com/preview.jpg",
                            "previews": [{"url": "https://example.com/p1.jpg"}],
                            "tags": [{"tag": "Other", "display_name": "Other"}],
                            "num_children": 0,
                            "children": [],
                            "can_subscribe": True,
                            "can_be_deleted": False,
                            "banned": False,
                        }
                    ]
                }
            }
        )
    )
    client = SteamClient(session=session)

    result = client.remote_storage.get_published_file_detail("123")

    assert result["published_file_id"] == "123"
    assert result["title"] == "Example Mod"
    assert result["preview_urls"] == ["https://example.com/p1.jpg"]
    assert result["tags"] == ["Other"]
    client.close()


def test_remote_storage_get_published_file_detail_accepts_workshop_url() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "publishedfiledetails": [
                        {"publishedfileid": "3210489689", "result": 1, "title": "Example Workshop Item"}
                    ]
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.get_published_file_detail(
        "https://steamcommunity.com/sharedfiles/filedetails/?id=3210489689"
    )

    assert result["published_file_id"] == "3210489689"
    assert session.calls[0]["data"]["publishedfileids[0]"] == "3210489689"
    client.close()


def test_client_get_published_file_detail_by_url_delegates() -> None:
    client = SteamClient()

    original_get_published_file_detail = client.remote_storage.get_published_file_detail
    client.remote_storage.get_published_file_detail = lambda value: {"published_file_id": normalize_published_file_id(value)}

    result = client.get_published_file_detail_by_url(
        "https://steamcommunity.com/sharedfiles/filedetails/?id=3210489689"
    )

    assert result["published_file_id"] == "3210489689"
    client.remote_storage.get_published_file_detail = original_get_published_file_detail
    client.close()


def test_remote_storage_get_published_file_details_summary_normalizes_and_maps_items() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "publishedfiledetails": [
                        {
                            "publishedfileid": "123",
                            "result": 1,
                            "title": "First Item",
                            "consumer_appid": 570,
                            "subscriptions": 12,
                        },
                        {
                            "publishedfileid": "456",
                            "result": 9,
                            "title": "Invalid Item",
                        },
                    ]
                }
            }
        )
    )
    client = SteamClient(session=session)

    result = client.get_published_file_details(["123", "456"])

    assert result["item_ids"] == ["123"]
    assert result["items"][0]["title"] == "First Item"
    assert result["items_by_id"]["123"]["subscriptions"] == 12
    client.close()


def test_remote_storage_get_published_file_detail_raises_for_invalid_result() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "publishedfiledetails": [
                        {
                            "publishedfileid": "123",
                            "result": 9,
                        }
                    ]
                }
            }
        )
    )
    client = SteamClient(session=session)

    with pytest.raises(SteamNotFoundError):
        client.remote_storage.get_published_file_detail("123")

    client.close()


def test_remote_storage_get_collection_detail_normalizes_children() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "collectiondetails": [
                        {
                            "publishedfileid": "2682416130",
                            "result": 1,
                            "childcount": 2,
                            "children": [
                                {"publishedfileid": "111"},
                                {"publishedfileid": "222"},
                            ],
                        }
                    ]
                }
            }
        )
    )
    client = SteamClient(session=session)

    result = client.get_collection_detail("2682416130")

    assert result["published_file_id"] == "2682416130"
    assert result["child_count"] == 2
    assert result["child_ids"] == ["111", "222"]
    client.close()


def test_client_get_collection_details_returns_normalized_bulk_summary() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "collectiondetails": [
                        {
                            "publishedfileid": "2682416130",
                            "result": 1,
                            "childcount": 2,
                            "children": [
                                {"publishedfileid": "111"},
                                {"publishedfileid": "222"},
                            ],
                        }
                    ]
                }
            }
        )
    )
    client = SteamClient(session=session)

    result = client.get_collection_details(["2682416130"])

    assert result["collection_ids"] == ["2682416130"]
    assert result["collections"][0]["child_ids"] == ["111", "222"]
    client.close()


def test_remote_storage_get_collection_details_map_indexes_collections() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "collectiondetails": [
                        {
                            "publishedfileid": "2682416130",
                            "result": 1,
                            "childcount": 2,
                            "children": [{"publishedfileid": "111"}],
                        }
                    ]
                }
            }
        )
    )
    client = SteamClient(session=session)

    result = client.get_collection_details_map(["2682416130"])

    assert result["2682416130"]["child_count"] == 2
    client.close()


def test_remote_storage_get_collection_child_details_expands_children() -> None:
    session = SequenceSession(
        [
            DummyResponse(
                json_data={
                    "response": {
                        "collectiondetails": [
                            {
                                "publishedfileid": "2682416130",
                                "result": 1,
                                "childcount": 1,
                                "children": [{"publishedfileid": "111"}],
                            }
                        ]
                    }
                }
            ),
            DummyResponse(
                json_data={
                    "response": {
                        "publishedfiledetails": [
                            {
                                "publishedfileid": "111",
                                "result": 1,
                                "title": "Child Item",
                                "consumer_appid": 570,
                                "subscriptions": 10,
                            }
                        ]
                    }
                }
            ),
        ]
    )
    client = SteamClient(session=session)

    result = client.get_collection_child_details("2682416130")

    assert result["collection"]["published_file_id"] == "2682416130"
    assert result["child_ids"] == ["111"]
    assert result["children"][0]["title"] == "Child Item"
    client.close()


def test_remote_storage_get_collection_detail_accepts_workshop_url() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "collectiondetails": [
                        {
                            "publishedfileid": "3210489689",
                            "result": 1,
                            "childcount": 1,
                            "children": [{"publishedfileid": "111"}],
                        }
                    ]
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.get_collection_detail(
        "https://steamcommunity.com/sharedfiles/filedetails/?id=3210489689"
    )

    assert result["published_file_id"] == "3210489689"
    assert session.calls[0]["data"]["publishedfileids[0]"] == "3210489689"
    client.close()


def test_client_collection_url_helpers_delegate() -> None:
    client = SteamClient()

    original_get_collection_detail = client.remote_storage.get_collection_detail
    original_get_collection_child_details = client.remote_storage.get_collection_child_details
    original_get_collection_child_map = client.remote_storage.get_collection_child_map
    original_find_collection_child = client.remote_storage.find_collection_child

    client.remote_storage.get_collection_detail = lambda value: {"published_file_id": normalize_published_file_id(value)}
    client.remote_storage.get_collection_child_details = lambda value: {"collection": {"published_file_id": normalize_published_file_id(value)}}
    client.remote_storage.get_collection_child_map = lambda value: {"collection": {"published_file_id": normalize_published_file_id(value)}}
    client.remote_storage.find_collection_child = lambda value, **kwargs: {
        "collection": {"published_file_id": normalize_published_file_id(value)},
        "kwargs": kwargs,
    }

    workshop_url = "https://steamcommunity.com/sharedfiles/filedetails/?id=3210489689"

    assert client.get_collection_detail_by_url(workshop_url)["published_file_id"] == "3210489689"
    assert client.get_collection_child_details_by_url(workshop_url)["collection"]["published_file_id"] == "3210489689"
    assert client.get_collection_child_map_by_url(workshop_url)["collection"]["published_file_id"] == "3210489689"
    assert client.find_collection_child_by_url(workshop_url, title="Example")["collection"]["published_file_id"] == "3210489689"

    client.remote_storage.get_collection_detail = original_get_collection_detail
    client.remote_storage.get_collection_child_details = original_get_collection_child_details
    client.remote_storage.get_collection_child_map = original_get_collection_child_map
    client.remote_storage.find_collection_child = original_find_collection_child
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


def test_econ_get_trade_history_summary_normalizes_trades() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "trades": [
                        {
                            "tradeid": "123",
                            "steamid_other": "76561197960435530",
                            "assets_given": [{"appid": 730, "assetid": "10", "amount": "1"}],
                            "assets_received": [{"appid": 730, "assetid": "11", "amount": "2"}],
                        }
                    ],
                    "total_trades": 1,
                    "more": False,
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.econ.get_trade_history_summary(max_trades=10)

    assert result["trade_count"] == 1
    assert result["trades"][0]["trade_id"] == "123"
    assert result["trades"][0]["assets_given_count"] == 1
    assert result["trades"][0]["assets_received_count"] == 1
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


def test_econ_get_trade_offer_totals_normalizes_summary_counts() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "pending_received_count": 2,
                    "new_received_count": 1,
                    "historical_received_count": 5,
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.econ.get_trade_offer_totals()

    assert result["pending_received_count"] == 2
    assert result["new_received_count"] == 1
    assert result["historical_received_count"] == 5
    client.close()


def test_econ_get_trade_offers_summary_view_normalizes_offers() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "trade_offers_sent": [
                        {
                            "tradeofferid": "1",
                            "accountid_other": 2,
                            "items_to_give": [{"appid": 730, "assetid": "10", "amount": "1"}],
                            "items_to_receive": [{"appid": 730, "assetid": "11", "amount": "2"}],
                        }
                    ],
                    "trade_offers_received": [],
                    "descriptions": [{"appid": 730}],
                    "next_cursor": 0,
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.econ.get_trade_offers_summary_view()

    assert result["sent_count"] == 1
    assert result["received_count"] == 0
    assert result["description_count"] == 1
    assert result["sent"][0]["items_to_give_count"] == 1
    assert result["sent"][0]["items_to_receive_count"] == 1
    client.close()


def test_client_trade_helpers_delegate_to_econ_service() -> None:
    client = SteamClient(api_key="test")

    original_get_trade_offers_summary = client.econ.get_trade_offers_summary
    original_get_trade_offers = client.econ.get_trade_offers
    original_get_trade_history = client.econ.get_trade_history
    original_get_trade_offer_totals = client.econ.get_trade_offer_totals
    original_get_trade_offers_summary_view = client.econ.get_trade_offers_summary_view
    original_get_trade_history_summary = client.econ.get_trade_history_summary
    original_get_trade_offer_summary = client.econ.get_trade_offer_summary

    client.econ.get_trade_offers_summary = lambda: {"kind": "summary"}
    client.econ.get_trade_offers = lambda **kwargs: {"kind": "offers", "kwargs": kwargs}
    client.econ.get_trade_history = lambda **kwargs: {"kind": "history", "kwargs": kwargs}
    client.econ.get_trade_offer_totals = lambda **kwargs: {"kind": "totals", "kwargs": kwargs}
    client.econ.get_trade_offers_summary_view = lambda **kwargs: {"kind": "summary_view", "kwargs": kwargs}
    client.econ.get_trade_history_summary = lambda **kwargs: {"kind": "history_summary", "kwargs": kwargs}
    client.econ.get_trade_offer_summary = lambda trade_offer_id, **kwargs: {
        "kind": "offer_summary",
        "trade_offer_id": trade_offer_id,
        "kwargs": kwargs,
    }

    assert client.get_trade_offers_summary() == {"kind": "summary"}
    assert client.get_trade_offers(get_received_offers=False)["kwargs"]["get_received_offers"] is False
    assert client.get_trade_history(max_trades=5)["kwargs"]["max_trades"] == 5
    assert client.get_trade_offer_totals(time_last_visit=12)["kwargs"]["time_last_visit"] == 12
    assert client.get_trade_offers_summary_view(active_only=False)["kwargs"]["active_only"] is False
    assert client.get_trade_history_summary(max_trades=2)["kwargs"]["max_trades"] == 2
    assert client.get_trade_offer_summary("42")["trade_offer_id"] == "42"

    client.econ.get_trade_offers_summary = original_get_trade_offers_summary
    client.econ.get_trade_offers = original_get_trade_offers
    client.econ.get_trade_history = original_get_trade_history
    client.econ.get_trade_offer_totals = original_get_trade_offer_totals
    client.econ.get_trade_offers_summary_view = original_get_trade_offers_summary_view
    client.econ.get_trade_history_summary = original_get_trade_history_summary
    client.econ.get_trade_offer_summary = original_get_trade_offer_summary
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


def test_players_get_owned_games_summary_normalizes_games() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "game_count": 1,
                    "games": [
                        {
                            "appid": 570,
                            "name": "Dota 2",
                            "playtime_forever": 1234,
                            "img_icon_url": "icon",
                        }
                    ],
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.players.get_owned_games_summary("76561197960434622")

    assert result["game_count"] == 1
    assert result["games"][0]["app_id"] == 570
    assert result["games_map"][570]["name"] == "Dota 2"
    client.close()


def test_players_get_recently_played_games_summary_normalizes_games() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "total_count": 1,
                    "games": [
                        {
                            "appid": 730,
                            "name": "Counter-Strike 2",
                            "playtime_2weeks": 120,
                        }
                    ],
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.players.get_recently_played_games_summary("76561197960434622")

    assert result["total_count"] == 1
    assert result["games"][0]["app_id"] == 730
    assert result["games_map"][730]["playtime_2weeks"] == 120
    client.close()


def test_players_find_owned_game_filters_by_app_id() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "game_count": 2,
                    "games": [
                        {"appid": 570, "name": "Dota 2"},
                        {"appid": 730, "name": "Counter-Strike 2"},
                    ],
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.find_owned_game_for_user("76561197960434622", app_id=730, include_appinfo=True)

    assert result["count"] == 1
    assert result["games"][0]["name"] == "Counter-Strike 2"
    client.close()


def test_players_find_recently_played_game_filters_by_name() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "total_count": 2,
                    "games": [
                        {"appid": 570, "name": "Dota 2"},
                        {"appid": 730, "name": "Counter-Strike 2"},
                    ],
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.find_recently_played_game_for_user("76561197960434622", name_query="counter")

    assert result["count"] == 1
    assert result["games"][0]["app_id"] == 730
    client.close()


def test_players_get_badges_summary_normalizes_badges() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "player_level": 10,
                    "player_xp": 1000,
                    "badges": [
                        {
                            "badgeid": 1,
                            "level": 2,
                            "appid": 570,
                            "xp": 200,
                        }
                    ],
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.get_badges_summary_for_user("76561197960434622")

    assert result["player_level"] == 10
    assert result["badge_count"] == 1
    assert result["badges"][0]["badge_id"] == 1
    assert result["badges"][0]["appid"] == 570
    client.close()


def test_players_get_community_badge_progress_summary_counts_completed() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "quests": [
                        {"questid": 1, "completed": True},
                        {"questid": 2, "completed": False},
                    ]
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.get_community_badge_progress_summary_for_user("76561197960434622", 1)

    assert result["quest_count"] == 2
    assert result["completed_count"] == 1
    assert result["quests"][0]["quest_id"] == 1
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
    assert result["items"][0]["normalized_description"]["market_hash_name"] == "Example Item"
    client.close()


def test_inventory_items_summary_normalizes_items_and_maps_asset_ids() -> None:
    payload = {
        "assets": [{"assetid": "1", "classid": "10", "instanceid": "0", "amount": "1", "appid": 730, "contextid": "2"}],
        "descriptions": [
            {
                "classid": "10",
                "instanceid": "0",
                "market_hash_name": "Example Item",
                "name": "Example Item",
                "tradable": 1,
                "marketable": 1,
                "type": "Rifle",
            }
        ],
        "total_inventory_count": 1,
        "more_items": False,
    }
    session = RecordingSession(DummyResponse(json_data=payload))
    client = SteamClient(session=session)

    result = client.inventory.get_inventory_items_summary("76561197960435530", 730, 2)

    assert result["items"][0]["asset_id"] == "1"
    assert result["items"][0]["market_hash_name"] == "Example Item"
    assert result["items_by_asset_id"]["1"]["type"] == "Rifle"
    client.close()


def test_inventory_get_item_by_asset_id_returns_matching_item() -> None:
    payload = {
        "assets": [{"assetid": "1", "classid": "10", "instanceid": "0", "amount": "1", "appid": 730, "contextid": "2"}],
        "descriptions": [{"classid": "10", "instanceid": "0", "market_hash_name": "Example Item", "name": "Example Item"}],
        "total_inventory_count": 1,
        "more_items": False,
    }
    session = RecordingSession(DummyResponse(json_data=payload))
    client = SteamClient(session=session)

    result = client.inventory.get_inventory_item_by_asset_id("76561197960435530", 730, 2, "1")

    assert result["asset_id"] == "1"
    assert result["market_hash_name"] == "Example Item"
    client.close()


def test_inventory_get_item_by_asset_id_raises_not_found_when_missing() -> None:
    payload = {
        "assets": [{"assetid": "1", "classid": "10", "instanceid": "0", "amount": "1", "appid": 730, "contextid": "2"}],
        "descriptions": [{"classid": "10", "instanceid": "0", "market_hash_name": "Example Item", "name": "Example Item"}],
        "total_inventory_count": 1,
        "more_items": False,
    }
    session = RecordingSession(DummyResponse(json_data=payload))
    client = SteamClient(session=session)

    with pytest.raises(SteamNotFoundError):
        client.inventory.get_inventory_item_by_asset_id("76561197960435530", 730, 2, "2")

    client.close()


def test_inventory_item_counts_aggregates_by_market_hash_name() -> None:
    payload = {
        "assets": [
            {"assetid": "1", "classid": "10", "instanceid": "0", "amount": "2", "appid": 730, "contextid": "2"},
            {"assetid": "2", "classid": "10", "instanceid": "0", "amount": "1", "appid": 730, "contextid": "2"},
            {"assetid": "3", "classid": "11", "instanceid": "0", "amount": "1", "appid": 730, "contextid": "2"},
        ],
        "descriptions": [
            {"classid": "10", "instanceid": "0", "market_hash_name": "AK-47 | Example", "name": "AK-47 | Example", "tradable": 1, "marketable": 1},
            {"classid": "11", "instanceid": "0", "market_hash_name": "M4A4 | Example", "name": "M4A4 | Example", "tradable": 0, "marketable": 1},
        ],
        "total_inventory_count": 3,
        "more_items": False,
    }
    session = RecordingSession(DummyResponse(json_data=payload))
    client = SteamClient(session=session)

    result = client.get_inventory_item_counts_for_user("76561197960435530", 730, 2)

    assert result["unique_item_count"] == 2
    assert result["items"][0]["market_hash_name"] == "AK-47 | Example"
    assert result["items"][0]["count"] == 3
    assert result["items_map"]["AK-47 | Example"]["asset_count"] == 2
    client.close()


def test_inventory_find_items_filters_by_name_and_flags() -> None:
    payload = {
        "assets": [
            {"assetid": "1", "classid": "10", "instanceid": "0", "amount": "1", "appid": 730, "contextid": "2"},
            {"assetid": "2", "classid": "11", "instanceid": "0", "amount": "1", "appid": 730, "contextid": "2"},
        ],
        "descriptions": [
            {"classid": "10", "instanceid": "0", "market_hash_name": "AK-47 | Example", "name": "AK-47 | Example", "tradable": 1, "marketable": 1},
            {"classid": "11", "instanceid": "0", "market_hash_name": "M4A4 | Example", "name": "M4A4 | Example", "tradable": 0, "marketable": 1},
        ],
        "total_inventory_count": 2,
        "more_items": False,
    }
    session = RecordingSession(DummyResponse(json_data=payload))
    client = SteamClient(session=session)

    result = client.find_inventory_items_for_user(
        "76561197960435530",
        730,
        2,
        name_query="AK-47",
        tradable=True,
    )

    assert result["count"] == 1
    assert result["items"][0]["market_hash_name"] == "AK-47 | Example"
    client.close()


def test_inventory_full_items_summary_normalizes_paginated_inventory() -> None:
    session = SequenceSession(
        [
            DummyResponse(
                json_data={
                    "assets": [{"assetid": "1", "classid": "10", "instanceid": "0", "appid": 730, "contextid": "2"}],
                    "descriptions": [{"classid": "10", "instanceid": "0", "market_hash_name": "One", "name": "One", "tradable": 1}],
                    "total_inventory_count": 2,
                    "more_items": True,
                    "last_assetid": "1",
                }
            ),
            DummyResponse(
                json_data={
                    "assets": [{"assetid": "2", "classid": "11", "instanceid": "0", "appid": 730, "contextid": "2"}],
                    "descriptions": [{"classid": "11", "instanceid": "0", "market_hash_name": "Two", "name": "Two", "tradable": 0}],
                    "total_inventory_count": 2,
                    "more_items": False,
                }
            ),
        ]
    )
    client = SteamClient(session=session)

    result = client.get_full_inventory_items_summary_for_user("76561197960435530", 730, 2, max_pages=2)

    assert result["pages_fetched"] == 2
    assert len(result["items"]) == 2
    assert result["items_by_asset_id"]["2"]["market_hash_name"] == "Two"
    client.close()


def test_inventory_get_full_item_by_asset_id_returns_matching_item() -> None:
    session = SequenceSession(
        [
            DummyResponse(
                json_data={
                    "assets": [{"assetid": "1", "classid": "10", "instanceid": "0", "appid": 730, "contextid": "2"}],
                    "descriptions": [{"classid": "10", "instanceid": "0", "market_hash_name": "One", "name": "One"}],
                    "total_inventory_count": 2,
                    "more_items": True,
                    "last_assetid": "1",
                }
            ),
            DummyResponse(
                json_data={
                    "assets": [{"assetid": "2", "classid": "11", "instanceid": "0", "appid": 730, "contextid": "2"}],
                    "descriptions": [{"classid": "11", "instanceid": "0", "market_hash_name": "Two", "name": "Two"}],
                    "total_inventory_count": 2,
                    "more_items": False,
                }
            ),
        ]
    )
    client = SteamClient(session=session)

    result = client.inventory.get_full_inventory_item_by_asset_id("76561197960435530", 730, 2, "2", max_pages=2)

    assert result["asset_id"] == "2"
    assert result["market_hash_name"] == "Two"
    client.close()


def test_full_inventory_item_counts_aggregate_across_pages() -> None:
    session = SequenceSession(
        [
            DummyResponse(
                json_data={
                    "assets": [{"assetid": "1", "classid": "10", "instanceid": "0", "amount": "1", "appid": 730, "contextid": "2"}],
                    "descriptions": [{"classid": "10", "instanceid": "0", "market_hash_name": "AK-47 | One", "name": "AK-47 | One", "tradable": 1, "marketable": 1}],
                    "total_inventory_count": 3,
                    "more_items": True,
                    "last_assetid": "1",
                }
            ),
            DummyResponse(
                json_data={
                    "assets": [
                        {"assetid": "2", "classid": "10", "instanceid": "0", "amount": "2", "appid": 730, "contextid": "2"},
                        {"assetid": "3", "classid": "11", "instanceid": "0", "amount": "1", "appid": 730, "contextid": "2"},
                    ],
                    "descriptions": [
                        {"classid": "10", "instanceid": "0", "market_hash_name": "AK-47 | One", "name": "AK-47 | One", "tradable": 1, "marketable": 1},
                        {"classid": "11", "instanceid": "0", "market_hash_name": "M4A4 | Two", "name": "M4A4 | Two", "tradable": 0, "marketable": 1},
                    ],
                    "total_inventory_count": 3,
                    "more_items": False,
                }
            ),
        ]
    )
    client = SteamClient(session=session)

    result = client.get_full_inventory_item_counts_for_user("76561197960435530", 730, 2, max_pages=2)

    assert result["pages_fetched"] == 2
    assert result["unique_item_count"] == 2
    assert result["items_map"]["AK-47 | One"]["count"] == 3
    client.close()


def test_inventory_find_full_items_filters_across_pages() -> None:
    session = SequenceSession(
        [
            DummyResponse(
                json_data={
                    "assets": [{"assetid": "1", "classid": "10", "instanceid": "0", "appid": 730, "contextid": "2"}],
                    "descriptions": [{"classid": "10", "instanceid": "0", "market_hash_name": "AK-47 | One", "name": "AK-47 | One", "tradable": 1, "marketable": 1}],
                    "total_inventory_count": 2,
                    "more_items": True,
                    "last_assetid": "1",
                }
            ),
            DummyResponse(
                json_data={
                    "assets": [{"assetid": "2", "classid": "11", "instanceid": "0", "appid": 730, "contextid": "2"}],
                    "descriptions": [{"classid": "11", "instanceid": "0", "market_hash_name": "M4A4 | Two", "name": "M4A4 | Two", "tradable": 0, "marketable": 1}],
                    "total_inventory_count": 2,
                    "more_items": False,
                }
            ),
        ]
    )
    client = SteamClient(session=session)

    result = client.find_full_inventory_items_for_user(
        "76561197960435530",
        730,
        2,
        max_pages=2,
        name_query="AK-47",
        tradable=True,
    )

    assert result["pages_fetched"] == 2
    assert result["count"] == 1
    assert result["items"][0]["market_hash_name"] == "AK-47 | One"
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


def test_market_search_summary_normalizes_items() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "success": True,
                "start": 0,
                "pagesize": 10,
                "total_count": 123,
                "results": [
                    {
                        "name": "AK-47 | Example",
                        "hash_name": "AK-47 | Example",
                        "sell_listings": 5,
                        "sell_price": 1234,
                        "sell_price_text": "$12.34",
                        "sale_price_text": "$11.11",
                        "app_name": "Counter-Strike 2",
                        "app_icon": "icon.png",
                        "asset_description": {
                            "appid": 730,
                            "market_hash_name": "AK-47 | Example",
                            "market_name": "AK-47 | Example",
                            "commodity": 0,
                            "tradable": 1,
                            "type": "Rifle",
                            "name_color": "D2D2D2",
                            "icon_url": "asset_icon.png",
                            "background_color": "",
                        },
                    }
                ],
            }
        )
    )
    client = SteamClient(session=session)

    result = client.market.search_items_summary(query="AK-47", app_id=730, count=5)

    assert result["total_count"] == 123
    assert result["items"][0]["hash_name"] == "AK-47 | Example"
    assert result["items"][0]["market_url"] == "https://steamcommunity.com/market/listings/730/AK-47%20%7C%20Example"
    assert result["items"][0]["sell_price_text"] == "$12.34"
    client.close()


def test_market_search_all_items_paginates_results() -> None:
    session = SequenceSession(
        [
            DummyResponse(
                json_data={
                    "success": True,
                    "start": 0,
                    "pagesize": 2,
                    "total_count": 4,
                    "results": [
                        {
                            "name": "One",
                            "hash_name": "One",
                            "asset_description": {"appid": 730, "market_hash_name": "One"},
                        },
                        {
                            "name": "Two",
                            "hash_name": "Two",
                            "asset_description": {"appid": 730, "market_hash_name": "Two"},
                        },
                    ],
                }
            ),
            DummyResponse(
                json_data={
                    "success": True,
                    "start": 2,
                    "pagesize": 2,
                    "total_count": 4,
                    "results": [
                        {
                            "name": "Three",
                            "hash_name": "Three",
                            "asset_description": {"appid": 730, "market_hash_name": "Three"},
                        },
                        {
                            "name": "Four",
                            "hash_name": "Four",
                            "asset_description": {"appid": 730, "market_hash_name": "Four"},
                        },
                    ],
                }
            ),
        ]
    )
    client = SteamClient(session=session)

    result = client.market.search_all_items(query="AK", app_id=730, count=2)

    assert result["pages_fetched"] == 2
    assert len(result["items"]) == 4
    assert session.calls[1]["params"]["start"] == 2
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


def test_market_get_item_listings_summary_normalizes_assets_and_cheapest_listing() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "success": 1,
                "total_count": 2,
                "start": 0,
                "pagesize": 2,
                "assets": {
                    "730": {
                        "2": {
                            "1001": {
                                "appid": 730,
                                "contextid": "2",
                                "id": "1001",
                                "classid": "10",
                                "instanceid": "0",
                                "amount": "1",
                                "market_hash_name": "AK-47 | Example",
                            }
                        }
                    }
                },
                "listinginfo": {
                    "1": {
                        "price": 123,
                        "fee": 12,
                        "converted_price": 123,
                        "converted_fee": 12,
                        "asset": {"id": "1001"},
                    },
                    "2": {
                        "price": 150,
                        "fee": 15,
                        "converted_price": 150,
                        "converted_fee": 15,
                        "asset": {"id": "1001"},
                    },
                },
            }
        )
    )
    client = SteamClient(session=session)

    result = client.get_market_item_listings_summary(730, "AK-47 | Example", count=2)

    assert result["total_count"] == 2
    assert len(result["listings"]) == 2
    assert result["cheapest_listing"]["listing_id"] == "1"
    assert result["assets"]["1001"]["market_hash_name"] == "AK-47 | Example"
    client.close()


def test_market_get_item_listings_map_indexes_listings_by_id() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "success": True,
                "total_count": 2,
                "listinginfo": {
                    "1": {"listingid": "1", "price": 450, "fee": 50, "asset": {"id": "1001"}},
                    "2": {"listingid": "2", "price": 500, "fee": 50, "asset": {"id": "1002"}},
                },
                "assets": {
                    "730": {
                        "2": {
                            "1001": {"id": "1001", "market_hash_name": "AK-47 | Example"},
                            "1002": {"id": "1002", "market_hash_name": "AK-47 | Example"},
                        }
                    }
                },
            }
        )
    )
    client = SteamClient(session=session)

    result = client.get_market_item_listings_map(730, "AK-47 | Example", count=2)

    assert result["listings_by_id"]["1"]["asset_id"] == "1001"
    assert result["listings_by_id"]["2"]["asset_id"] == "1002"
    client.close()


def test_market_get_all_item_listings_summary_paginates_and_deduplicates() -> None:
    session = SequenceSession(
        [
            DummyResponse(
                json_data={
                    "success": 1,
                    "total_count": 3,
                    "start": 0,
                    "pagesize": 2,
                    "assets": {"730": {"2": {"1001": {"id": "1001", "market_hash_name": "One"}}}},
                    "listinginfo": {
                        "1": {"price": 100, "converted_price": 100, "asset": {"id": "1001"}},
                        "2": {"price": 110, "converted_price": 110, "asset": {"id": "1001"}},
                    },
                }
            ),
            DummyResponse(
                json_data={
                    "success": 1,
                    "total_count": 3,
                    "start": 2,
                    "pagesize": 1,
                    "assets": {"730": {"2": {"1002": {"id": "1002", "market_hash_name": "Two"}}}},
                    "listinginfo": {
                        "3": {"price": 120, "converted_price": 120, "asset": {"id": "1002"}},
                    },
                }
            ),
        ]
    )
    client = SteamClient(session=session)

    result = client.get_all_market_item_listings_summary(730, "AK-47 | Example", count=2, max_pages=2)

    assert result["pages_fetched"] == 2
    assert len(result["listings"]) == 3
    assert result["assets"]["1002"]["market_hash_name"] == "Two"
    client.close()


def test_market_get_all_item_listings_map_indexes_paginated_listings_by_id() -> None:
    session = SequenceSession(
        [
            DummyResponse(
                json_data={
                    "success": True,
                    "total_count": 2,
                    "start": 0,
                    "pagesize": 1,
                    "listinginfo": {
                        "1": {"listingid": "1", "price": 450, "fee": 50, "asset": {"id": "1001"}}
                    },
                    "assets": {"730": {"2": {"1001": {"id": "1001", "market_hash_name": "One"}}}},
                }
            ),
            DummyResponse(
                json_data={
                    "success": True,
                    "total_count": 2,
                    "start": 1,
                    "pagesize": 1,
                    "listinginfo": {
                        "2": {"listingid": "2", "price": 500, "fee": 50, "asset": {"id": "1002"}}
                    },
                    "assets": {"730": {"2": {"1002": {"id": "1002", "market_hash_name": "Two"}}}},
                }
            ),
        ]
    )
    client = SteamClient(session=session)

    result = client.get_all_market_item_listings_map(730, "AK-47 | Example", count=1, max_pages=2)

    assert set(result["listings_by_id"]) == {"1", "2"}
    client.close()


def test_market_find_item_listings_filters_by_max_price() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "success": 1,
                "total_count": 2,
                "start": 0,
                "pagesize": 2,
                "assets": {"730": {"2": {"1001": {"id": "1001"}, "1002": {"id": "1002"}}}},
                "listinginfo": {
                    "1": {"price": 100, "converted_price": 100, "asset": {"id": "1001"}},
                    "2": {"price": 600, "converted_price": 600, "asset": {"id": "1002"}},
                },
            }
        )
    )
    client = SteamClient(session=session)

    result = client.find_market_item_listings(730, "AK-47 | Example", max_price=500)

    assert result["count"] == 1
    assert result["listings"][0]["listing_id"] == "1"
    client.close()


def test_market_get_listing_by_id_returns_matching_listing() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "success": True,
                "total_count": 2,
                "listinginfo": {
                    "1": {"listingid": "1", "price": 450, "fee": 50, "asset": {"id": "1001"}},
                    "2": {"listingid": "2", "price": 500, "fee": 50, "asset": {"id": "1002"}},
                },
                "assets": {
                    "730": {
                        "2": {
                            "1001": {"id": "1001", "market_hash_name": "AK-47 | Example"},
                            "1002": {"id": "1002", "market_hash_name": "AK-47 | Example"},
                        }
                    }
                },
            }
        )
    )
    client = SteamClient(session=session)

    result = client.get_market_listing_by_id(730, "AK-47 | Example", "2")

    assert result["listing_id"] == "2"
    assert result["asset_id"] == "1002"
    client.close()


def test_market_get_all_listing_by_id_raises_not_found_when_missing() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "success": True,
                "total_count": 1,
                "listinginfo": {
                    "1": {"listingid": "1", "price": 450, "fee": 50, "asset": {"id": "1001"}}
                },
                "assets": {"730": {"2": {"1001": {"id": "1001", "market_hash_name": "AK-47 | Example"}}}},
            }
        )
    )
    client = SteamClient(session=session)

    with pytest.raises(SteamNotFoundError):
        client.market.get_all_listing_by_id(730, "AK-47 | Example", "999", max_pages=1)

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
    assert session.calls[1]["params"]["two_factor"] == 0
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


def test_market_find_search_item_prefers_exact_market_hash_name() -> None:
    client = SteamClient()

    original_search_all_items = client.market.search_all_items
    client.market.search_all_items = lambda **kwargs: {
        "items": [
            {"market_hash_name": "AK-47 | Other", "name": "AK-47 | Other"},
            {"market_hash_name": "AK-47 | Redline (Field-Tested)", "name": "AK-47 | Redline (Field-Tested)"},
        ]
    }

    result = client.find_market_item(
        "AK-47",
        app_id=730,
        market_hash_name="AK-47 | Redline (Field-Tested)",
    )

    assert result["matched_exactly"] is True
    assert result["match"]["market_hash_name"] == "AK-47 | Redline (Field-Tested)"

    client.market.search_all_items = original_search_all_items
    client.close()


def test_market_price_history_summary_calculates_ranges() -> None:
    client = SteamClient()

    original_get_price_history = client.market.get_price_history
    client.market.get_price_history = lambda app_id, market_hash_name: {
        "price_prefix": "$",
        "price_suffix": "",
        "prices": [
            ["Feb 21 2014 01: +0", 41.405, "198"],
            ["Feb 22 2014 01: +0", 35.08, "225"],
            ["Feb 23 2014 01: +0", 38.5, "210"],
        ],
    }

    result = client.get_market_price_history_summary(730, "AK-47 | Example")

    assert result["point_count"] == 3
    assert result["latest_price"] == 38.5
    assert result["min_price"] == 35.08
    assert result["max_price"] == 41.405

    client.market.get_price_history = original_get_price_history
    client.close()


def test_market_price_snapshot_combines_price_orders_and_listings() -> None:
    client = SteamClient()

    original_get_item_name_id = client.market.get_item_name_id
    original_get_price_overview = client.market.get_price_overview
    original_get_item_orders_summary = client.market.get_item_orders_summary
    original_get_item_listings_summary = client.market.get_item_listings_summary

    client.market.get_item_name_id = lambda app_id, market_hash_name: 7178002
    client.market.get_price_overview = lambda app_id, market_hash_name, **kwargs: {
        "lowest_price": "$1.23",
        "median_price": "$1.25",
        "volume": "12",
    }
    client.market.get_item_orders_summary = lambda **kwargs: {
        "highest_buy_order": "123",
        "lowest_sell_order": "125",
        "buy_order_count": "10",
        "sell_order_count": "20",
    }
    client.market.get_item_listings_summary = lambda app_id, market_hash_name, **kwargs: {
        "total_count": 5,
        "cheapest_listing": {"price": 123, "fee": 10},
    }

    result = client.get_market_price_snapshot(730, "AK-47 | Example")

    assert result["item_name_id"] == 7178002
    assert result["lowest_price_text"] == "$1.23"
    assert result["listing_count"] == 5
    assert result["cheapest_listing_price"] == 123

    client.market.get_item_name_id = original_get_item_name_id
    client.market.get_price_overview = original_get_price_overview
    client.market.get_item_orders_summary = original_get_item_orders_summary
    client.market.get_item_listings_summary = original_get_item_listings_summary
    client.close()


def test_client_market_helpers_accept_listing_url() -> None:
    client = SteamClient()

    original_get_price_overview = client.market.get_price_overview
    original_get_price_history = client.market.get_price_history
    original_get_price_history_summary = client.market.get_price_history_summary
    original_get_market_price_snapshot = client.market.get_market_price_snapshot
    original_get_item_listings_summary = client.market.get_item_listings_summary

    client.market.get_price_overview = lambda app_id, market_hash_name, **kwargs: {
        "appid": app_id,
        "market_hash_name": market_hash_name,
        "lowest_price": "$1.23",
    }
    client.market.get_price_history = lambda app_id, market_hash_name: {
        "appid": app_id,
        "market_hash_name": market_hash_name,
        "prices": [],
    }
    client.market.get_price_history_summary = lambda app_id, market_hash_name: {
        "app_id": app_id,
        "market_hash_name": market_hash_name,
        "point_count": 0,
    }
    client.market.get_market_price_snapshot = lambda app_id, market_hash_name, **kwargs: {
        "app_id": app_id,
        "market_hash_name": market_hash_name,
        "listing_count": 5,
    }
    client.market.get_item_listings_summary = lambda app_id, market_hash_name, **kwargs: {
        "app_id": app_id,
        "market_hash_name": market_hash_name,
        "total_count": 5,
        "listings": [],
    }

    market_url = "https://steamcommunity.com/market/listings/730/AK-47%20%7C%20Example"

    assert client.get_market_price_overview_by_url(market_url)["market_hash_name"] == "AK-47 | Example"
    assert client.get_market_price_history_by_url(market_url)["appid"] == 730
    assert client.get_market_price_history_summary_by_url(market_url)["app_id"] == 730
    assert client.get_market_price_snapshot_by_url(market_url)["listing_count"] == 5
    assert client.get_market_item_listings_summary_by_url(market_url)["total_count"] == 5

    client.market.get_price_overview = original_get_price_overview
    client.market.get_price_history = original_get_price_history
    client.market.get_price_history_summary = original_get_price_history_summary
    client.market.get_market_price_snapshot = original_get_market_price_snapshot
    client.market.get_item_listings_summary = original_get_item_listings_summary
    client.close()


def test_client_more_market_url_helpers_delegate_correctly() -> None:
    client = SteamClient()

    original_get_item_name_id = client.market.get_item_name_id
    original_get_item_orders_histogram = client.market.get_item_orders_histogram
    original_get_item_orders_summary = client.market.get_item_orders_summary
    original_get_item_listings_map = client.market.get_item_listings_map
    original_get_all_item_listings_summary = client.market.get_all_item_listings_summary
    original_get_all_item_listings_map = client.market.get_all_item_listings_map
    original_get_listing_by_id = client.market.get_listing_by_id
    original_get_all_listing_by_id = client.market.get_all_listing_by_id
    original_find_item_listings = client.market.find_item_listings

    client.market.get_item_name_id = lambda app_id, market_hash_name: 7178002
    client.market.get_item_orders_histogram = lambda **kwargs: {"kind": "histogram", "kwargs": kwargs}
    client.market.get_item_orders_summary = lambda **kwargs: {"kind": "summary", "kwargs": kwargs}
    client.market.get_item_listings_map = lambda app_id, market_hash_name, **kwargs: {
        "kind": "listings_map",
        "app_id": app_id,
        "market_hash_name": market_hash_name,
        "kwargs": kwargs,
    }
    client.market.get_all_item_listings_summary = lambda app_id, market_hash_name, **kwargs: {
        "kind": "all_listings",
        "app_id": app_id,
        "market_hash_name": market_hash_name,
        "kwargs": kwargs,
    }
    client.market.get_all_item_listings_map = lambda app_id, market_hash_name, **kwargs: {
        "kind": "all_listings_map",
        "app_id": app_id,
        "market_hash_name": market_hash_name,
        "kwargs": kwargs,
    }
    client.market.get_listing_by_id = lambda app_id, market_hash_name, listing_id, **kwargs: {
        "kind": "listing_by_id",
        "app_id": app_id,
        "market_hash_name": market_hash_name,
        "listing_id": listing_id,
        "kwargs": kwargs,
    }
    client.market.get_all_listing_by_id = lambda app_id, market_hash_name, listing_id, **kwargs: {
        "kind": "all_listing_by_id",
        "app_id": app_id,
        "market_hash_name": market_hash_name,
        "listing_id": listing_id,
        "kwargs": kwargs,
    }
    client.market.find_item_listings = lambda app_id, market_hash_name, **kwargs: {
        "kind": "find_listings",
        "app_id": app_id,
        "market_hash_name": market_hash_name,
        "kwargs": kwargs,
    }

    market_url = "https://steamcommunity.com/market/listings/730/AK-47%20%7C%20Example"

    assert client.get_market_item_name_id_by_url(market_url) == 7178002
    assert client.get_market_item_orders_histogram_by_url(market_url)["kind"] == "histogram"
    assert client.get_market_item_orders_summary_by_url(market_url)["kind"] == "summary"
    assert client.get_market_item_listings_map_by_url(market_url)["kind"] == "listings_map"
    assert client.get_all_market_item_listings_summary_by_url(market_url)["kind"] == "all_listings"
    assert client.get_all_market_item_listings_map_by_url(market_url)["kind"] == "all_listings_map"
    assert client.get_market_listing_by_id_by_url(market_url, "123")["kind"] == "listing_by_id"
    assert client.get_all_market_listing_by_id_by_url(market_url, "123")["kind"] == "all_listing_by_id"
    assert client.find_market_item_listings_by_url(market_url, max_price=500)["kind"] == "find_listings"

    client.market.get_item_name_id = original_get_item_name_id
    client.market.get_item_orders_histogram = original_get_item_orders_histogram
    client.market.get_item_orders_summary = original_get_item_orders_summary
    client.market.get_item_listings_map = original_get_item_listings_map
    client.market.get_all_item_listings_summary = original_get_all_item_listings_summary
    client.market.get_all_item_listings_map = original_get_all_item_listings_map
    client.market.get_listing_by_id = original_get_listing_by_id
    client.market.get_all_listing_by_id = original_get_all_listing_by_id
    client.market.find_item_listings = original_find_item_listings
    client.close()


def test_client_inventory_url_helpers_delegate_correctly() -> None:
    client = SteamClient()

    original_get_inventory = client.get_inventory_for_user
    original_get_inventory_items = client.get_inventory_items_for_user
    original_get_inventory_items_summary = client.get_inventory_items_summary_for_user
    original_get_inventory_item_counts = client.get_inventory_item_counts_for_user
    original_get_inventory_item_by_asset_id = client.get_inventory_item_by_asset_id_for_user
    original_find_inventory_items = client.find_inventory_items_for_user
    original_get_full_inventory = client.get_full_inventory_for_user
    original_get_full_inventory_items = client.get_full_inventory_items_for_user
    original_get_full_inventory_items_summary = client.get_full_inventory_items_summary_for_user
    original_get_full_inventory_item_counts = client.get_full_inventory_item_counts_for_user
    original_get_full_inventory_item_by_asset_id = client.get_full_inventory_item_by_asset_id_for_user
    original_find_full_inventory_items = client.find_full_inventory_items_for_user

    client.get_inventory_for_user = lambda steam_id, app_id, context_id, **kwargs: {"steam_id": steam_id, "app_id": app_id, "context_id": context_id, "kind": "inventory"}
    client.get_inventory_items_for_user = lambda steam_id, app_id, context_id, **kwargs: {"steam_id": steam_id, "app_id": app_id, "context_id": context_id, "kind": "inventory_items"}
    client.get_inventory_items_summary_for_user = lambda steam_id, app_id, context_id, **kwargs: {"steam_id": steam_id, "app_id": app_id, "context_id": context_id, "kind": "inventory_summary"}
    client.get_inventory_item_counts_for_user = lambda steam_id, app_id, context_id, **kwargs: {"steam_id": steam_id, "app_id": app_id, "context_id": context_id, "kind": "inventory_counts"}
    client.get_inventory_item_by_asset_id_for_user = lambda steam_id, app_id, context_id, asset_id, **kwargs: {"steam_id": steam_id, "app_id": app_id, "context_id": context_id, "asset_id": asset_id, "kind": "inventory_asset"}
    client.find_inventory_items_for_user = lambda steam_id, app_id, context_id, **kwargs: {"steam_id": steam_id, "app_id": app_id, "context_id": context_id, "kind": "find_inventory"}
    client.get_full_inventory_for_user = lambda steam_id, app_id, context_id, **kwargs: {"steam_id": steam_id, "app_id": app_id, "context_id": context_id, "kind": "full_inventory"}
    client.get_full_inventory_items_for_user = lambda steam_id, app_id, context_id, **kwargs: {"steam_id": steam_id, "app_id": app_id, "context_id": context_id, "kind": "full_inventory_items"}
    client.get_full_inventory_items_summary_for_user = lambda steam_id, app_id, context_id, **kwargs: {"steam_id": steam_id, "app_id": app_id, "context_id": context_id, "kind": "full_inventory_summary"}
    client.get_full_inventory_item_counts_for_user = lambda steam_id, app_id, context_id, **kwargs: {"steam_id": steam_id, "app_id": app_id, "context_id": context_id, "kind": "full_inventory_counts"}
    client.get_full_inventory_item_by_asset_id_for_user = lambda steam_id, app_id, context_id, asset_id, **kwargs: {"steam_id": steam_id, "app_id": app_id, "context_id": context_id, "asset_id": asset_id, "kind": "full_inventory_asset"}
    client.find_full_inventory_items_for_user = lambda steam_id, app_id, context_id, **kwargs: {"steam_id": steam_id, "app_id": app_id, "context_id": context_id, "kind": "find_full_inventory"}

    inventory_url = "https://steamcommunity.com/inventory/76561197960435530/753/6"

    assert client.get_inventory_by_url(inventory_url)["kind"] == "inventory"
    assert client.get_inventory_items_by_url(inventory_url)["kind"] == "inventory_items"
    assert client.get_inventory_items_summary_by_url(inventory_url)["kind"] == "inventory_summary"
    assert client.get_inventory_item_counts_by_url(inventory_url)["kind"] == "inventory_counts"
    assert client.get_inventory_item_by_asset_id_by_url(inventory_url, "10")["kind"] == "inventory_asset"
    assert client.find_inventory_items_by_url(inventory_url)["kind"] == "find_inventory"
    assert client.get_full_inventory_by_url(inventory_url)["kind"] == "full_inventory"
    assert client.get_full_inventory_items_by_url(inventory_url)["kind"] == "full_inventory_items"
    assert client.get_full_inventory_items_summary_by_url(inventory_url)["kind"] == "full_inventory_summary"
    assert client.get_full_inventory_item_counts_by_url(inventory_url)["kind"] == "full_inventory_counts"
    assert client.get_full_inventory_item_by_asset_id_by_url(inventory_url, "10")["kind"] == "full_inventory_asset"
    assert client.find_full_inventory_items_by_url(inventory_url)["kind"] == "find_full_inventory"

    client.get_inventory_for_user = original_get_inventory
    client.get_inventory_items_for_user = original_get_inventory_items
    client.get_inventory_items_summary_for_user = original_get_inventory_items_summary
    client.get_inventory_item_counts_for_user = original_get_inventory_item_counts
    client.get_inventory_item_by_asset_id_for_user = original_get_inventory_item_by_asset_id
    client.find_inventory_items_for_user = original_find_inventory_items
    client.get_full_inventory_for_user = original_get_full_inventory
    client.get_full_inventory_items_for_user = original_get_full_inventory_items
    client.get_full_inventory_items_summary_for_user = original_get_full_inventory_items_summary
    client.get_full_inventory_item_counts_for_user = original_get_full_inventory_item_counts
    client.get_full_inventory_item_by_asset_id_for_user = original_get_full_inventory_item_by_asset_id
    client.find_full_inventory_items_for_user = original_find_full_inventory_items
    client.close()


def test_client_search_market_items_uses_market_summary_helper() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "success": True,
                "start": 0,
                "pagesize": 10,
                "total_count": 1,
                "results": [
                    {
                        "name": "AK-47 | Example",
                        "hash_name": "AK-47 | Example",
                        "asset_description": {"appid": 730, "market_hash_name": "AK-47 | Example"},
                    }
                ],
            }
        )
    )
    client = SteamClient(session=session)

    result = client.search_market_items(query="AK-47", app_id=730)

    assert result["items"][0]["hash_name"] == "AK-47 | Example"
    client.close()


def test_client_market_convenience_helpers_delegate_to_market_service() -> None:
    client = SteamClient()

    original_get_price_overview = client.market.get_price_overview
    original_get_item_name_id = client.market.get_item_name_id
    original_get_item_orders_histogram = client.market.get_item_orders_histogram
    original_get_item_orders_summary = client.market.get_item_orders_summary
    original_get_price_history = client.market.get_price_history
    original_get_item_listings_map = client.market.get_item_listings_map
    original_get_listing_by_id = client.market.get_listing_by_id

    client.market.get_price_overview = lambda app_id, market_hash_name, **kwargs: {
        "kind": "overview",
        "app_id": app_id,
        "market_hash_name": market_hash_name,
        "kwargs": kwargs,
    }
    client.market.get_item_name_id = lambda app_id, market_hash_name: 7178002
    client.market.get_item_orders_histogram = lambda **kwargs: {"kind": "histogram", "kwargs": kwargs}
    client.market.get_item_orders_summary = lambda **kwargs: {"kind": "summary", "kwargs": kwargs}
    client.market.get_price_history = lambda app_id, market_hash_name: {
        "kind": "history",
        "app_id": app_id,
        "market_hash_name": market_hash_name,
    }
    client.market.get_item_listings_map = lambda app_id, market_hash_name, **kwargs: {
        "kind": "listings_map",
        "app_id": app_id,
        "market_hash_name": market_hash_name,
        "kwargs": kwargs,
    }
    client.market.get_listing_by_id = lambda app_id, market_hash_name, listing_id, **kwargs: {
        "kind": "listing_by_id",
        "app_id": app_id,
        "market_hash_name": market_hash_name,
        "listing_id": listing_id,
        "kwargs": kwargs,
    }

    assert client.get_market_price_overview(730, "AK-47 | Example")["kind"] == "overview"
    assert client.get_market_item_name_id(730, "AK-47 | Example") == 7178002
    assert client.get_market_item_orders_histogram(app_id=730, market_hash_name="AK-47 | Example")["kind"] == "histogram"
    assert client.get_market_item_orders_summary(app_id=730, market_hash_name="AK-47 | Example")["kind"] == "summary"
    assert client.get_market_price_history(730, "AK-47 | Example")["kind"] == "history"
    assert client.get_market_item_listings_map(730, "AK-47 | Example")["kind"] == "listings_map"
    assert client.get_market_listing_by_id(730, "AK-47 | Example", "1")["kind"] == "listing_by_id"

    client.market.get_price_overview = original_get_price_overview
    client.market.get_item_name_id = original_get_item_name_id
    client.market.get_item_orders_histogram = original_get_item_orders_histogram
    client.market.get_item_orders_summary = original_get_item_orders_summary
    client.market.get_price_history = original_get_price_history
    client.market.get_item_listings_map = original_get_item_listings_map
    client.market.get_listing_by_id = original_get_listing_by_id
    client.close()


def test_client_public_app_stats_and_webapi_helpers_delegate_to_services() -> None:
    client = SteamClient(api_key="test")

    original_get_servers_at_address = client.apps.get_servers_at_address
    original_up_to_date_check = client.apps.up_to_date_check
    original_get_news_for_app = client.news.get_news_for_app
    original_get_news_for_app_authed = client.news.get_news_for_app_authed
    original_get_number_of_current_players = client.user_stats.get_number_of_current_players
    original_get_global_achievement_percentages_for_app = client.user_stats.get_global_achievement_percentages_for_app
    original_get_schema_for_game = client.user_stats.get_schema_for_game
    original_get_global_stats_for_game = client.user_stats.get_global_stats_for_game
    original_get_player_achievements = client.user_stats.get_player_achievements
    original_get_user_stats_for_game = client.user_stats.get_user_stats_for_game
    original_get_server_info = client.webapi_util.get_server_info
    original_get_supported_api_list = client.webapi_util.get_supported_api_list

    client.apps.get_servers_at_address = lambda address: {"address": address}
    client.apps.up_to_date_check = lambda app_id, version: {"app_id": app_id, "version": version}
    client.news.get_news_for_app = lambda app_id, **kwargs: {"app_id": app_id, "kwargs": kwargs}
    client.news.get_news_for_app_authed = lambda app_id, **kwargs: {"app_id": app_id, "kwargs": kwargs}
    client.user_stats.get_number_of_current_players = lambda app_id: {"app_id": app_id, "player_count": 123}
    client.user_stats.get_global_achievement_percentages_for_app = lambda app_id: {"app_id": app_id}
    client.user_stats.get_schema_for_game = lambda app_id, **kwargs: {"app_id": app_id, "kwargs": kwargs}
    client.user_stats.get_global_stats_for_game = lambda app_id, names, **kwargs: {
        "app_id": app_id,
        "names": names,
        "kwargs": kwargs,
    }
    client.user_stats.get_player_achievements = lambda steam_id, app_id, **kwargs: {
        "steam_id": steam_id,
        "app_id": app_id,
        "kwargs": kwargs,
    }
    client.user_stats.get_user_stats_for_game = lambda steam_id, app_id: {
        "steam_id": steam_id,
        "app_id": app_id,
    }
    client.webapi_util.get_server_info = lambda: {"servertime": 1}
    client.webapi_util.get_supported_api_list = lambda **kwargs: {"kwargs": kwargs}

    assert client.get_servers_at_address("1.2.3.4")["address"] == "1.2.3.4"
    assert client.up_to_date_check(570, 0)["app_id"] == 570
    assert client.get_news_for_app(570, count=1)["kwargs"]["count"] == 1
    assert client.get_news_for_app_authed(570, count=1)["kwargs"]["count"] == 1
    assert client.get_number_of_current_players(570)["player_count"] == 123
    assert client.get_global_achievement_percentages_for_app(570)["app_id"] == 570
    assert client.get_schema_for_game(570, language="english")["kwargs"]["language"] == "english"
    assert client.get_global_stats_for_game(570, ["total_kills"])["names"] == ["total_kills"]
    assert client.get_player_achievements_for_user("76561197960435530", 570)["steam_id"] == "76561197960435530"
    assert client.get_user_stats_for_game_for_user("76561197960435530", 570)["app_id"] == 570
    assert client.get_web_api_server_info()["servertime"] == 1
    assert client.get_supported_api_list(include_restricted=True)["kwargs"]["include_restricted"] is True

    client.apps.get_servers_at_address = original_get_servers_at_address
    client.apps.up_to_date_check = original_up_to_date_check
    client.news.get_news_for_app = original_get_news_for_app
    client.news.get_news_for_app_authed = original_get_news_for_app_authed
    client.user_stats.get_number_of_current_players = original_get_number_of_current_players
    client.user_stats.get_global_achievement_percentages_for_app = original_get_global_achievement_percentages_for_app
    client.user_stats.get_schema_for_game = original_get_schema_for_game
    client.user_stats.get_global_stats_for_game = original_get_global_stats_for_game
    client.user_stats.get_player_achievements = original_get_player_achievements
    client.user_stats.get_user_stats_for_game = original_get_user_stats_for_game
    client.webapi_util.get_server_info = original_get_server_info
    client.webapi_util.get_supported_api_list = original_get_supported_api_list
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


def test_client_can_get_friend_ids_for_user_from_profile_url() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "friendslist": {
                    "friends": [
                        {"steamid": "76561197960435530"},
                        {"steamid": "76561197960287930"},
                    ]
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.get_friend_ids_for_user("https://steamcommunity.com/profiles/76561197960434622/")

    assert result == ["76561197960435530", "76561197960287930"]
    client.close()


def test_client_can_get_user_group_ids_for_user_from_profile_url() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "groups": [
                        {"gid": "103582791429521412"},
                        {"gid": "103582791429521413"},
                    ]
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.get_user_group_ids_for_user("https://steamcommunity.com/profiles/76561197960434622/")

    assert result == ["103582791429521412", "103582791429521413"]
    client.close()


def test_client_can_get_friend_bans_for_user_with_limit() -> None:
    session = SequenceSession(
        [
            DummyResponse(
                json_data={
                    "friendslist": {
                        "friends": [
                            {"steamid": "76561197960435530"},
                            {"steamid": "76561197960287930"},
                        ]
                    }
                }
            ),
            DummyResponse(
                json_data={
                    "players": [
                        {"SteamId": "76561197960435530", "VACBanned": False, "CommunityBanned": False},
                    ]
                }
            ),
        ]
    )
    client = SteamClient(api_key="test", session=session)

    result = client.get_friend_bans_for_user("76561197960434622", limit=1)

    assert len(result) == 1
    assert result[0]["steamid"] == "76561197960435530"
    client.close()


def test_client_can_get_friend_bans_map_for_user() -> None:
    session = SequenceSession(
        [
            DummyResponse(
                json_data={
                    "friendslist": {
                        "friends": [
                            {"steamid": "76561197960435530"},
                            {"steamid": "76561197960287930"},
                        ]
                    }
                }
            ),
            DummyResponse(
                json_data={
                    "players": [
                        {"SteamId": "76561197960435530", "VACBanned": False, "CommunityBanned": False},
                        {"SteamId": "76561197960287930", "VACBanned": True, "CommunityBanned": False},
                    ]
                }
            ),
        ]
    )
    client = SteamClient(api_key="test", session=session)

    result = client.get_friend_bans_map_for_user("76561197960434622")

    assert result["76561197960287930"]["vac_banned"] is True
    client.close()


def test_client_can_get_friend_summaries_for_user_from_profile_url() -> None:
    session = SequenceSession(
        [
            DummyResponse(
                json_data={
                    "friendslist": {
                        "friends": [
                            {"steamid": "76561197960435530"},
                            {"steamid": "76561197960287930"},
                        ]
                    }
                }
            ),
            DummyResponse(
                json_data={
                    "response": {
                        "players": [
                            {"steamid": "76561197960435530", "personaname": "Robin"},
                            {"steamid": "76561197960287930", "personaname": "John"},
                        ]
                    }
                }
            ),
        ]
    )
    client = SteamClient(api_key="test", session=session)

    result = client.get_friend_summaries_for_user("https://steamcommunity.com/profiles/76561197960434622/", limit=2)

    assert len(result["friends"]) == 2
    assert result["friends"][1]["personaname"] == "John"
    client.close()


def test_apps_get_app_details_many_returns_multiple_items() -> None:
    session = SequenceSession(
        [
            DummyResponse(json_data={"570": {"success": True, "data": {"name": "Dota 2", "type": "game"}}}),
            DummyResponse(json_data={"730": {"success": True, "data": {"name": "Counter-Strike 2", "type": "game"}}}),
        ]
    )
    client = SteamClient(session=session)

    result = client.get_app_details_many([570, 730])

    assert len(result) == 2
    assert result[0]["name"] == "Dota 2"
    assert result[1]["name"] == "Counter-Strike 2"
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


def test_community_get_web_api_key_page_state_parses_registration_state() -> None:
    html = """
    <div id="mainContents"><h2>Access Denied</h2></div>
    <div id="bodyContents_lo">
        <p>You will be granted access to Steam Web API keys when you have games in your Steam account.</p>
    </div>
    <h2>Register for a new Steam Web API Key</h2>
    <form><input name="domain" value=""></form>
    <a>Steam Web API Terms of Use</a>
    """
    session = SequenceSession([DummyResponse(text=html), DummyResponse(text=html)])
    client = SteamClient(api_key="test", session=session)
    client.set_community_credentials(
        CommunityCredentials(
            steam_id="76561197960435530",
            session_id="session123",
            steam_login_secure="securecookie123",
        )
    )

    state = client.get_web_api_key_page_state()

    assert state["has_access"] is False
    assert state["registration_form_visible"] is True
    assert state["revoke_available"] is False
    assert state["terms_required"] is True
    assert "have games in your Steam account" in state["reason"]
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


def test_groups_get_group_details_accepts_full_group_url() -> None:
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
      <totalPages>1</totalPages>
      <currentPage>1</currentPage>
    </memberList>
    """
    session = RecordingSession(DummyResponse(text=xml))
    client = SteamClient(session=session)

    details = client.get_group_details("https://steamcommunity.com/groups/Valve/")

    assert details["group_name"] == "Valve"
    assert "/groups/Valve/memberslistxml/" in session.calls[0]["url"]
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


def test_groups_fetch_group_id64_does_not_require_login() -> None:
    xml = """
    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <memberList><groupID64>103582791429521412</groupID64></memberList>
    """
    session = RecordingSession(DummyResponse(text=xml))
    client = SteamClient(session=session)

    group_id64 = client.groups.fetch_group_id64("Valve")

    assert group_id64 == "103582791429521412"
    assert session.calls[0]["cookies"] is None
    client.close()


def test_groups_get_all_group_members_paginates_and_deduplicates() -> None:
    session = SequenceSession(
        [
            DummyResponse(
                text="""
                <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                <memberList>
                  <groupID64>103582791429521412</groupID64>
                  <memberCount>4</memberCount>
                  <totalPages>2</totalPages>
                  <currentPage>1</currentPage>
                  <members>
                    <steamID64>1</steamID64>
                    <steamID64>2</steamID64>
                  </members>
                </memberList>
                """
            ),
            DummyResponse(
                text="""
                <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                <memberList>
                  <groupID64>103582791429521412</groupID64>
                  <memberCount>4</memberCount>
                  <totalPages>2</totalPages>
                  <currentPage>2</currentPage>
                  <members>
                    <steamID64>2</steamID64>
                    <steamID64>3</steamID64>
                    <steamID64>4</steamID64>
                  </members>
                </memberList>
                """
            ),
        ]
    )
    client = SteamClient(session=session)

    result = client.groups.get_all_group_members("Valve")

    assert result["pages_fetched"] == 2
    assert result["member_count"] == 4
    assert result["members"] == ["1", "2", "3", "4"]
    assert session.calls[1]["params"]["p"] == 2
    client.close()


def test_client_can_get_all_group_members_without_login() -> None:
    session = RecordingSession(
        DummyResponse(
            text="""
            <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <memberList>
              <groupID64>103582791429521412</groupID64>
              <memberCount>2</memberCount>
              <totalPages>1</totalPages>
              <currentPage>1</currentPage>
              <members>
                <steamID64>1</steamID64>
                <steamID64>2</steamID64>
              </members>
            </memberList>
            """
        )
    )
    client = SteamClient(session=session)

    result = client.get_all_group_members("Valve")

    assert result["pages_fetched"] == 1
    assert result["members"] == ["1", "2"]
    client.close()


def test_user_stats_global_achievement_percentages_map_normalizes_entries() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "achievementpercentages": {
                    "achievements": [
                        {"name": "FIRST_BLOOD", "percent": 12.5},
                    ]
                }
            }
        )
    )
    client = SteamClient(session=session)

    result = client.get_global_achievement_percentages_map(570)

    assert result["achievement_count"] == 1
    assert result["achievements_map"]["FIRST_BLOOD"]["percent"] == 12.5
    client.close()


def test_user_stats_schema_for_game_summary_normalizes_achievements_and_stats() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "game": {
                    "gameName": "Dota 2",
                    "gameVersion": "1",
                    "availableGameStats": {
                        "achievements": [
                            {"name": "WIN_ONE", "displayName": "Winner", "description": "Win one game", "hidden": 0}
                        ],
                        "stats": [
                            {"name": "total_kills", "displayName": "Total Kills", "defaultvalue": 0}
                        ],
                    },
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.get_schema_for_game_summary(570)

    assert result["game_name"] == "Dota 2"
    assert result["achievement_count"] == 1
    assert result["achievements_map"]["WIN_ONE"]["display_name"] == "Winner"
    assert result["stats_map"]["total_kills"]["display_name"] == "Total Kills"
    client.close()


def test_user_stats_global_stats_for_game_summary_maps_requested_names() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "result": {
                    "globalstats": {
                        "total_kills": 12345,
                    }
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.get_global_stats_for_game_summary(570, ["total_kills"])

    assert result["stats"][0]["name"] == "total_kills"
    assert result["stats"][0]["value"] == 12345
    assert result["stats_map"]["total_kills"]["value"] == 12345
    client.close()


def test_user_stats_player_achievements_summary_normalizes_progress() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "playerstats": {
                    "steamID": "76561197960434622",
                    "gameName": "Dota 2",
                    "achievements": [
                        {"apiname": "WIN_ONE", "achieved": 1, "unlocktime": 100, "name": "Winner"},
                        {"apiname": "WIN_TEN", "achieved": 0, "unlocktime": 0, "name": "Veteran"},
                    ],
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.get_player_achievements_summary_for_user("76561197960434622", 570)

    assert result["game_name"] == "Dota 2"
    assert result["achievement_count"] == 2
    assert result["achieved_count"] == 1
    assert result["completion_percentage"] == 50.0
    client.close()


def test_groups_get_group_member_summaries_combines_member_ids_with_player_summaries() -> None:
    session = SequenceSession(
        [
            DummyResponse(
                text="""
                <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                <memberList>
                  <groupID64>103582791429521412</groupID64>
                  <memberCount>2</memberCount>
                  <totalPages>1</totalPages>
                  <currentPage>1</currentPage>
                  <members>
                    <steamID64>76561197960435530</steamID64>
                    <steamID64>76561197960287930</steamID64>
                  </members>
                </memberList>
                """
            ),
            DummyResponse(
                json_data={
                    "response": {
                        "players": [
                            {"steamid": "76561197960435530", "personaname": "Robin"},
                        ]
                    }
                }
            ),
        ]
    )
    client = SteamClient(api_key="test", session=session)

    result = client.groups.get_group_member_summaries("Valve", limit=1)

    assert result["member_ids"] == ["76561197960435530"]
    assert result["members"][0]["personaname"] == "Robin"
    client.close()


def test_groups_get_group_member_summaries_map_indexes_members_by_steam_id() -> None:
    session = SequenceSession(
        [
            DummyResponse(
                text="""
                <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                <memberList>
                  <groupID64>103582791429521412</groupID64>
                  <memberCount>1</memberCount>
                  <members>
                    <steamID64>76561197960435530</steamID64>
                  </members>
                </memberList>
                """
            ),
            DummyResponse(
                json_data={
                    "response": {
                        "players": [
                            {"steamid": "76561197960435530", "personaname": "Robin"}
                        ]
                    }
                }
            ),
        ]
    )
    client = SteamClient(api_key="test-key", session=session)

    result = client.get_group_member_summaries_map("Valve", limit=1)

    assert result["members_by_steam_id"]["76561197960435530"]["personaname"] == "Robin"
    client.close()


def test_groups_get_all_group_member_summaries_combines_aggregated_members_with_player_summaries() -> None:
    session = SequenceSession(
        [
            DummyResponse(
                text="""
                <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                <memberList>
                  <groupID64>103582791429521412</groupID64>
                  <memberCount>3</memberCount>
                  <totalPages>2</totalPages>
                  <currentPage>1</currentPage>
                  <members>
                    <steamID64>76561197960435530</steamID64>
                    <steamID64>76561197960287930</steamID64>
                  </members>
                </memberList>
                """
            ),
            DummyResponse(
                text="""
                <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                <memberList>
                  <groupID64>103582791429521412</groupID64>
                  <memberCount>3</memberCount>
                  <totalPages>2</totalPages>
                  <currentPage>2</currentPage>
                  <members>
                    <steamID64>76561198000000000</steamID64>
                  </members>
                </memberList>
                """
            ),
            DummyResponse(
                json_data={
                    "response": {
                        "players": [
                            {"steamid": "76561197960435530", "personaname": "Robin"},
                            {"steamid": "76561197960287930", "personaname": "John"},
                        ]
                    }
                }
            ),
        ]
    )
    client = SteamClient(api_key="test", session=session)

    result = client.get_all_group_member_summaries("Valve", max_pages=2, max_members=2)

    assert result["pages_fetched"] == 2
    assert result["member_ids"] == ["76561197960435530", "76561197960287930"]
    assert len(result["members"]) == 2
    client.close()


def test_groups_get_all_group_member_summaries_map_indexes_members_by_steam_id() -> None:
    session = SequenceSession(
        [
            DummyResponse(
                text="""
                <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                <memberList>
                  <groupID64>103582791429521412</groupID64>
                  <memberCount>2</memberCount>
                  <totalPages>1</totalPages>
                  <currentPage>1</currentPage>
                  <members>
                    <steamID64>76561197960435530</steamID64>
                    <steamID64>76561197960287930</steamID64>
                  </members>
                </memberList>
                """
            ),
            DummyResponse(
                json_data={
                    "response": {
                        "players": [
                            {"steamid": "76561197960435530", "personaname": "Robin"},
                            {"steamid": "76561197960287930", "personaname": "Other"},
                        ]
                    }
                }
            ),
        ]
    )
    client = SteamClient(api_key="test-key", session=session)

    result = client.get_all_group_member_summaries_map("Valve", max_pages=1, max_members=2)

    assert set(result["members_by_steam_id"]) == {"76561197960435530", "76561197960287930"}
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


def test_client_group_helpers_delegate_to_groups_service() -> None:
    client = SteamClient()

    original_fetch_group_id64 = client.groups.fetch_group_id64
    original_fetch_group_id = client.groups.fetch_group_id
    original_check_name_availability = client.groups.check_name_availability
    original_check_url_availability = client.groups.check_url_availability
    original_check_tag_availability = client.groups.check_tag_availability
    original_get_group_member_summaries_map = client.groups.get_group_member_summaries_map
    original_get_all_group_member_summaries_map = client.groups.get_all_group_member_summaries_map
    original_create_group = client.groups.create_group

    client.groups.fetch_group_id64 = lambda group_url: "103582791429521412"
    client.groups.fetch_group_id = lambda group_url: "123456"
    client.groups.check_name_availability = lambda name: {"kind": "name", "value": name}
    client.groups.check_url_availability = lambda group_url: {"kind": "url", "value": group_url}
    client.groups.check_tag_availability = lambda abbreviation: {"kind": "tag", "value": abbreviation}
    client.groups.get_group_member_summaries_map = lambda group_url, **kwargs: {"kind": "member_map", "group_url": group_url, "kwargs": kwargs}
    client.groups.get_all_group_member_summaries_map = lambda group_url, **kwargs: {"kind": "all_member_map", "group_url": group_url, "kwargs": kwargs}
    client.groups.create_group = lambda **kwargs: {"kind": "create", "kwargs": kwargs}

    assert client.get_group_id64("Valve") == "103582791429521412"
    assert client.get_group_id("editable-group") == "123456"
    assert client.check_group_name_availability("Example")["value"] == "Example"
    assert client.check_group_url_availability("example-group")["kind"] == "url"
    assert client.check_group_tag_availability("EX")["kind"] == "tag"
    assert client.get_group_member_summaries_map("Valve", limit=5)["kind"] == "member_map"
    assert client.get_all_group_member_summaries_map("Valve", max_pages=2)["kind"] == "all_member_map"
    assert client.create_group(name="Example", abbreviation="EX", group_url="example")["kwargs"]["group_url"] == "example"

    client.groups.fetch_group_id64 = original_fetch_group_id64
    client.groups.fetch_group_id = original_fetch_group_id
    client.groups.check_name_availability = original_check_name_availability
    client.groups.check_url_availability = original_check_url_availability
    client.groups.check_tag_availability = original_check_tag_availability
    client.groups.get_group_member_summaries_map = original_get_group_member_summaries_map
    client.groups.get_all_group_member_summaries_map = original_get_all_group_member_summaries_map
    client.groups.create_group = original_create_group
    client.close()


def test_remote_storage_collection_child_map_indexes_children() -> None:
    session = SequenceSession(
        [
            DummyResponse(
                json_data={
                    "response": {
                        "collectiondetails": [
                            {
                                "publishedfileid": "3210489689",
                                "result": 1,
                                "childcount": 2,
                                "children": [
                                    {"publishedfileid": "111"},
                                    {"publishedfileid": "222"},
                                ],
                            }
                        ]
                    }
                }
            ),
            DummyResponse(
                json_data={
                    "response": {
                        "publishedfiledetails": [
                            {"publishedfileid": "111", "result": 1, "title": "Alpha Child"},
                            {"publishedfileid": "222", "result": 1, "title": "Beta Child"},
                        ]
                    }
                }
            ),
        ]
    )
    client = SteamClient(api_key="test", session=session)

    result = client.get_collection_child_map("3210489689")

    assert result["children_by_id"]["111"]["title"] == "Alpha Child"
    assert result["children_by_id"]["222"]["title"] == "Beta Child"
    client.close()


def test_remote_storage_find_collection_child_prefers_exact_title() -> None:
    session = SequenceSession(
        [
            DummyResponse(
                json_data={
                    "response": {
                        "collectiondetails": [
                            {
                                "publishedfileid": "3210489689",
                                "result": 1,
                                "childcount": 2,
                                "children": [
                                    {"publishedfileid": "111"},
                                    {"publishedfileid": "222"},
                                ],
                            }
                        ]
                    }
                }
            ),
            DummyResponse(
                json_data={
                    "response": {
                        "publishedfiledetails": [
                            {"publishedfileid": "111", "result": 1, "title": "ChengHai3C test"},
                            {"publishedfileid": "222", "result": 1, "title": "ChengHai3C test beta"},
                        ]
                    }
                }
            ),
        ]
    )
    client = SteamClient(api_key="test", session=session)

    result = client.find_collection_child("3210489689", title="ChengHai3C test")

    assert result["matched_exactly"] is True
    assert result["count"] == 1
    assert result["match"]["published_file_id"] == "111"
    client.close()


def test_published_files_find_published_file_prefers_exact_title() -> None:
    session = RecordingSession(
        DummyResponse(
            json_data={
                "response": {
                    "total": 2,
                    "next_cursor": "*",
                    "publishedfiledetails": [
                        {"publishedfileid": "111", "result": 1, "title": "Dota Run Old"},
                        {"publishedfileid": "222", "result": 1, "title": "Dota Run Old Beta"},
                    ],
                }
            }
        )
    )
    client = SteamClient(api_key="test", session=session)

    result = client.find_published_file(
        query_type=0,
        title="Dota Run Old",
        app_id=570,
        max_pages=1,
        max_items=10,
    )

    assert result["matched_exactly"] is True
    assert result["count"] == 1
    assert result["match"]["published_file_id"] == "111"
    assert session.calls[0]["params"]["search_text"] == "Dota Run Old"
    client.close()
