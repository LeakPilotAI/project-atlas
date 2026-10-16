"""Durable local storage for explicit Discord DM subscriptions."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

DEFAULT_SUBSCRIPTION_PATH = Path(__file__).resolve().parents[2] / "data" / "discord_subscribers.json"
MAX_DISCORD_USER_ID = (1 << 64) - 1


def validate_discord_user_id(value: object) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
        or value > MAX_DISCORD_USER_ID
    ):
        raise ValueError("Discord user IDs must be unsigned 64-bit positive integers")
    return value


class DiscordSubscriptionStore:
    def __init__(self, path: Path = DEFAULT_SUBSCRIPTION_PATH) -> None:
        self.path = Path(path)
        self.subscriber_ids: set[int] = set()
        self.error: str | None = None
        try:
            self.subscriber_ids = self._read()
        except (OSError, RecursionError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self.error = f"{type(exc).__name__}: {str(exc)[:180]}"

    @property
    def reliable(self) -> bool:
        return self.error is None

    def _read(self) -> set[int]:
        if not self.path.exists():
            return set()
        raw = self.path.read_text(encoding="utf-8")
        if len(raw) > 65536:
            raise ValueError("Discord subscription file exceeds 64 KiB")
        document = json.loads(raw)
        if (
            not isinstance(document, dict)
            or type(document.get("version")) is not int
            or document["version"] != 1
        ):
            raise ValueError("unsupported Discord subscription file format")
        ids = document.get("subscriber_ids")
        if not isinstance(ids, list):
            raise TypeError("subscriber_ids must be a list")
        parsed: set[int] = set()
        for value in ids:
            user_id = validate_discord_user_id(value)
            if user_id in parsed:
                raise ValueError("subscriber IDs must be unique")
            parsed.add(user_id)
        return parsed

    def save(self, subscriber_ids: set[int]) -> None:
        if not self.reliable:
            raise OSError("Discord subscription state is unreliable; refusing to overwrite it")
        subscriber_ids = {validate_discord_user_id(value) for value in subscriber_ids}

        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
                newline="\n",
            ) as handle:
                temporary_path = Path(handle.name)
                json.dump(
                    {"version": 1, "subscriber_ids": sorted(subscriber_ids)},
                    handle,
                    separators=(",", ":"),
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
