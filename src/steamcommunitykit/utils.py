from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Union

from steamcommunitykit.exceptions import SteamValidationError


def ensure_not_blank(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SteamValidationError(f"{field_name} must be a non-empty string.")
    return value.strip()


def validate_steam_id(steam_id: Union[str, int], field_name: str = "steam_id") -> str:
    value = str(steam_id).strip()
    if not value.isdigit():
        raise SteamValidationError(f"{field_name} must be a numeric SteamID64 string.")
    if len(value) < 17:
        raise SteamValidationError(f"{field_name} must be a SteamID64 value.")
    return value


def validate_app_id(app_id: Union[str, int], field_name: str = "app_id") -> int:
    try:
        value = int(app_id)
    except (TypeError, ValueError) as exc:
        raise SteamValidationError(f"{field_name} must be an integer.") from exc
    if value <= 0:
        raise SteamValidationError(f"{field_name} must be greater than zero.")
    return value


def validate_uint32(
    value: Union[str, int],
    field_name: str,
    *,
    allow_zero: bool = False,
) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise SteamValidationError(f"{field_name} must be an integer.") from exc
    if normalized < 0 or (normalized == 0 and not allow_zero):
        comparator = "greater than or equal to zero" if allow_zero else "greater than zero"
        raise SteamValidationError(f"{field_name} must be {comparator}.")
    return normalized


def validate_int32(value: Union[str, int], field_name: str) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise SteamValidationError(f"{field_name} must be an integer.") from exc
    minimum = -(2 ** 31)
    maximum = (2 ** 31) - 1
    if normalized < minimum or normalized > maximum:
        raise SteamValidationError(
            f"{field_name} must fit in the signed 32-bit integer range."
        )
    return normalized


def validate_uint64(
    value: Union[str, int],
    field_name: str,
    *,
    allow_zero: bool = False,
) -> str:
    normalized = str(value).strip()
    if not normalized.isdigit():
        raise SteamValidationError(f"{field_name} must be a numeric string or integer.")
    if int(normalized) < 0 or (int(normalized) == 0 and not allow_zero):
        comparator = "greater than or equal to zero" if allow_zero else "greater than zero"
        raise SteamValidationError(f"{field_name} must be {comparator}.")
    return normalized


def normalize_binary_value(value: Union[str, bytes, bytearray], field_name: str) -> str:
    if isinstance(value, (bytes, bytearray)):
        if not value:
            raise SteamValidationError(f"{field_name} cannot be empty.")
        return bytes(value).hex()
    return ensure_not_blank(value, field_name)


def normalize_steam_ids(
    steam_ids: Union[str, int, Iterable[Union[str, int]]]
) -> List[str]:
    if isinstance(steam_ids, (str, int)):
        return [validate_steam_id(steam_ids)]
    normalized = [validate_steam_id(item) for item in steam_ids]
    if not normalized:
        raise SteamValidationError("steam_ids cannot be empty.")
    return normalized


def normalize_app_ids(app_ids: Union[str, int, Iterable[Union[str, int]]]) -> List[int]:
    if isinstance(app_ids, (str, int)):
        return [validate_app_id(app_ids)]
    normalized = [validate_app_id(item) for item in app_ids]
    if not normalized:
        raise SteamValidationError("app_ids cannot be empty.")
    return normalized


def normalize_uint64_ids(
    values: Union[str, int, Iterable[Union[str, int]]],
    field_name: str,
) -> List[str]:
    if isinstance(values, (str, int)):
        return [validate_uint64(values, field_name)]
    normalized = [validate_uint64(value, field_name) for value in values]
    if not normalized:
        raise SteamValidationError("{0} cannot be empty.".format(field_name))
    return normalized


def load_api_key_from_json(path: Union[str, Path]) -> str:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        key = data["API_KEY"]
    except KeyError as exc:
        raise SteamValidationError("API json file is missing an API_KEY entry.") from exc
    return ensure_not_blank(key, "API_KEY")
