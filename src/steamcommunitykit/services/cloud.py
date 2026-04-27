from __future__ import annotations

import json
from typing import Iterable, Optional

from steamcommunitykit.constants import WEB_API_BASE_URL
from steamcommunitykit.exceptions import SteamValidationError
from steamcommunitykit.http import SteamHTTPTransport
from steamcommunitykit.utils import ensure_not_blank, validate_app_id, validate_uint32, validate_uint64


class CloudService:
    def __init__(self, transport: SteamHTTPTransport) -> None:
        self.transport = transport
        self.base_url = f"{WEB_API_BASE_URL}/ICloudService"

    def enumerate_user_files(
        self,
        access_token: str,
        app_id,
        *,
        extended_details: Optional[bool] = None,
        count: Optional[int] = None,
        start_index: Optional[int] = None,
    ) -> dict:
        params = {
            "access_token": ensure_not_blank(access_token, "access_token"),
            "appid": validate_app_id(app_id),
        }
        if extended_details is not None:
            params["extended_details"] = int(extended_details)
        if count is not None:
            params["count"] = validate_uint32(count, "count")
        if start_index is not None:
            params["start_index"] = validate_uint32(start_index, "start_index", allow_zero=True)
        return self.transport.request(
            "GET",
            f"{self.base_url}/EnumerateUserFiles/v1/",
            params=params,
        )

    def begin_app_upload_batch(
        self,
        access_token: str,
        app_id,
        machine_name: str,
        *,
        files_to_upload: Iterable[str],
        files_to_delete: Iterable[str],
    ) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/BeginAppUploadBatch/v1/",
            data=self._service_form(
                access_token,
                {
                    "appid": validate_app_id(app_id),
                    "machine_name": ensure_not_blank(machine_name, "machine_name"),
                    "files_to_upload": self._normalize_string_list(files_to_upload, "files_to_upload"),
                    "files_to_delete": self._normalize_string_list(files_to_delete, "files_to_delete"),
                },
            ),
        )

    def complete_app_upload_batch(
        self,
        access_token: str,
        app_id,
        batch_id,
        batch_eresult: int,
    ) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/CompleteAppUploadBatch/v1/",
            data=self._service_form(
                access_token,
                {
                    "appid": validate_app_id(app_id),
                    "batch_id": validate_uint64(batch_id, "batch_id"),
                    "batch_eresult": validate_uint32(batch_eresult, "batch_eresult"),
                },
            ),
        )

    def begin_http_upload(
        self,
        access_token: str,
        app_id,
        file_size: int,
        filename: str,
        file_sha: str,
        upload_batch_id,
        *,
        platforms_to_sync: Iterable[str],
        is_public: Optional[bool] = None,
    ) -> dict:
        payload = {
            "appid": validate_app_id(app_id),
            "file_size": validate_uint32(file_size, "file_size"),
            "filename": ensure_not_blank(filename, "filename"),
            "file_sha": self._validate_sha1(file_sha),
            "upload_batch_id": validate_uint64(upload_batch_id, "upload_batch_id"),
            "platforms_to_sync": self._normalize_string_list(platforms_to_sync, "platforms_to_sync"),
        }
        if is_public is not None:
            payload["is_public"] = bool(is_public)
        return self.transport.request(
            "POST",
            f"{self.base_url}/BeginHTTPUpload/v1/",
            data=self._service_form(access_token, payload),
        )

    def commit_http_upload(
        self,
        access_token: str,
        app_id,
        *,
        transfer_succeeded: bool,
        filename: str,
        file_sha: str,
    ) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/CommitHTTPUpload/v1/",
            data=self._service_form(
                access_token,
                {
                    "appid": validate_app_id(app_id),
                    "transfer_succeeded": bool(transfer_succeeded),
                    "filename": ensure_not_blank(filename, "filename"),
                    "file_sha": self._validate_sha1(file_sha),
                },
            ),
        )

    def delete(self, access_token: str, app_id, filename: str) -> dict:
        return self.transport.request(
            "POST",
            f"{self.base_url}/Delete/v1/",
            data=self._service_form(
                access_token,
                {
                    "appid": validate_app_id(app_id),
                    "filename": ensure_not_blank(filename, "filename"),
                },
            ),
        )

    @staticmethod
    def _service_form(access_token: str, payload: dict) -> dict:
        return {
            "access_token": ensure_not_blank(access_token, "access_token"),
            "input_json": json.dumps(payload, separators=(",", ":")),
        }

    @staticmethod
    def _normalize_string_list(values: Iterable[str], field_name: str) -> list:
        normalized = [ensure_not_blank(value, field_name) for value in values]
        return normalized

    @staticmethod
    def _validate_sha1(value: str) -> str:
        normalized = ensure_not_blank(value, "file_sha").lower()
        if len(normalized) != 40 or any(char not in "0123456789abcdef" for char in normalized):
            raise SteamValidationError("file_sha must be a 40-character SHA1 hex digest.")
        return normalized
