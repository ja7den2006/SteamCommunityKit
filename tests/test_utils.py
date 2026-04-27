from pathlib import Path

import pytest

from steamcommunitykit.exceptions import SteamValidationError
from steamcommunitykit.utils import (
    load_api_key_from_json,
    normalize_binary_value,
    normalize_app_ids,
    normalize_steam_ids,
    normalize_uint64_ids,
    validate_app_id,
    validate_steam_id,
    validate_uint32,
    validate_uint64,
)


def test_validate_steam_id_accepts_steamid64() -> None:
    assert validate_steam_id("76561197960435530") == "76561197960435530"


def test_validate_steam_id_rejects_short_value() -> None:
    with pytest.raises(SteamValidationError):
        validate_steam_id("123")


def test_validate_app_id_rejects_non_positive_value() -> None:
    with pytest.raises(SteamValidationError):
        validate_app_id(0)


def test_normalize_steam_ids_handles_single_and_list_values() -> None:
    assert normalize_steam_ids("76561197960435530") == ["76561197960435530"]
    assert normalize_steam_ids(["76561197960435530", "76561197972495328"]) == [
        "76561197960435530",
        "76561197972495328",
    ]


def test_load_api_key_from_json_reads_expected_key(tmp_path: Path) -> None:
    file_path = tmp_path / "api.json"
    file_path.write_text('{"API_KEY":"abc123"}', encoding="utf-8")
    assert load_api_key_from_json(file_path) == "abc123"


def test_normalize_app_ids_handles_single_and_list_values() -> None:
    assert normalize_app_ids(440) == [440]
    assert normalize_app_ids(["440", 570]) == [440, 570]


def test_validate_uint64_and_normalize_uint64_ids() -> None:
    assert validate_uint64("123456789", "published_file_id") == "123456789"
    assert normalize_uint64_ids([123, "456"], "published_file_id") == ["123", "456"]


def test_validate_uint32_and_normalize_binary_value() -> None:
    assert validate_uint32("5", "count") == 5
    assert validate_uint32(0, "date_start", allow_zero=True) == 0
    assert normalize_binary_value(b"\xde\xad\xbe\xef", "session_key") == "deadbeef"
