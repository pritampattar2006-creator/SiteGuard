import json

import pytest

from ppe.roles import Role, load_roles, usable_items


def write(tmp_path, payload):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_the_shipped_rules_file_loads_and_every_role_is_valid():
    roles = load_roles("config/ppe_rules.json")
    assert {"general_worker", "electrician", "welder", "site_supervisor"} <= set(roles)
    assert all(r.required for r in roles.values())


def test_roles_are_read_from_the_file_not_hard_coded(tmp_path):
    roles = load_roles(write(tmp_path, {"roles": {"diver": {"label": "Diver", "required": ["goggles"], "standards": ["X-1"]}}}))
    assert roles["diver"] == Role("diver", "Diver", ("goggles",), ("X-1",))


def test_unknown_equipment_is_rejected_with_a_clear_message(tmp_path):
    with pytest.raises(ValueError, match="unknown equipment"):
        load_roles(write(tmp_path, {"roles": {"x": {"required": ["jetpack"]}}}))


def test_a_role_with_no_required_items_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="at least one"):
        load_roles(write(tmp_path, {"roles": {"x": {"required": []}}}))


def test_missing_or_broken_files_give_plain_errors(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        load_roles(tmp_path / "nope.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_roles(bad)


def test_usable_items_separates_what_the_loaded_models_can_check():
    welder = Role("welder", "Welder", ("helmet", "goggles", "gloves", "boots"))
    assert usable_items(welder, ["helmet", "vest"]) == (("helmet",), ("goggles", "gloves", "boots"))
