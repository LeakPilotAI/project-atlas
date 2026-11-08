import json
from types import SimpleNamespace

import pytest
from app.alerts.subscriptions import DiscordSubscriptionStore


@pytest.fixture(autouse=True)
def isolated_discord_import_defaults(monkeypatch, tmp_path):
    # The real disabled sender module constructs a subscription reader at import.
    # Keep that import in the fixture instead of reading an operational address file.
    monkeypatch.setattr(
        DiscordSubscriptionStore.__init__,
        "__defaults__",
        (tmp_path / "isolated-discord.json",),
    )


def test_subscription_store_starts_empty_and_persists_restart_state(tmp_path):
    path = tmp_path / "discord_subscribers.json"
    first = DiscordSubscriptionStore(path)

    assert first.reliable
    assert first.subscriber_ids == set()

    first.save({987654321, 123456789})
    restarted = DiscordSubscriptionStore(path)

    assert restarted.reliable
    assert restarted.subscriber_ids == {123456789, 987654321}
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "version": 1,
        "subscriber_ids": [123456789, 987654321],
    }


@pytest.mark.parametrize(
    "raw",
    [
        "{",
        "[]",
        '{"version":2,"subscriber_ids":[]}',
        '{"version":1,"subscriber_ids":"123"}',
        '{"version":1,"subscriber_ids":[0]}',
        '{"version":1,"subscriber_ids":[true]}',
        '{"version":true,"subscriber_ids":[]}',
        '{"version":1,"subscriber_ids":[123,123]}',
        '{"version":1,"subscriber_ids":[18446744073709551616]}',
    ],
)
def test_invalid_subscription_state_fails_closed_without_rewriting(tmp_path, raw):
    path = tmp_path / "discord_subscribers.json"
    path.write_text(raw, encoding="utf-8")
    store = DiscordSubscriptionStore(path)

    assert not store.reliable
    assert store.subscriber_ids == set()
    with pytest.raises(OSError, match="refusing to overwrite"):
        store.save({123456789})
    assert path.read_text(encoding="utf-8") == raw


def test_oversized_subscription_state_is_rejected_without_rewriting(tmp_path):
    path = tmp_path / "discord_subscribers.json"
    raw = " " * 65537
    path.write_text(raw, encoding="utf-8")
    store = DiscordSubscriptionStore(path)

    assert not store.reliable
    with pytest.raises(OSError, match="refusing to overwrite"):
        store.save({123456789})
    assert path.read_text(encoding="utf-8") == raw


def test_subscription_updates_are_persisted_before_memory_changes(
    tmp_path, monkeypatch
):
    import app.alerts.discord as discord_mod

    store = DiscordSubscriptionStore(tmp_path / "discord_subscribers.json")
    subscribers = set()
    monkeypatch.setattr(discord_mod, "_subscription_store", store)
    monkeypatch.setattr(discord_mod, "_subscribers", subscribers)

    assert discord_mod._change_subscription(123456789, subscribed=True)
    assert subscribers == {123456789}
    assert DiscordSubscriptionStore(store.path).subscriber_ids == {123456789}

    assert discord_mod._change_subscription(123456789, subscribed=False)
    assert subscribers == set()
    assert DiscordSubscriptionStore(store.path).subscriber_ids == set()


def test_failed_subscription_write_preserves_previous_memory_and_disk(
    tmp_path, monkeypatch
):
    import app.alerts.discord as discord_mod

    path = tmp_path / "discord_subscribers.json"
    store = DiscordSubscriptionStore(path)
    store.save({111111111})
    before = path.read_bytes()

    def fail_save(_subscriber_ids):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(store, "save", fail_save)
    subscribers = {111111111}
    monkeypatch.setattr(discord_mod, "_subscription_store", store)
    monkeypatch.setattr(discord_mod, "_subscribers", subscribers)

    assert not discord_mod._change_subscription(222222222, subscribed=True)
    assert subscribers == {111111111}
    assert path.read_bytes() == before
    assert not store.reliable


def test_failed_atomic_replace_keeps_prior_file_and_cleans_temporary_file(
    tmp_path, monkeypatch
):
    import app.alerts.subscriptions as subscription_mod

    path = tmp_path / "discord_subscribers.json"
    store = DiscordSubscriptionStore(path)
    store.save({111111111})
    before = path.read_bytes()

    def fail_replace(_source, _destination):
        raise OSError("simulated atomic replace failure")

    monkeypatch.setattr(subscription_mod.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated atomic replace failure"):
        store.save({222222222})

    assert path.read_bytes() == before
    assert list(tmp_path.glob(".discord_subscribers.json.*.tmp")) == []


def test_subscription_store_rejects_invalid_user_ids(tmp_path, monkeypatch):
    import app.alerts.discord as discord_mod

    store = DiscordSubscriptionStore(tmp_path / "discord_subscribers.json")
    subscribers = set()
    monkeypatch.setattr(discord_mod, "_subscription_store", store)
    monkeypatch.setattr(discord_mod, "_subscribers", subscribers)

    for invalid in (0, -1, True, "123", 18446744073709551616):
        with pytest.raises(ValueError):
            discord_mod._change_subscription(invalid, subscribed=True)
    assert subscribers == set()
    assert not store.path.exists()


@pytest.mark.asyncio
async def test_subscribe_command_reports_unreliable_store_without_claiming_success(
    tmp_path, monkeypatch
):
    import app.alerts.discord as discord_mod

    path = tmp_path / "discord_subscribers.json"
    path.write_text("{", encoding="utf-8")
    store = DiscordSubscriptionStore(path)
    subscribers = set()
    replies = []

    async def send_message(content, *, ephemeral):
        replies.append((content, ephemeral))

    interaction = SimpleNamespace(
        user=SimpleNamespace(id=123456789),
        response=SimpleNamespace(send_message=send_message),
    )
    monkeypatch.setattr(discord_mod, "_subscription_store", store)
    monkeypatch.setattr(discord_mod, "_subscribers", subscribers)

    await discord_mod.subscribe_cmd.callback(interaction)

    assert subscribers == set()
    assert len(replies) == 1
    assert "could not be saved" in replies[0][0]
    assert replies[0][1] is True
    assert path.read_text(encoding="utf-8") == "{"


def test_discord_diagnostics_exposes_subscription_store_reliability(monkeypatch):
    import ast
    from pathlib import Path
    from typing import Any

    import app.alerts.discord as discord_mod
    from app.core import config
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    # Execute the exact existing diagnostic handler in an isolated ASGI app,
    # without importing app.main or its legacy service/singleton startup graph.
    file = Path(__file__).resolve().parents[1] / "backend/app/api/diagnostics.py"
    tree = ast.parse(file.read_text(encoding="utf-8"))
    handler = next(
        n
        for n in tree.body
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "diagnostics_discord"
    )
    handler.decorator_list = []
    namespace = {"Any": Any, "Dict": dict}
    exec(  # noqa: S102 - exact tracked handler, no main/startup imports
        compile(ast.Module(body=[handler], type_ignores=[]), str(file), "exec"),
        namespace,
    )
    app = FastAPI()
    app.add_api_route(
        "/diagnostics/discord", namespace["diagnostics_discord"], methods=["GET"]
    )
    monkeypatch.setattr(
        config,
        "get_settings",
        lambda: SimpleNamespace(discord_token="", discord_owner_id_list=[]),
    )

    monkeypatch.setattr(discord_mod, "subscription_store_reliable", lambda: False)
    response = TestClient(app).get("/diagnostics/discord")

    assert response.status_code == 200
    assert response.json()["subscription_store_reliable"] is False
