import os

from ppe import fileio
from ppe.fileio import write_text_safely


def test_the_file_is_saved(tmp_path):
    target = tmp_path / "people.json"
    write_text_safely(target, "one")
    write_text_safely(target, "two")
    assert target.read_text(encoding="utf-8") == "two" and not (tmp_path / "people.tmp").exists()


def test_a_swap_that_is_refused_once_or_twice_is_retried(tmp_path, monkeypatch):
    target = tmp_path / "people.json"
    real, refused = os.replace, {"n": 0}

    def flaky(a, b):
        refused["n"] += 1
        if refused["n"] <= 2:
            raise PermissionError("Access is denied")
        return real(a, b)

    monkeypatch.setattr(fileio.os, "replace", flaky)
    monkeypatch.setattr(fileio.time, "sleep", lambda s: None)
    write_text_safely(target, "kept")
    assert target.read_text(encoding="utf-8") == "kept" and refused["n"] == 3


def test_a_swap_that_is_always_refused_still_saves_the_data(tmp_path, monkeypatch):
    target = tmp_path / "people.json"

    def always(a, b):
        raise PermissionError("Access is denied")

    monkeypatch.setattr(fileio.os, "replace", always)
    monkeypatch.setattr(fileio.time, "sleep", lambda s: None)
    write_text_safely(target, "still saved")
    assert target.read_text(encoding="utf-8") == "still saved"
