"""HTTP cache semantics on frozen demo routes: ETag + Cache-Control + X-Cache + 304."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import demo


def _fresh_client():
    demo._SEEN_DEMO_IDS.clear()
    demo._ETAG_CACHE.clear()
    demo._SEEN_LIST = False
    demo.load_bundle.cache_clear()
    app = FastAPI()
    app.include_router(demo.router)
    return TestClient(app)


def test_demo_cache_miss_hit_304():
    client = _fresh_client()
    r1 = client.get("/demo/priya")
    assert r1.status_code == 200
    assert r1.headers.get("X-Cache") == "MISS"
    assert "ETag" in r1.headers
    assert r1.headers.get("Cache-Control") == "public, max-age=3600"
    etag = r1.headers["ETag"]
    assert etag.startswith('"') and etag.endswith('"')

    r2 = client.get("/demo/priya")
    assert r2.status_code == 200
    assert r2.headers.get("X-Cache") == "HIT"
    assert r2.headers.get("ETag") == etag

    r3 = client.get("/demo/priya", headers={"If-None-Match": etag})
    assert r3.status_code == 304
    assert r3.content == b""
    assert r3.headers.get("ETag") == etag
    assert r3.headers.get("X-Cache") == "HIT"

    # wrong etag still returns 200 HIT (not 304)
    r4 = client.get("/demo/priya", headers={"If-None-Match": '"bogus"'})
    assert r4.status_code == 200

    # list endpoint also has cache headers
    c2 = _fresh_client()
    rl1 = c2.get("/demo")
    assert rl1.status_code == 200
    assert rl1.headers.get("Cache-Control") == "public, max-age=3600"
    assert "ETag" in rl1.headers


def test_demo_etag_stable_across_ids():
    client = _fresh_client()
    for did in ["priya", "msme", "dpdp"]:
        r = client.get(f"/demo/{did}")
        assert r.status_code == 200
        assert "ETag" in r.headers
        etag = r.headers["ETag"]
        r2 = client.get(f"/demo/{did}", headers={"If-None-Match": etag})
        assert r2.status_code == 304
