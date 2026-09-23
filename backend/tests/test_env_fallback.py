"""Legacy NEO4J_* env fallback for Aura chain (TDD).

Fake values only — never real creds. Proves resolver priority:
AURA_* > NEO4J_CLOUD_* > NEO4J_* (legacy).
"""

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_index  # noqa: E402 - sys.path insert above is required to reach scripts/


FAKE_AURA_URI = "neo4j+s://fake-aura-host:7687"
FAKE_AURA_USER = "fake-aura-user"
FAKE_AURA_PASSWORD = "fake-aura-pass"
FAKE_AURA_DB = "fake-aura-db"

FAKE_CLOUD_URI = "neo4j+s://fake-cloud-host:7687"
FAKE_CLOUD_USER = "fake-cloud-user"
FAKE_CLOUD_PASSWORD = "fake-cloud-pass"
FAKE_CLOUD_DB = "fake-cloud-db"

FAKE_LEGACY_URI = "neo4j+s://fake-legacy-host:7687"
FAKE_LEGACY_USER = "fake-legacy-user"
FAKE_LEGACY_PASSWORD = "fake-legacy-pass"
FAKE_LEGACY_DB = "fake-legacy-db"

ALL_KEYS = [
    "AURA_URI",
    "AURA_USERNAME",
    "AURA_PASSWORD",
    "AURA_DATABASE",
    "NEO4J_CLOUD_URI",
    "NEO4J_CLOUD_USERNAME",
    "NEO4J_CLOUD_PASSWORD",
    "NEO4J_CLOUD_DATABASE",
    "NEO4J_URI",
    "NEO4J_USERNAME",
    "NEO4J_PASSWORD",
    "NEO4J_DATABASE",
]


def _clear_all(monkeypatch):
    for key in ALL_KEYS:
        monkeypatch.delenv(key, raising=False)


def _fake_run_factory(captured):
    def _fake_run(argv, **kwargs):
        captured["argv"] = list(argv)
        return SimpleNamespace(returncode=0, stdout=" 42\n", stderr="")

    return _fake_run


def _argv_map(argv):
    out = {}
    for flag in ("-a", "-u", "-p", "-d"):
        if flag in argv:
            out[flag] = argv[argv.index(flag) + 1]
    return out


def test_legacy_only_resolves(monkeypatch):
    _clear_all(monkeypatch)
    monkeypatch.setenv("NEO4J_URI", FAKE_LEGACY_URI)
    monkeypatch.setenv("NEO4J_USERNAME", FAKE_LEGACY_USER)
    monkeypatch.setenv("NEO4J_PASSWORD", FAKE_LEGACY_PASSWORD)
    monkeypatch.setenv("NEO4J_DATABASE", FAKE_LEGACY_DB)
    captured: dict = {}
    monkeypatch.setattr(subprocess, "run", _fake_run_factory(captured))
    assert build_index.aura_node_count() == 42
    assert "argv" in captured, "legacy vars must trigger cypher-shell call"
    got = _argv_map(captured["argv"])
    assert got["-a"] == FAKE_LEGACY_URI
    assert got["-u"] == FAKE_LEGACY_USER
    assert got["-p"] == FAKE_LEGACY_PASSWORD
    assert got["-d"] == FAKE_LEGACY_DB


def test_aura_wins_over_cloud_and_legacy(monkeypatch):
    _clear_all(monkeypatch)
    monkeypatch.setenv("AURA_URI", FAKE_AURA_URI)
    monkeypatch.setenv("AURA_USERNAME", FAKE_AURA_USER)
    monkeypatch.setenv("AURA_PASSWORD", FAKE_AURA_PASSWORD)
    monkeypatch.setenv("AURA_DATABASE", FAKE_AURA_DB)
    monkeypatch.setenv("NEO4J_CLOUD_URI", FAKE_CLOUD_URI)
    monkeypatch.setenv("NEO4J_CLOUD_USERNAME", FAKE_CLOUD_USER)
    monkeypatch.setenv("NEO4J_CLOUD_PASSWORD", FAKE_CLOUD_PASSWORD)
    monkeypatch.setenv("NEO4J_CLOUD_DATABASE", FAKE_CLOUD_DB)
    monkeypatch.setenv("NEO4J_URI", FAKE_LEGACY_URI)
    monkeypatch.setenv("NEO4J_USERNAME", FAKE_LEGACY_USER)
    monkeypatch.setenv("NEO4J_PASSWORD", FAKE_LEGACY_PASSWORD)
    monkeypatch.setenv("NEO4J_DATABASE", FAKE_LEGACY_DB)
    captured: dict = {}
    monkeypatch.setattr(subprocess, "run", _fake_run_factory(captured))
    assert build_index.aura_node_count() == 42
    got = _argv_map(captured["argv"])
    assert got["-a"] == FAKE_AURA_URI
    assert got["-u"] == FAKE_AURA_USER
    assert got["-p"] == FAKE_AURA_PASSWORD
    assert got["-d"] == FAKE_AURA_DB


def test_cloud_wins_over_legacy(monkeypatch):
    _clear_all(monkeypatch)
    monkeypatch.setenv("NEO4J_CLOUD_URI", FAKE_CLOUD_URI)
    monkeypatch.setenv("NEO4J_CLOUD_USERNAME", FAKE_CLOUD_USER)
    monkeypatch.setenv("NEO4J_CLOUD_PASSWORD", FAKE_CLOUD_PASSWORD)
    monkeypatch.setenv("NEO4J_CLOUD_DATABASE", FAKE_CLOUD_DB)
    monkeypatch.setenv("NEO4J_URI", FAKE_LEGACY_URI)
    monkeypatch.setenv("NEO4J_USERNAME", FAKE_LEGACY_USER)
    monkeypatch.setenv("NEO4J_PASSWORD", FAKE_LEGACY_PASSWORD)
    monkeypatch.setenv("NEO4J_DATABASE", FAKE_LEGACY_DB)
    captured: dict = {}
    monkeypatch.setattr(subprocess, "run", _fake_run_factory(captured))
    assert build_index.aura_node_count() == 42
    got = _argv_map(captured["argv"])
    assert got["-a"] == FAKE_CLOUD_URI
    assert got["-d"] == FAKE_CLOUD_DB


def test_none_set_returns_none(monkeypatch):
    _clear_all(monkeypatch)
    called = {"hit": False}

    def _boom(argv, **kwargs):
        called["hit"] = True
        return SimpleNamespace(returncode=0, stdout=" 42\n", stderr="")

    monkeypatch.setattr(subprocess, "run", _boom)
    assert build_index.aura_node_count() is None
    assert called["hit"] is False
