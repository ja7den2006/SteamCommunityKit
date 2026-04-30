from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from steamcommunitykit import (  # noqa: E402
    SteamClient,
    SteamError,
    build_group_url,
    build_market_listing_url,
    build_steam_profile_url,
    build_workshop_file_url,
    parse_group_url,
    parse_market_listing_url,
    parse_steam_profile_url,
    parse_workshop_file_url,
)


DEFAULT_STEAM_ID = "76561197960435530"
DEFAULT_VANITY = "gaben"
DEFAULT_APP_ID = 570
DEFAULT_GROUP_URL = "valve"
DEFAULT_LARGE_GROUP_URL = "steamdb"
DEFAULT_PUBLISHED_FILE_ID = "2682416130"
DEFAULT_COLLECTION_FILE_ID = "3210489689"
DEFAULT_GROUP_NAME_CHECK = "steamcommunitykit-smoke-check"
DEFAULT_MARKET_ITEM = "AK-47 | Redline (Field-Tested)"
DEFAULT_INVENTORY_APP_ID = 753
DEFAULT_INVENTORY_CONTEXT_ID = 6
DEFAULT_STORE_SEARCH_QUERY = "Counter-Strike"


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
    collection_cache = {}

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
        "Get Friend IDs",
        lambda: "friend_ids={0}".format(
            len(client.get_friend_ids_for_user(args.profile_identifier))
        ),
    )
    run_check(
        "Get Friend Summaries",
        lambda: _format_friend_summaries(
            client.get_friend_summaries_for_user(args.profile_identifier, limit=5)
        ),
    )
    run_check(
        "Get User Group List",
        lambda: "groups={0}".format(
            len(client.get_user_group_list_for_user(args.profile_identifier).get("groups", []))
        ),
    )
    run_check(
        "Get User Group IDs",
        lambda: "group_ids={0}".format(
            len(client.get_user_group_ids_for_user(args.profile_identifier))
        ),
    )
    run_check(
        "Get Player Summaries Map",
        lambda: "mapped_players={0}".format(
            len(client.get_player_summaries_map([args.steam_id, client.resolve_steam_id(args.vanity)]))
        ),
    )
    run_check(
        "Get Player Bans Summary",
        lambda: _format_player_bans_summary(
            client.get_player_bans_summary(client.get_friend_ids_for_user(args.profile_identifier)[:5])
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
        "Get Owned Games Summary",
        lambda: _format_game_summary(
            client.get_owned_games_summary_for_user(args.profile_identifier, include_appinfo=True)
        ),
    )
    run_check(
        "Find Owned Game",
        lambda: _format_found_games(
            client.find_owned_game_for_user(args.profile_identifier, app_id=args.app_id, include_appinfo=True)
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
        "Get Recently Played Games Summary",
        lambda: _format_game_summary(
            client.get_recently_played_games_summary_for_user(args.profile_identifier)
        ),
    )
    run_check(
        "Find Recently Played Game",
        lambda: _format_found_games(
            client.find_recently_played_game_for_user(args.profile_identifier, app_id=args.app_id)
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
        "Get Badges Summary",
        lambda: _format_badges_summary(client.get_badges_summary_for_user(args.profile_identifier)),
    )
    run_check(
        "Get Community Badge Progress",
        lambda: "quests={0}".format(
            len(client.get_community_badge_progress_for_user(args.profile_identifier, 1).get("quests", []))
        ),
    )
    run_check(
        "Get Community Badge Progress Summary",
        lambda: _format_badge_progress_summary(
            client.get_community_badge_progress_summary_for_user(args.profile_identifier, 1)
        ),
    )
    run_check(
        "Get Servers At Address",
        lambda: "servers={0}".format(
            len(client.get_servers_at_address("208.64.200.0").get("response", {}).get("servers", []))
        ),
    )
    run_check(
        "Up To Date Check",
        lambda: str(client.up_to_date_check(args.app_id, 0).get("up_to_date")),
    )
    run_check(
        "Get App Details",
        lambda: _format_app_details(client.get_app_details(args.app_id)),
    )
    run_check(
        "Get App Details Many",
        lambda: _format_app_details_many(client.get_app_details_many([args.app_id, 730])),
    )
    run_check(
        "Get News For App",
        lambda: "newsitems={0}".format(
            len(client.get_news_for_app(args.app_id, count=1).get("appnews", {}).get("newsitems", []))
        ),
    )
    run_check(
        "Get News Summary",
        lambda: _format_news_summary(client.get_news_summary(args.app_id, count=2)),
    )
    run_check(
        "Get Number Of Current Players",
        lambda: str(client.get_number_of_current_players(args.app_id).get("player_count", 0)),
    )
    run_check(
        "Get Global Achievement Percentages",
        lambda: "achievements={0}".format(
            len(
                client.get_global_achievement_percentages_for_app(args.app_id).get(
                    "achievementpercentages", {}
                ).get("achievements", [])
            )
        ),
    )
    run_check(
        "Get Global Achievement Percentages Map",
        lambda: _format_global_achievement_map(client.get_global_achievement_percentages_map(args.app_id)),
    )
    run_check(
        "Get Schema For Game",
        lambda: "gameName={0}".format(
            client.get_schema_for_game(args.app_id).get("game", {}).get("gameName", "<unknown>")
        ),
    )
    run_check(
        "Get Schema For Game Summary",
        lambda: _format_schema_summary(client.get_schema_for_game_summary(args.app_id)),
    )
    run_check(
        "Get Global Stats For Game",
        lambda: "globalstats_keys={0}".format(
            sorted(
                client.get_global_stats_for_game(
                    args.app_id,
                    ["total_kills"],
                ).keys()
            )
        ),
    )
    run_check(
        "Get Global Stats For Game Summary",
        lambda: _format_global_stats_summary(
            client.get_global_stats_for_game_summary(
                args.app_id,
                ["total_kills"],
            )
        ),
    )
    run_check(
        "Get Trade Offers Summary",
        lambda: "pending_received={0}".format(
            client.get_trade_offers_summary().get("pending_received_count", 0)
        ),
    )
    run_check(
        "Get Trade Offer Totals",
        lambda: _format_trade_offer_totals(client.get_trade_offer_totals()),
    )
    run_check(
        "Get Trade Offers",
        lambda: _format_trade_offers(
            client.get_trade_offers(
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
        "Get Trade Offers Summary View",
        lambda: _format_trade_offers_summary_view(client.get_trade_offers_summary_view()),
    )
    run_check(
        "Get Trade History",
        lambda: _format_trade_history(
            client.get_trade_history(
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
        "Get Trade History Summary",
        lambda: _format_trade_history_summary(client.get_trade_history_summary(max_trades=10)),
    )
    run_check(
        "Get Store App List",
        lambda: "apps={0}".format(
            len(client.store.get_app_list(include_games=True).get("apps", []))
        ),
    )
    run_check(
        "Search Store Apps",
        lambda: _format_store_app_search(
            client.search_store_apps(args.store_search_query, max_results=3, include_games=True)
        ),
    )
    run_check(
        "Find Store App",
        lambda: _format_store_app_find(
            client.find_store_app(args.store_search_query, prefer_exact=False, include_games=True)
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
        "Get Published File Details Batch",
        lambda: _format_published_file_details_batch(
            client.get_published_file_details(
                [_require_workshop_item_id(workshop_cache, args), args.collection_published_file_id]
            )
        ),
    )
    run_check(
        "Get Published File Detail From URL",
        lambda: _format_published_file_detail(
            client.get_published_file_detail(
                build_workshop_file_url(_require_workshop_item_id(workshop_cache, args))
            )
        ),
    )
    run_check(
        "Get Collection Details",
        lambda: _format_collection_details(client.get_collection_details([args.collection_published_file_id])),
    )
    run_check(
        "Get Collection Details Map",
        lambda: _format_collection_details_map(
            client.get_collection_details_map([args.collection_published_file_id])
        ),
    )
    run_check(
        "Get Collection Detail",
        lambda: _format_collection_detail(client.get_collection_detail(args.collection_published_file_id)),
    )
    run_check(
        "Get Collection Child Details",
        lambda: _format_collection_children(client.get_collection_child_details(args.collection_published_file_id)),
    )
    run_check(
        "Get Collection Child Map",
        lambda: _capture_result(
            collection_cache,
            "child_map",
            lambda: client.get_collection_child_map(args.collection_published_file_id),
            _format_collection_child_map,
        ),
    )
    run_check(
        "Find Collection Child",
        lambda: _format_collection_child_find(
            _find_cached_collection_child(client, collection_cache, args)
        ),
    )
    run_check(
        "Find Published File",
        lambda: _format_published_file_find(
            _find_cached_published_file(client, workshop_cache, args)
        ),
    )
    run_check(
        "Profile URL Helpers",
        lambda: _format_profile_url_helper(
            parse_steam_profile_url(build_steam_profile_url(vanity=args.vanity))
        ),
    )
    run_check(
        "Group URL Helpers",
        lambda: _format_group_url_helper(
            parse_group_url(build_group_url(args.group_url))
        ),
    )
    run_check(
        "Workshop URL Helpers",
        lambda: _format_workshop_url_helper(
            parse_workshop_file_url(
                build_workshop_file_url(_require_workshop_item_id(workshop_cache, args))
            )
        ),
    )
    run_check(
        "Market Listing URL Helpers",
        lambda: _format_market_url_helper(
            parse_market_listing_url(
                build_market_listing_url(args.market_app_id, args.market_hash_name)
            )
        ),
    )
    run_check(
        "Get Web API Server Info",
        lambda: str(client.get_web_api_server_info()),
    )
    run_check(
        "Get Supported API List",
        lambda: "interfaces={0}".format(
            len(client.get_supported_api_list().get("apilist", {}).get("interfaces", []))
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
                    client.get_news_for_app_authed(args.app_id, count=1).get(
                        "appnews", {}
                    ).get("newsitems", [])
                )
            ),
        )
        run_check(
            "Get Player Achievements",
            lambda: "playerstats_keys={0}".format(
                sorted(
                    client.get_player_achievements_for_user(
                        args.profile_identifier,
                        args.app_id,
                    ).keys()
                )
            ),
        )
        run_check(
            "Get Player Achievements Summary",
            lambda: _format_player_achievement_summary(
                client.get_player_achievements_summary_for_user(
                    args.profile_identifier,
                    args.app_id,
                )
            ),
        )
        run_check(
            "Get User Stats For Game",
            lambda: "playerstats_keys={0}".format(
                sorted(
                    client.get_user_stats_for_game_for_user(
                        args.profile_identifier,
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
        lambda: str(client.get_market_price_overview(args.market_app_id, args.market_hash_name)),
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
        "Find Market Item",
        lambda: _format_market_find(
            client.find_market_item(
                args.market_hash_name,
                app_id=args.market_app_id,
                count=20,
                max_pages=5,
                max_results=100,
                market_hash_name=args.market_hash_name,
            )
        ),
    )
    run_check(
        "Market Item Name ID",
        lambda: str(client.get_market_item_name_id(args.market_app_id, args.market_hash_name)),
    )
    run_check(
        "Market Price History",
        lambda: "points={0}".format(
            len(client.get_market_price_history(args.market_app_id, args.market_hash_name).get("prices", []))
        ),
    )
    run_check(
        "Market Price History Summary",
        lambda: _format_market_price_history_summary(
            client.get_market_price_history_summary(args.market_app_id, args.market_hash_name)
        ),
    )
    run_check(
        "Market Orders Histogram",
        lambda: "success={0}".format(
            client.get_market_item_orders_histogram(
                app_id=args.market_app_id,
                market_hash_name=args.market_hash_name,
            ).get("success")
        ),
    )
    run_check(
        "Market Orders Histogram By URL",
        lambda: "success={0}".format(
            client.get_market_item_orders_histogram_by_url(
                build_market_listing_url(args.market_app_id, args.market_hash_name)
            ).get("success")
        ),
    )
    run_check(
        "Market Orders Summary",
        lambda: _format_market_orders_summary(
            client.get_market_item_orders_summary(
                app_id=args.market_app_id,
                market_hash_name=args.market_hash_name,
            )
        ),
    )
    run_check(
        "Market Orders Summary By URL",
        lambda: _format_market_orders_summary(
            client.get_market_item_orders_summary_by_url(
                build_market_listing_url(args.market_app_id, args.market_hash_name)
            )
        ),
    )
    run_check(
        "Market Price Snapshot",
        lambda: _format_market_price_snapshot(
            client.get_market_price_snapshot(
                args.market_app_id,
                args.market_hash_name,
                listings_count=10,
            )
        ),
    )
    run_check(
        "Market Price Snapshot By URL",
        lambda: _format_market_price_snapshot(
            client.get_market_price_snapshot_by_url(
                build_market_listing_url(args.market_app_id, args.market_hash_name),
                listings_count=10,
            )
        ),
    )
    run_check(
        "Market Listings Summary",
        lambda: _format_market_listings_summary(
            client.get_market_item_listings_summary(
                args.market_app_id,
                args.market_hash_name,
                count=10,
            )
        ),
    )
    run_check(
        "Market Listings Multi-Page",
        lambda: _format_market_listings_summary(
            client.get_all_market_item_listings_summary(
                args.market_app_id,
                args.market_hash_name,
                count=10,
                max_pages=2,
                max_listings=15,
            )
        ),
    )
    run_check(
        "Market Listings Multi-Page By URL",
        lambda: _format_market_listings_summary(
            client.get_all_market_item_listings_summary_by_url(
                build_market_listing_url(args.market_app_id, args.market_hash_name),
                count=10,
                max_pages=2,
                max_listings=15,
            )
        ),
    )
    run_check(
        "Find Market Listings",
        lambda: _format_found_market_listings(
            client.find_market_item_listings(
                args.market_app_id,
                args.market_hash_name,
                count=10,
                max_pages=2,
                max_listings=15,
                max_price=5000,
            )
        ),
    )
    run_check(
        "Find Market Listings By URL",
        lambda: _format_found_market_listings(
            client.find_market_item_listings_by_url(
                build_market_listing_url(args.market_app_id, args.market_hash_name),
                count=10,
                max_pages=2,
                max_listings=15,
                max_price=5000,
            )
        ),
    )
    run_check(
        "Fetch Group ID64 (Public)",
        lambda: client.get_group_id64(args.group_url),
    )
    run_check(
        "Get Group Details From URL (Public)",
        lambda: _format_group_details(
            client.get_group_details(build_group_url(args.group_url))
        ),
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
        lambda: str(_capture_result(cache, "account_info", client.get_account_info, lambda value: value)),
    )
    run_check(
        "Get Profile Edit State",
        lambda: "persona={0}".format(
            _capture_result(cache, "profile_edit_state", client.get_profile_edit_state, lambda value: value).get(
                "strPersonaName",
                "",
            )
        ),
    )
    run_check(
        "Get Profile Privacy",
        lambda: str(_capture_result(cache, "profile_privacy", client.get_profile_privacy, lambda value: value)),
    )
    run_check(
        "Get Trade Offer URL",
        lambda: _capture_result(cache, "trade_offer_url", client.get_trade_offer_url, str),
    )
    run_check(
        "Get Web API Key Status",
        lambda: _capture_result(cache, "web_api_key_status", client.get_web_api_key_status, str),
    )
    run_check(
        "Get Web API Key Page State",
        lambda: _format_web_api_key_page_state(client.get_web_api_key_page_state()),
    )
    run_check(
        "Fetch Group ID64",
        lambda: str(client.get_group_id64(args.group_url)),
    )
    run_check(
        "Check Group Name Availability",
        lambda: str(client.check_group_name_availability(args.group_name_check)),
    )
    run_check(
        "Check Group URL Availability",
        lambda: str(client.check_group_url_availability(args.group_name_check)),
    )
    run_check(
        "Check Group Tag Availability",
        lambda: str(client.check_group_tag_availability(args.group_tag_check)),
    )
    run_check(
        "Get Group Details",
        lambda: str(client.get_group_details(args.group_url)),
    )
    run_check(
        "Get Group Members",
        lambda: "members={0}".format(len(client.get_group_members(args.group_url).get("members", []))),
    )
    run_check(
        "Get Group Member Summaries",
        lambda: _format_group_member_summaries(client.get_group_member_summaries(args.group_url, limit=5)),
    )
    if client.api_key:
        run_check(
            "Get Friend Bans",
            lambda: _format_player_bans_summary(client.get_friend_bans_for_user(args.profile_identifier, limit=5)),
        )
    else:
        print_result("Get Friend Bans", True, "skipped: requires Steam Web API key")
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
    run_check(
        "Get Own Inventory Summary",
        lambda: _format_inventory_summary(
            client.get_inventory_items_summary_for_user(
                _require_cached(cache, "account_info").get("steamid"),
                args.inventory_app_id,
                args.inventory_context_id,
                count=args.inventory_count,
            )
        ),
    )
    run_check(
        "Get Own Inventory Item Counts",
        lambda: _format_inventory_counts(
            client.get_inventory_item_counts_for_user(
                _require_cached(cache, "account_info").get("steamid"),
                args.inventory_app_id,
                args.inventory_context_id,
                count=args.inventory_count,
            )
        ),
    )
    run_check(
        "Find Own Inventory Items",
        lambda: _format_inventory_find(
            client.find_inventory_items_for_user(
                _require_cached(cache, "account_info").get("steamid"),
                args.inventory_app_id,
                args.inventory_context_id,
                count=args.inventory_count,
                tradable=True,
            )
        ),
    )
    run_check(
        "Get Own Full Inventory Summary",
        lambda: _format_inventory_items(
            client.get_full_inventory_items_summary_for_user(
                _require_cached(cache, "account_info").get("steamid"),
                args.inventory_app_id,
                args.inventory_context_id,
                count=args.inventory_count,
                max_pages=2,
            )
        ),
    )
    run_check(
        "Get Own Full Inventory Item Counts",
        lambda: _format_inventory_counts(
            client.get_full_inventory_item_counts_for_user(
                _require_cached(cache, "account_info").get("steamid"),
                args.inventory_app_id,
                args.inventory_context_id,
                count=args.inventory_count,
                max_pages=2,
            )
        ),
    )
    run_check(
        "Find Own Full Inventory Items",
        lambda: _format_inventory_find(
            client.find_full_inventory_items_for_user(
                _require_cached(cache, "account_info").get("steamid"),
                args.inventory_app_id,
                args.inventory_context_id,
                count=args.inventory_count,
                max_pages=2,
                tradable=True,
            )
        ),
    )

    if args.editable_group_url:
        run_check(
            "Fetch Editable Group ID",
            lambda: str(client.get_group_id(args.editable_group_url)),
        )

    if args.write_checks:
        run_check(
            "Write Check: Edit Profile With Current Persona",
            lambda: str(
                client.edit_profile(
                    persona_name=(cache.get("profile_edit_state") or client.get_profile_edit_state()).get(
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
                cache.get("profile_privacy") or client.get_profile_privacy(),
            ),
        )
        if args.set_persona_name:
            run_check(
                "Write Check: Set Persona Name",
                lambda: str(client.update_persona_name(args.set_persona_name)),
            )
        if args.set_custom_url:
            run_check(
                "Write Check: Set Custom URL",
                lambda: str(client.update_custom_url(args.set_custom_url)),
            )
        if args.set_real_name:
            run_check(
                "Write Check: Set Real Name",
                lambda: str(client.update_real_name(args.set_real_name)),
            )
        if args.set_summary:
            run_check(
                "Write Check: Set Summary",
                lambda: str(client.update_summary(args.set_summary)),
            )

    if args.rotate_trade_url:
        run_check(
            "Write Check: Rotate Trade URL",
            lambda: str(client.rotate_trade_offer_url()),
        )

    if args.write_checks and (cache.get("account_info") or client.get_account_info()).get("is_limited"):
        run_check(
            "Expected Denial: Limited Account Group Creation",
            lambda: _expect_limited_group_creation_denial(client),
        )

    if args.write_checks and args.avatar_image:
        run_check(
            "Write Check: Upload Avatar",
            lambda: str(client.upload_avatar(args.avatar_image)),
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


def _format_trade_offer_totals(payload: dict) -> str:
    return "pending_received={0} new_received={1} historical_received={2}".format(
        payload.get("pending_received_count"),
        payload.get("new_received_count"),
        payload.get("historical_received_count"),
    )


def _format_trade_offers_summary_view(payload: dict) -> str:
    return "sent={0} received={1} descriptions={2} next_cursor={3}".format(
        payload.get("sent_count"),
        payload.get("received_count"),
        payload.get("description_count"),
        payload.get("next_cursor"),
    )


def _format_trade_history_summary(payload: dict) -> str:
    first = payload.get("trades", [None])[0] if payload.get("trades") else None
    first_trade_id = first.get("trade_id") if first else None
    return "trades={0} total={1} first_trade_id={2} more={3}".format(
        payload.get("trade_count"),
        payload.get("total_trades"),
        first_trade_id,
        payload.get("more"),
    )


def _format_app_details(payload: dict) -> str:
    return "name={0} type={1} free={2}".format(
        payload.get("name", ""),
        payload.get("type", ""),
        payload.get("is_free"),
    )


def _format_news_summary(payload: dict) -> str:
    items = payload.get("items", [])
    first_title = items[0]["title"] if items else "<none>"
    return "items={0} first={1}".format(len(items), first_title)


def _format_store_app_search(payload: dict) -> str:
    matches = payload.get("matches", [])
    first_name = matches[0]["name"] if matches else "<none>"
    return "matches={0} first={1}".format(payload.get("count"), first_name)


def _format_store_app_find(payload: dict) -> str:
    match = payload.get("match") or {}
    return "matched={0} exact={1} app_id={2}".format(
        match.get("name", "<none>"),
        payload.get("matched_exactly"),
        match.get("app_id"),
    )


def _format_friend_summaries(payload: dict) -> str:
    friends = payload.get("friends", [])
    first_name = friends[0]["personaname"] if friends else "<none>"
    return "friends={0} first={1}".format(len(friends), first_name)


def _format_player_bans_summary(payload: list) -> str:
    vac_banned = sum(1 for item in payload if item.get("vac_banned"))
    return "players={0} vac_banned={1}".format(len(payload), vac_banned)


def _format_game_summary(payload: dict) -> str:
    games = payload.get("games", [])
    first_name = games[0].get("name") if games and games[0].get("name") else "<none>"
    count = payload.get("game_count")
    if count is None:
        count = payload.get("total_count")
    if count is None:
        count = "unavailable"
    return "count={0} first={1}".format(count, first_name)


def _format_found_games(payload: dict) -> str:
    games = payload.get("games", [])
    first_name = games[0].get("name") if games and games[0].get("name") else "<none>"
    return "matches={0} first={1}".format(payload.get("count"), first_name)


def _format_badges_summary(payload: dict) -> str:
    badges = payload.get("badges", [])
    first_badge_id = badges[0].get("badge_id") if badges else None
    return "badges={0} player_level={1} first_badge_id={2}".format(
        payload.get("badge_count"),
        payload.get("player_level"),
        first_badge_id,
    )


def _format_badge_progress_summary(payload: dict) -> str:
    return "quests={0} completed={1}".format(
        payload.get("quest_count"),
        payload.get("completed_count"),
    )


def _format_app_details_many(payload: list) -> str:
    first_name = payload[0].get("name") if payload else "<none>"
    return "apps={0} first={1}".format(len(payload), first_name)


def _format_global_achievement_map(payload: dict) -> str:
    achievements = payload.get("achievements", [])
    first_name = achievements[0].get("name") if achievements else "<none>"
    return "achievements={0} first={1}".format(payload.get("achievement_count"), first_name)


def _format_schema_summary(payload: dict) -> str:
    return "game={0} achievements={1} stats={2}".format(
        payload.get("game_name", "<unknown>"),
        payload.get("achievement_count"),
        payload.get("stat_count"),
    )


def _format_global_stats_summary(payload: dict) -> str:
    stats = payload.get("stats", [])
    first = stats[0] if stats else {}
    return "stats={0} first={1} value={2}".format(
        len(stats),
        first.get("name"),
        first.get("value"),
    )


def _format_group_member_summaries(payload: dict) -> str:
    members = payload.get("members", [])
    first_name = members[0].get("personaname") if members else "<none>"
    return "members={0} first={1}".format(len(members), first_name)


def _format_group_details(payload: dict) -> str:
    return "group={0} members={1} online={2}".format(
        _safe_console_text(payload.get("group_name") or "<none>"),
        payload.get("member_count"),
        payload.get("members_online"),
    )


def _format_market_orders_summary(payload: dict) -> str:
    return "buy_rows={0} sell_rows={1} buy_summary={2}".format(
        len(payload.get("buy_orders", [])),
        len(payload.get("sell_orders", [])),
        payload.get("buy_order_summary", ""),
    )


def _format_market_price_snapshot(payload: dict) -> str:
    return "lowest={0} median={1} listings={2} cheapest={3}".format(
        payload.get("lowest_price_text"),
        payload.get("median_price_text"),
        payload.get("listing_count"),
        payload.get("cheapest_listing_price"),
    )


def _format_market_price_history_summary(payload: dict) -> str:
    return "points={0} latest={1} min={2} max={3}".format(
        payload.get("point_count"),
        payload.get("latest_price"),
        payload.get("min_price"),
        payload.get("max_price"),
    )


def _format_market_listings_summary(payload: dict) -> str:
    cheapest = payload.get("cheapest_listing") or {}
    cheapest_price = cheapest.get("converted_price") or cheapest.get("price")
    return "listings={0} total={1} cheapest={2}".format(
        len(payload.get("listings", [])),
        payload.get("total_count"),
        cheapest_price,
    )


def _format_found_market_listings(payload: dict) -> str:
    listings = payload.get("listings", [])
    first_price = None
    if listings:
        first_price = listings[0].get("converted_price") or listings[0].get("price")
    return "matches={0} first_price={1} pages={2}".format(
        payload.get("count"),
        first_price,
        payload.get("pages_fetched", 0),
    )


def _format_market_search_summary(payload: dict) -> str:
    items = payload.get("items", [])
    first_hash_name = items[0]["hash_name"] if items else "<none>"
    return "items={0} total={1} first={2}".format(
        len(items),
        payload.get("total_count"),
        first_hash_name,
    )


def _format_market_find(payload: dict) -> str:
    match = payload.get("match") or {}
    return "matched={0} exact={1}".format(
        _safe_console_text(match.get("market_hash_name") or match.get("name") or "<none>"),
        payload.get("matched_exactly"),
    )


def _format_inventory_items(payload: dict) -> str:
    return "items={0} total_inventory_count={1} pages={2}".format(
        len(payload.get("items", [])),
        payload.get("total_inventory_count"),
        payload.get("pages_fetched", 0),
    )


def _format_inventory_summary(payload: dict) -> str:
    items = payload.get("items", [])
    first_name = items[0].get("market_hash_name") or items[0].get("name") if items else "<none>"
    first_name = _safe_console_text(first_name)
    return "items={0} total_inventory_count={1} first={2}".format(
        len(items),
        payload.get("total_inventory_count"),
        first_name,
    )


def _format_inventory_find(payload: dict) -> str:
    items = payload.get("items", [])
    first_name = items[0].get("market_hash_name") or items[0].get("name") if items else "<none>"
    first_name = _safe_console_text(first_name)
    return "matches={0} first={1}".format(payload.get("count"), first_name)


def _format_inventory_counts(payload: dict) -> str:
    items = payload.get("items", [])
    first = items[0] if items else {}
    first_name = _safe_console_text(first.get("market_hash_name") or first.get("name") or "<none>")
    return "unique={0} first={1} count={2}".format(
        payload.get("unique_item_count", 0),
        first_name,
        first.get("count", 0),
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


def _find_cached_published_file(client: SteamClient, cache: dict, args) -> dict:
    payload = cache.get("query_published_files")
    if payload and payload.get("items"):
        title = payload["items"][0].get("title")
        if title:
            return client.find_published_file(
                query_type=0,
                title=title,
                app_id=args.app_id,
                max_pages=1,
                max_items=10,
                return_short_description=True,
            )
    return client.find_published_file(
        query_type=0,
        published_file_id=_require_workshop_item_id(cache, args),
        app_id=args.app_id,
        max_pages=1,
        max_items=10,
        return_short_description=True,
    )


def _find_cached_collection_child(client: SteamClient, cache: dict, args) -> dict:
    payload = cache.get("child_map")
    if payload and payload.get("children"):
        title = payload["children"][0].get("title")
        if title:
            return client.find_collection_child(
                args.collection_published_file_id,
                title=title,
            )
    return client.find_collection_child(
        args.collection_published_file_id,
        child_published_file_id=args.published_file_id,
    )


def _format_published_file_detail(payload: dict) -> str:
    return "title={0} app={1} subs={2}".format(
        payload.get("title", ""),
        payload.get("app_name") or payload.get("app_id"),
        payload.get("subscriptions"),
    )


def _format_published_file_details_batch(payload: dict) -> str:
    items = payload.get("items", [])
    first_title = items[0].get("title", "") if items else "<none>"
    first_title = _safe_console_text(first_title)
    return "items={0} first={1}".format(
        len(items),
        first_title,
    )


def _format_collection_details(payload: dict) -> str:
    collections = payload.get("collections", [])
    first_id = collections[0].get("published_file_id") if collections else "<none>"
    return "collections={0} first={1}".format(
        len(collections),
        first_id,
    )


def _format_collection_details_map(payload: dict) -> str:
    first_id = next(iter(payload), "<none>")
    return "collections={0} first={1}".format(len(payload), first_id)


def _format_collection_detail(payload: dict) -> str:
    return "collection={0} children={1}".format(
        payload.get("published_file_id"),
        payload.get("child_count"),
    )


def _format_collection_children(payload: dict) -> str:
    children = payload.get("children", [])
    first_title = children[0].get("title") if children else "<none>"
    first_title = _safe_console_text(first_title)
    return "children={0} first={1}".format(len(children), first_title)


def _format_collection_child_map(payload: dict) -> str:
    children_by_id = payload.get("children_by_id", {})
    first_child_id = next(iter(children_by_id), "<none>")
    return "children={0} first_id={1}".format(len(children_by_id), first_child_id)


def _format_collection_child_find(payload: dict) -> str:
    match = payload.get("match") or {}
    return "matched={0} exact={1} child_id={2}".format(
        _safe_console_text(match.get("title") or "<none>"),
        payload.get("matched_exactly"),
        match.get("published_file_id"),
    )


def _format_published_file_find(payload: dict) -> str:
    match = payload.get("match") or {}
    return "matched={0} exact={1} published_file_id={2}".format(
        _safe_console_text(match.get("title") or "<none>"),
        payload.get("matched_exactly"),
        match.get("published_file_id"),
    )


def _format_profile_url_helper(payload: dict) -> str:
    return "type={0} value={1}".format(
        payload.get("profile_type"),
        payload.get("value"),
    )


def _format_group_url_helper(payload: dict) -> str:
    return "group_slug={0}".format(payload.get("group_slug"))


def _format_workshop_url_helper(payload: dict) -> str:
    return "published_file_id={0}".format(payload.get("published_file_id"))


def _format_market_url_helper(payload: dict) -> str:
    return "app_id={0} hash={1}".format(
        payload.get("app_id"),
        _safe_console_text(payload.get("market_hash_name")),
    )


def _format_player_achievement_summary(payload: dict) -> str:
    return "achieved={0}/{1} completion={2}".format(
        payload.get("achieved_count"),
        payload.get("achievement_count"),
        payload.get("completion_percentage"),
    )


def _format_web_api_key_page_state(payload: dict) -> str:
    return "has_access={0} registration_form_visible={1} revoke_available={2} reason={3}".format(
        payload.get("has_access"),
        payload.get("registration_form_visible"),
        payload.get("revoke_available"),
        _safe_console_text(payload.get("reason", "")),
    )


def _safe_console_text(value) -> str:
    text = str(value)
    return text.encode("cp1252", errors="replace").decode("cp1252")


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
        info = roundtrip_client.get_account_info()
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
    response = client.set_profile_privacy(
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
        client.create_group(
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
        "--store-search-query",
        default=DEFAULT_STORE_SEARCH_QUERY,
        help="Query string used for keyed store app list search tests.",
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
        "--collection-published-file-id",
        default=DEFAULT_COLLECTION_FILE_ID,
        help="Workshop collection published file ID used for collection detail reads.",
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
