import json

import pytest

from app.services.style_rules_service import MAX_RULES, StyleRuleNotFoundError, StyleRulesStore


@pytest.fixture
def path(tmp_path) -> str:
    return str(tmp_path / "style_rules.json")


@pytest.fixture
def store(path: str) -> StyleRulesStore:
    return StyleRulesStore(path)


def test_defaults_to_enabled_without_rules(store: StyleRulesStore):
    assert store.is_enabled() is True
    assert store.list_rules() == []
    assert store.active_rules() == []


def test_add_rule_persists_across_restart(path: str):
    store = StyleRulesStore(path)

    entry = store.add_rule("Duze den Empfänger.")

    assert entry is not None
    assert entry["text"] == "Duze den Empfänger."
    reloaded = StyleRulesStore(path)
    assert reloaded.active_rules() == ["Duze den Empfänger."]


def test_duplicate_rule_is_not_stored_twice(store: StyleRulesStore):
    store.add_rule("Duze den Empfänger.")

    duplicate = store.add_rule("  duze   den EMPFÄNGER. ")

    assert duplicate is None
    assert len(store.list_rules()) == 1


def test_oldest_rule_is_dropped_when_limit_is_reached(store: StyleRulesStore):
    for index in range(MAX_RULES + 2):
        store.add_rule(f"Regel {index}")

    texts = [rule["text"] for rule in store.list_rules()]
    assert len(texts) == MAX_RULES
    assert texts[0] == "Regel 2"
    assert texts[-1] == f"Regel {MAX_RULES + 1}"


def test_disabled_store_returns_no_active_rules_but_keeps_them(store: StyleRulesStore):
    store.add_rule("Halte dich kurz.")

    store.set_enabled(False)

    assert store.is_enabled() is False
    assert store.active_rules() == []
    assert len(store.list_rules()) == 1


def test_enabled_flag_survives_restart(path: str):
    StyleRulesStore(path).set_enabled(False)

    assert StyleRulesStore(path).is_enabled() is False


def test_delete_rule_removes_only_that_rule(store: StyleRulesStore):
    first = store.add_rule("Regel A")
    store.add_rule("Regel B")
    assert first is not None

    store.delete_rule(first["id"])

    assert store.active_rules() == ["Regel B"]


def test_delete_unknown_rule_raises(store: StyleRulesStore):
    with pytest.raises(StyleRuleNotFoundError):
        store.delete_rule("does-not-exist")


def test_clear_removes_all_rules(store: StyleRulesStore):
    store.add_rule("Regel A")
    store.add_rule("Regel B")

    store.clear()

    assert store.list_rules() == []


def test_corrupt_file_falls_back_to_empty_store(tmp_path):
    corrupt = tmp_path / "style_rules.json"
    corrupt.write_text("{ not valid json", encoding="utf-8")

    store = StyleRulesStore(str(corrupt))

    assert store.is_enabled() is True
    assert store.list_rules() == []


def test_file_contains_only_rule_text(path: str):
    StyleRulesStore(path).add_rule("Duze den Empfänger.")

    data = json.loads(open(path, encoding="utf-8").read())  # noqa: PTH123, SIM115
    assert set(data) == {"enabled", "rules"}
    assert set(data["rules"][0]) == {"id", "text"}
