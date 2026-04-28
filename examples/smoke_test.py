from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from steamcommunitykit import SteamClient, SteamError  # noqa: E402


DEFAULT_STEAM_ID = "76561197960435530"
DEFAULT_VANITY = "gaben"
DEFAULT_APP_ID = 570
DEFAULT_GROUP_URL = "valve"
DEFAULT_LARGE_GROUP_URL = "steamdb"
DEFAULT_PUBLISHED_FILE_ID = "2682416130"
DEFAULT_GROUP_NAME_CHECK = "steamcommunitykit-smoke-check"
DEFAULT_MARKET_ITEM = "AK-47 | Redline (Field-Tested)"
DEFAULT_INVENTORY_APP_ID = 753
DEFAULT_INVENTORY_CONTEXT_ID = 6


def print_header(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def print_result(name: str, ok: bool, detail: str) -> None:
    status = "PASS" if ok else "FAIL"
    print("[{0}] {1}: {2}".format(status, name, detail))


def run_check(name: str, func) -> None:
    try:
        result = func()
        print_result(name, True, result)
    except Exception as exc:  # noqa: BLE001
        print_result(name, False, "{0}: {1}".format(type(exc).__name__, exc))


def build_client(args) -> SteamClient:
    if args.api_json:
        return SteamClient.from_api_json(args.api_json)
    if args.api_key:
        return SteamClient(api_key=args.api_key)
    return SteamClient()


def configure_community_session(client: SteamClient, args) -> bool:
    if args.cookie_string:
        client.set_community_credentials_from_cookie_string(args.cookie_string)
        return True
    if args.refresh_token:
        client.login_to_community_with_refresh_token(args.refresh_token)
        return True
    if args.username and args.password:
        client.login_to_community(
            args.username,
            args.password,
            steam_guard_code=args.steam_guard_code,
            prompt_for_steam_guard=not args.no_prompt_steam_guard,
        )
        return True
    return False


def run_public_suite(client: SteamClient, args) -> None:
    print_header("Public / API Key Tests")
    workshop_cache = {}

    run_check(
        "Resolve Steam ID From Vanity",
        lambda: client.resolve_steam_id(args.vanity),
    )
    run_check(
        "Get Player Summary",
        lambda: client.get_player_summary(args.profile_identifier).get("personaname", "<no personaname>"),
    )
    run_check(
        "Get Player Summaries Batch",
        lambda: "players={0}".format(
            len(client.users.get_player_summaries([args.steam_id, client.resolve_steam_id(args.vanity)]))
        ),
    )
    run_check(
        "Get Friend List",
        lambda: "friends={0}".format(
            len(client.get_friend_list_for_user(args.profile_identifier)["friendslist"]["friends"])
        ),
    )
    run_check(
        "Get User Group List",
        lambda: "groups={0}".format(
            len(client.get_user_group_list_for_user(args.profile_identifier).get("groups", []))
        ),
    )
    run_check(
        "Get Owned Games",
        lambda: _format_optional_count(
            client.get_owned_games_for_user(args.profile_identifier, include_appinfo=False),
            "game_count",
        ),
    )
    run_check(
        "Get Recently Played Games",
        lambda: _format_optional_count(
            client.get_recently_played_games_for_user(args.profile_identifier),
            "total_count",
        ),
    )
    run_check(
        "Get Steam Level",
        lambda: str(client.get_steam_level_for_user(args.profile_identifier).get("player_level", 0)),
    )
    run_check(
        "Get Badges",
        lambda: "badges={0}".format(len(client.get_badges_for_user(args.profile_identifier).get("badges", []))),
    )
    run_check(
        "Get Community Badge Progress",
        lambda: "quests={0}".format(
            len(client.get_community_badge_progress_for_user(args.profile_identifier, 1).get("quests", []))
        ),
    )
    run_check(
        "Get Servers At Address",
        lambda: "servers={0}".format(
            len(client.apps.get_servers_at_address("208.64.200.0").get("response", {}).get("servers", []))
        ),
    )
    run_check(
        "Up To Date Check",
        lambda: str(client.apps.up_to_date_check(args.app_id, 0).get("up_to_date")),
    )
    run_check(
        "Get News For App",
        lambda: "newsitems={0}".format(
            len(client.news.get_news_for_app(args.app_id, count=1).get("appnews", {}).get("newsitems", []))
        ),
    )
    run_check(
        "Get Number Of Current Players",
        lambda: str(client.user_stats.get_number_of_current_players(args.app_id).get("player_count", 0)),
    )
    run_check(
        "Get Global Achievement Percentages",
        lambda: "achievements={0}".format(
            len(
                client.user_stats.get_global_achievement_percentages_for_app(args.app_id).get(
                    "achievementpercentages", {}
                ).get("achievements", [])
            )
        ),
    )
    run_check(
        "Get Schema For Game",
        lambda: "gameName={0}".format(
            client.user_stats.get_schema_for_game(args.app_id).get("game", {}).get("gameName", "<unknown>")
        ),
    )
    run_check(
        "Get Global Stats For Game",
        lambda: "globalstats_keys={0}".format(
            sorted(
                client.user_stats.get_global_stats_for_game(
                    args.app_id,
                    ["total_kills"],
                ).keys()
            )
        ),
    )
    run_check(
        "Get Trade Offers Summary",
        lambda: "pending_received={0}".format(
            client.econ.get_trade_offers_summary().get("pending_received_count", 0)
        ),
    )
    run_check(
        "Get Trade Offers",
        lambda: _format_trade_offers(
            client.econ.get_trade_offers(
                get_sent_offers=True,
                get_received_offers=True,
                get_descriptions=False,
                language="en",
                active_only=True,
                historical_only=False,
                time_historical_cutoff=0,
            )
        ),
    )
    run_check(
        "Get Trade History",
        lambda: _format_trade_history(
            client.econ.get_trade_history(
                max_trades=10,
                start_after_time=0,
                start_after_trade_id="1",
                navigating_back=False,
                get_descriptions=False,
                language="en",
                include_failed=False,
                include_total=True,
            )
        ),
    )
    run_check(
        "Get Store App List",
        lambda: "apps={0}".format(
            len(client.store.get_app_list(include_games=True).get("apps", []))
        ),
    )
    run_check(
        "Query Published Files",
        lambda: _capture_workshop_query_summary(
            workshop_cache,
            client.query_published_files(
                query_type=0,
                app_id=args.app_id,
                cursor="*",
                num_per_page=1,
                return_short_description=True,
                return_previews=True,
                return_tags=True,
            )
        ),
    )
    run_check(
        "Query Published Files Multi-Page",
        lambda: _format_workshop_multi_page(
            client.query_all_published_files(
                query_type=0,
                app_id=args.app_id,
                cursor="*",
                num_per_page=2,
                return_short_description=True,
                max_pages=2,
                max_items=3,
            )
        ),
    )
    run_check(
        "Get Published File Details",
        lambda: _format_published_file_detail(
            client.get_published_file_detail(
                _require_workshop_item_id(workshop_cache, args)
            )
        ),
    )
    run_check(
        "Get Collection Details",
        lambda: "collections={0}".format(
            len(client.remote_storage.get_collection_details([args.published_file_id]).get("collectiondetails", []))
        ),
    )
    run_check(
        "Get Web API Server Info",
        lambda: str(client.webapi_util.get_server_info()),
    )
    run_check(
        "Get Supported API List",
        lambda: "interfaces={0}".format(
            len(client.webapi_util.get_supported_api_list().get("apilist", {}).get("interfaces", []))
        ),
    )

    if args.include_conditional:
        print_header("Conditional / Steam-Dependent Public Tests")
        run_check(
            "Get Single Game Playtime",
            lambda: str(
                client.get_single_game_playtime_for_user(args.profile_identifier, args.app_id).get(
                    "playtime_forever", 0
                )
            ),
        )
        run_check(
            "Get News For App Authed",
            lambda: "newsitems={0}".format(
                len(
                    client.news.get_news_for_app_authed(args.app_id, count=1).get(
                        "appnews", {}
                    ).get("newsitems", [])
                )
            ),
        )
        run_check(
            "Get Player Achievements",
            lambda: "playerstats_keys={0}".format(
                sorted(
                    client.user_stats.get_player_achievements(
                        client.resolve_steam_id(args.profile_identifier),
                        args.app_id,
                    ).keys()
                )
            ),
        )
        run_check(
            "Get User Stats For Game",
            lambda: "playerstats_keys={0}".format(
                sorted(
                    client.user_stats.get_user_stats_for_game(
                        client.resolve_steam_id(args.profile_identifier),
                        args.app_id,
                    ).keys()
                )
            ),
        )
        run_check(
            "Get UGC File Details",
            lambda: "data_keys={0}".format(
                sorted(
                    client.remote_storage.get_ugc_file_details(
                        args.published_file_id,
                        args.app_id,
                        client.resolve_steam_id(args.profile_identifier),
                    ).keys()
                )
            ),
        )


def run_no_key_public_suite(client: SteamClient, args) -> None:
    print_header("Public / No-Key Community Tests")
    run_check(
        "Resolve Steam ID From Vanity (Community XML)",
        lambda: client.resolve_steam_id(args.vanity),
    )
    run_check(
        "Resolve Community Profile XML",
        lambda: "persona={0}".format(client.users.resolve_community_profile_xml(args.profile_identifier).get("personaname", "")),
    )
    run_check(
        "Get Player Summary (Community XML)",
        lambda: client.get_player_summary(args.profile_identifier).get("personaname", "<no personaname>"),
    )
    run_check(
        "Market Price Overview",
        lambda: str(client.market.get_price_overview(args.market_app_id, args.market_hash_name)),
    )
    run_check(
        "Market Search",
        lambda: "results={0}".format(
            client.market.search_items(query=args.market_query, app_id=args.market_app_id, count=5).get(
                "total_count",
                0,
            )
        ),
    )
    run_check(
        "Market Search Summary",
        lambda: _format_market_search_summary(
            client.search_market_items(query=args.market_query, app_id=args.market_app_id, count=5)
        ),
    )
    run_check(
        "Market Item Name ID",
        lambda: str(client.market.get_item_name_id(args.market_app_id, args.market_hash_name)),
    )
    run_check(
        "Market Price History",
        lambda: "points={0}".format(
            len(client.market.get_price_history(args.market_app_id, args.market_hash_name).get("prices", []))
        ),
    )
    run_check(
        "Market Orders Histogram",
        lambda: "success={0}".format(
            client.market.get_item_orders_histogram(
                app_id=args.market_app_id,
                market_hash_name=args.market_hash_name,
            ).get("success")
        ),
    )
    run_check(
        "Market Orders Summary",
        lambda: _format_market_orders_summary(
            client.market.get_item_orders_summary(
                app_id=args.market_app_id,
                market_hash_name=args.market_hash_name,
            )
        ),
    )
    run_check(
        "Fetch Group ID64 (Public)",
        lambda: client.get_group_id64(args.group_url),
    )
    run_check(
        "Get Large Group Members (Public)",
        lambda: _format_group_members_aggregate(
            client.get_all_group_members(args.large_group_url, max_pages=2)
        ),
    )


def run_community_suite(client: SteamClient, args) -> None:
    print_header("Community / Logged-In Tests")
    cache = {}

    run_check(
        "Get Profile Bundle",
        lambda: _capture_profile_bundle(cache, client),
    )
    run_check(
        "Get Account Info",
        lambda: str(_require_cached(cache, "account_info")),
    )
    run_check(
        "Get Profile Edit State",
        lambda: "persona={0}".format(_require_cached(cache, "profile_edit_state").get("strPersonaName", "")),
    )
    run_check(
        "Get Profile Privacy",
        lambda: str(_require_cached(cache, "profile_privacy")),
    )
    run_check(
        "Get Trade Offer URL",
        lambda: _capture_result(cache, "trade_offer_url", client.community.get_trade_offer_url, str),
    )
    run_check(
        "Get Web API Key Status",
        lambda: _capture_result(cache, "web_api_key_status", client.community.get_web_api_key_status, str),
    )
    run_check(
        "Fetch Group ID64",
        lambda: str(client.groups.fetch_group_id64(args.group_url)),
    )
    run_check(
        "Check Group Name Availability",
        lambda: str(client.groups.check_name_availability(args.group_name_check)),
    )
    run_check(
        "Check Group URL Availability",
        lambda: str(client.groups.check_url_availability(args.group_name_check)),
    )
    run_check(
        "Check Group Tag Availability",
        lambda: str(client.groups.check_tag_availability(args.group_tag_check)),
    )
    run_check(
        "Get Group Details",
        lambda: str(client.groups.get_group_details(args.group_url)),
    )
    run_check(
        "Get Group Members",
        lambda: "members={0}".format(len(client.groups.get_group_members(args.group_url).get("members", []))),
    )
    run_check(
        "Community Cookie Export/Import Roundtrip",
        lambda: _format_cookie_roundtrip(client, args),
    )
    run_check(
        "Get Own Inventory Items",
        lambda: _format_inventory_items(
            client.get_full_inventory_items_for_user(
                _require_cached(cache, "account_info").get("steamid"),
                args.inventory_app_id,
                args.inventory_context_id,
                count=args.inventory_count,
                max_pages=2,
            )
        ),
    )

    if args.editable_group_url:
        run_check(
            "Fetch Editable Group ID",
            lambda: str(client.groups.fetch_group_id(args.editable_group_url)),
        )

    if args.write_checks:
        run_check(
            "Write Check: Edit Profile With Current Persona",
            lambda: str(
                client.community.edit_profile(
                    persona_name=(cache.get("profile_edit_state") or client.community.get_profile_edit_state()).get(
                        "strPersonaName",
                        "SteamCommunityKit",
                    )
                )
            ),
        )
        run_check(
            "Write Check: Set Profile Privacy With Current Values",
            lambda: _format_privacy_roundtrip(
                client,
                cache.get("profile_privacy") or client.community.get_profile_privacy(),
            ),
        )
        if args.set_persona_name:
            run_check(
                "Write Check: Set Persona Name",
                lambda: str(client.community.update_persona_name(persona_name=args.set_persona_name)),
            )
        if args.set_custom_url:
            run_check(
                "Write Check: Set Custom URL",
                lambda: str(client.community.update_custom_url(args.set_custom_url)),
            )
        if args.set_real_name:
            run_check(
                "Write Check: Set Real Name",
                lambda: str(client.community.update_real_name(args.set_real_name)),
            )
        if args.set_summary:
            run_check(
                "Write Check: Set Summary",
                lambda: str(client.community.update_summary(args.set_summary)),
            )

    if args.rotate_trade_url:
        run_check(
            "Write Check: Rotate Trade URL",
            lambda: str(client.community.rotate_trade_offer_url()),
        )

    if args.write_checks and (cache.get("account_info") or client.community.get_account_info()).get("is_limited"):
        run_check(
            "Expected Denial: Limited Account Group Creation",
            lambda: _expect_limited_group_creation_denial(client),
        )

    if args.write_checks and args.avatar_image:
        run_check(
            "Write Check: Upload Avatar",
            lambda: str(client.community.upload_avatar(args.avatar_image)),
        )


def _format_optional_count(payload: dict, key: str) -> str:
    value = payload.get(key)
    if value is None:
        return "{0}=unavailable".format(key)
    return "{0}={1}".format(key, value)


def _format_trade_offers(payload: dict) -> str:
    sent = len(payload.get("trade_offers_sent", []))
    received = len(payload.get("trade_offers_received", []))
    descriptions = len(payload.get("descriptions", []))
    next_cursor = payload.get("next_cursor", 0)
    return "sent={0} received={1} descriptions={2} next_cursor={3}".format(
        sent,
        received,
        descriptions,
        next_cursor,
    )


def _format_trade_history(payload: dict) -> str:
    total_trades = payload.get("total_trades")
    trades = payload.get("trades", [])
    more = payload.get("more")
    return "total_trades={0} returned={1} more={2}".format(
        total_trades if total_trades is not None else "unavailable",
        len(trades),
        more,
    )


def _format_market_orders_summary(payload: dict) -> str:
    return "buy_rows={0} sell_rows={1} buy_summary={2}".format(
        len(payload.get("buy_orders", [])),
        len(payload.get("sell_orders", [])),
        payload.get("buy_order_summary", ""),
    )


def _format_market_search_summary(payload: dict) -> str:
    items = payload.get("items", [])
    first_hash_name = items[0]["hash_name"] if items else "<none>"
    return "items={0} total={1} first={2}".format(
        len(items),
        payload.get("total_count"),
        first_hash_name,
    )


def _format_inventory_items(payload: dict) -> str:
    return "items={0} total_inventory_count={1} pages={2}".format(
        len(payload.get("items", [])),
        payload.get("total_inventory_count"),
        payload.get("pages_fetched", 0),
    )


def _capture_workshop_query_summary(cache: dict, payload: dict) -> str:
    cache["query_published_files"] = payload
    return "total={0} items={1}".format(
        payload.get("total"),
        len(payload.get("items", [])),
    )


def _require_workshop_item_id(cache: dict, args) -> str:
    payload = cache.get("query_published_files")
    if payload:
        item_ids = payload.get("item_ids", [])
        if item_ids:
            return item_ids[0]
    return args.published_file_id


def _format_published_file_detail(payload: dict) -> str:
    return "title={0} app={1} subs={2}".format(
        payload.get("title", ""),
        payload.get("app_name") or payload.get("app_id"),
        payload.get("subscriptions"),
    )


def _format_workshop_multi_page(payload: dict) -> str:
    return "items={0} pages={1} total={2}".format(
        len(payload.get("items", [])),
        payload.get("pages_fetched", 0),
        payload.get("total"),
    )


def _format_group_members_aggregate(payload: dict) -> str:
    return "members={0} pages={1}/{2}".format(
        len(payload.get("members", [])),
        payload.get("pages_fetched", 0),
        payload.get("total_pages", 0),
    )


def _format_cookie_roundtrip(client: SteamClient, args) -> str:
    cookie_string = client.export_community_cookie_string()
    roundtrip_client = build_client(args)
    try:
        roundtrip_client.set_community_credentials_from_cookie_string(cookie_string)
        info = roundtrip_client.community.get_account_info()
        return "steamid={0} logged_in={1}".format(
            info.get("steamid", "<unknown>"),
            info.get("logged_in", False),
        )
    finally:
        roundtrip_client.close()


def _capture_result(cache: dict, key: str, fetcher, formatter=str) -> str:
    value = fetcher()
    cache[key] = value
    return formatter(value)


def _format_privacy_roundtrip(client: SteamClient, privacy: dict) -> str:
    settings = privacy.get("PrivacySettings", {})
    response = client.community.set_profile_privacy(
        privacy_profile=settings.get("PrivacyProfile", 1),
        privacy_inventory=settings.get("PrivacyInventory", 1),
        privacy_inventory_gifts=settings.get("PrivacyInventoryGifts", 1),
        privacy_owned_games=settings.get("PrivacyOwnedGames", 1),
        privacy_playtime=settings.get("PrivacyPlaytime", 1),
        privacy_friends_list=settings.get("PrivacyFriendsList", 1),
        comment_permission=privacy.get("eCommentPermission", 0),
    )
    return str(response)


def _expect_limited_group_creation_denial(client: SteamClient) -> str:
    suffix = str(int(time.time()))
    try:
        client.groups.create_group(
            name="steamcommunitykit-{0}".format(suffix),
            abbreviation="sk{0}".format(suffix[-6:]),
            group_url="steamcommunitykit-{0}".format(suffix),
            validate_availability=False,
            wait_for_sync=0.0,
        )
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if "does not meet the requirements" in message.lower():
            return "limited-account denial confirmed"
        raise
    raise AssertionError("Expected Steam to reject group creation for a limited account.")


def _capture_profile_bundle(cache: dict, client: SteamClient) -> str:
    bundle = client.get_community_profile_bundle()
    cache["profile_bundle"] = bundle
    cache["account_info"] = bundle["account_info"]
    cache["profile_edit_state"] = bundle["profile_edit_state"]
    cache["profile_privacy"] = bundle["privacy"]
    return "steamid={0} persona={1}".format(
        bundle["account_info"].get("steamid", "<unknown>"),
        bundle["profile_edit_state"].get("strPersonaName", ""),
    )


def _require_cached(cache: dict, key: str):
    if key not in cache:
        raise RuntimeError("Expected cached community profile data for {0}.".format(key))
    return cache[key]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SteamCommunityKit smoke test for both public API-key flows and logged-in community flows."
    )
    parser.add_argument("--api-json", type=Path, help="Path to api.json containing API_KEY.")
    parser.add_argument("--api-key", help="Steam Web API key.")
    parser.add_argument("--username", help="Steam username for community login.")
    parser.add_argument("--password", help="Steam password for community login.")
    parser.add_argument("--steam-guard-code", help="Steam Guard code to use for credential login.")
    parser.add_argument(
        "--no-prompt-steam-guard",
        action="store_true",
        help="Do not prompt for a Steam Guard code when Steam requests one.",
    )
    parser.add_argument("--refresh-token", help="Steam refresh token for community login reuse.")
    parser.add_argument("--cookie-string", help="Community cookie string: sessionid=...; steamLoginSecure=...")
    parser.add_argument("--steam-id", default=DEFAULT_STEAM_ID, help="SteamID64 used for public API tests.")
    parser.add_argument(
        "--profile-identifier",
        default=DEFAULT_VANITY,
        help="SteamID64, vanity name, /profiles/... URL, or /id/... URL.",
    )
    parser.add_argument("--vanity", default=DEFAULT_VANITY, help="Vanity name used in resolution tests.")
    parser.add_argument("--app-id", type=int, default=DEFAULT_APP_ID, help="App ID used in game-related tests.")
    parser.add_argument("--market-app-id", type=int, default=730, help="App ID used in market tests.")
    parser.add_argument(
        "--market-hash-name",
        default=DEFAULT_MARKET_ITEM,
        help="Market hash name used for market price and listing tests.",
    )
    parser.add_argument(
        "--market-query",
        default="AK-47",
        help="Query string used for market search tests.",
    )
    parser.add_argument(
        "--inventory-app-id",
        type=int,
        default=DEFAULT_INVENTORY_APP_ID,
        help="App ID used for logged-in inventory tests.",
    )
    parser.add_argument(
        "--inventory-context-id",
        type=int,
        default=DEFAULT_INVENTORY_CONTEXT_ID,
        help="Context ID used for logged-in inventory tests.",
    )
    parser.add_argument(
        "--inventory-count",
        type=int,
        default=2000,
        help="Per-page inventory request count used for inventory tests.",
    )
    parser.add_argument(
        "--group-url",
        default=DEFAULT_GROUP_URL,
        help="Public group URL slug used for group read tests.",
    )
    parser.add_argument(
        "--large-group-url",
        default=DEFAULT_LARGE_GROUP_URL,
        help="Larger public group URL slug used for multi-page group member tests.",
    )
    parser.add_argument(
        "--editable-group-url",
        help="Group URL slug for a group the logged-in account can edit, used for fetch_group_id tests.",
    )
    parser.add_argument(
        "--published-file-id",
        default=DEFAULT_PUBLISHED_FILE_ID,
        help="Published file ID used for workshop/remote storage reads.",
    )
    parser.add_argument(
        "--group-name-check",
        default=DEFAULT_GROUP_NAME_CHECK,
        help="Name and URL slug used for group availability checks.",
    )
    parser.add_argument(
        "--group-tag-check",
        default="sckit1",
        help="Tag used for group abbreviation availability checks.",
    )
    parser.add_argument(
        "--community-only",
        action="store_true",
        help="Skip public API tests and only run community/session tests.",
    )
    parser.add_argument(
        "--public-only",
        action="store_true",
        help="Skip community/session tests even if login details are provided.",
    )
    parser.add_argument(
        "--write-checks",
        action="store_true",
        help="Run safe-ish write checks like profile edit using the current persona name.",
    )
    parser.add_argument("--set-persona-name", help="Optional persona name to set during write checks.")
    parser.add_argument("--set-custom-url", help="Optional custom profile URL slug to set during write checks.")
    parser.add_argument("--set-real-name", help="Optional real name to set during write checks.")
    parser.add_argument("--set-summary", help="Optional profile summary to set during write checks.")
    parser.add_argument(
        "--rotate-trade-url",
        action="store_true",
        help="Actually rotate the account's trade offer URL token.",
    )
    parser.add_argument(
        "--avatar-image",
        type=Path,
        help="Path to an image file used for an optional avatar upload write test.",
    )
    parser.add_argument(
        "--include-conditional",
        action="store_true",
        help="Include Steam-dependent checks that often fail due profile privacy or key restrictions.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = build_client(args)
    try:
        if not args.community_only and client.api_key:
            run_public_suite(client, args)
        elif not args.community_only:
            run_no_key_public_suite(client, args)

        if not args.public_only:
            try:
                has_community_session = configure_community_session(client, args)
            except Exception as exc:  # noqa: BLE001
                print_header("Community / Logged-In Tests")
                print_result("Community Login", False, "{0}: {1}".format(type(exc).__name__, exc))
                return 1
            if has_community_session:
                run_community_suite(client, args)
            else:
                print_header("Community / Logged-In Tests")
                print("Skipped community tests. Provide one of:")
                print("  --username + --password")
                print("  --refresh-token")
                print("  --cookie-string")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
