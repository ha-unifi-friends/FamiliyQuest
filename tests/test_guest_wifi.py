"""Guest Wi-Fi QR code (an image entity of Home Assistant, e.g. UniFi) in «Invite guests»: the setting, the proxy
GET /api/guest-wifi-qr (only for signed-in family members), its checks and cache, and the `wifi` flag of the invitation.
Home Assistant is faked with an httpx MockTransport behind the real HAClient (its /api/image_proxy answers a PNG)."""
import asyncio
import threading

import httpx
import pytest

from familyquest import backup
from familyquest.ha.client import HAClient
from familyquest.ha.service import HAService
from test_api import setup_family

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")


class FakeHA:
    """The image proxy of a fake Home Assistant: image.guest_qr → PNG, image.text → text/html, image.big → too big."""
    def __init__(self):
        self.hits = []
        self.down = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer tok"
        if request.method == "POST":                                     # the sensors the app publishes: fine
            return httpx.Response(200, json={})
        if "_proxy/" in request.url.path:
            self.hits.append(request.url.path)
        if self.down:
            return httpx.Response(502)
        ent = request.url.path.rsplit("/", 1)[-1]
        if request.url.path.startswith("/api/image_proxy/image.guest_qr") or request.url.path == "/api/camera_proxy/camera.door":
            return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})
        if ent == "image.text":
            return httpx.Response(200, content=b"<script>alert(1)</script>", headers={"content-type": "text/html"})
        if ent == "image.svg":
            return httpx.Response(200, content=b"<svg/>", headers={"content-type": "image/svg+xml"})
        if ent == "image.big":
            return httpx.Response(200, content=b"\0" * (2 * 1024 * 1024 + 1), headers={"content-type": "image/png"})
        if request.url.path == "/api/states":
            return httpx.Response(200, json=[{"entity_id": "image.guest_qr", "state": "x", "attributes": {"friendly_name": "Gast QR"}},
                                             {"entity_id": "sensor.t", "state": "1", "attributes": {}}])
        return httpx.Response(404)


@pytest.fixture
def ha(client):
    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, daemon=True).start()
    fake = FakeHA()
    c = HAClient("http://ha.local", "tok")

    async def setup():
        c.http = httpx.AsyncClient(base_url="http://ha.local", headers={"Authorization": "Bearer tok"},
                                   transport=httpx.MockTransport(fake))
        c.connected.set()
    asyncio.run_coroutine_threadsafe(setup(), loop).result(5)
    fq = client.app.state.fq
    fq.ha = HAService(fq, c, loop)
    yield fake
    fq.ha = None
    loop.call_soon_threadsafe(loop.stop)


def _login(client):
    ph, mia, leo = setup_family(client)
    kh = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    return ph, kh


def test_setting_round_trip_and_validation(client):
    ph, _ = _login(client)
    assert client.get("/api/parent/settings", headers=ph).json()["guest_wifi_qr"] is None
    r = client.put("/api/parent/settings", json={"guest_wifi_qr": " image.munwifi40_qr_code "}, headers=ph)
    assert r.status_code == 200 and r.json()["guest_wifi_qr"] == "image.munwifi40_qr_code"
    assert client.put("/api/parent/settings", json={"guest_wifi_qr": "camera.door"}, headers=ph).json()["guest_wifi_qr"] == "camera.door"
    for bad in ["light.kitchen", "image.", "image.x/../../api/states", "IMAGE.X", 5, ["image.x"]]:
        assert client.put("/api/parent/settings", json={"guest_wifi_qr": bad}, headers=ph).status_code == 400, bad
    assert client.get("/api/parent/settings", headers=ph).json()["guest_wifi_qr"] == "camera.door"
    assert client.put("/api/parent/settings", json={"guest_wifi_qr": ""}, headers=ph).json()["guest_wifi_qr"] is None
    # only parents set it
    mia = client.get("/api/profiles").json()[0]["id"]
    kh = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    assert client.put("/api/parent/settings", json={"guest_wifi_qr": "image.x"}, headers=kh).status_code == 401


def test_backup_classification():
    assert backup.setting_kind("guest_wifi_qr", None) == backup.CUSTOM


def test_not_configured_or_ha_missing_is_404(client, ha):
    ph, kh = _login(client)
    assert client.get("/api/guest-wifi-qr", headers=kh).status_code == 404            # not set up
    client.put("/api/parent/settings", json={"guest_wifi_qr": "image.guest_qr"}, headers=ph)
    ha.down = True
    assert client.get("/api/guest-wifi-qr", headers=kh).status_code == 404            # HA has no picture
    client.app.state.fq.ha = None
    assert client.get("/api/guest-wifi-qr", headers=kh).status_code == 404            # no Home Assistant at all


def test_access_only_for_family_members(client, ha):
    ph, kh = _login(client)
    client.put("/api/parent/settings", json={"guest_wifi_qr": "image.guest_qr"}, headers=ph)
    assert client.get("/api/guest-wifi-qr").status_code == 401
    assert client.get("/api/guest-wifi-qr", headers={"X-FQ-Token": "nonsense"}).status_code == 401
    for hd in (kh, ph):
        r = client.get("/api/guest-wifi-qr", headers=hd)
        assert r.status_code == 200 and r.content == PNG and r.headers["content-type"] == "image/png"
        assert r.headers["cache-control"] == "private, no-store"
    assert ha.hits == ["/api/image_proxy/image.guest_qr"]                                 # the second one from the cache
    # a guest of a running game never gets it (it holds the Wi-Fi password)
    client.post("/api/community/bingo/start", json={}, headers=kh)
    inv = client.post("/api/community/guests", json={"game": "bingo"}, headers=kh).json()
    g = {"X-FQ-Token": client.post("/api/community/guest/join", json={"code": inv["invite"]["code"], "name": "Oma"}).json()["token"]}
    assert client.get("/api/guest-wifi-qr", headers=g).status_code == 401


def test_only_pictures_and_size_cap(client, ha):
    ph, kh = _login(client)
    for ent in ("image.text", "image.svg", "image.big"):
        client.put("/api/parent/settings", json={"guest_wifi_qr": ent}, headers=ph)
        assert client.get("/api/guest-wifi-qr", headers=kh).status_code == 404, ent
    client.put("/api/parent/settings", json={"guest_wifi_qr": "camera.door"}, headers=ph)    # a camera: camera_proxy
    r = client.get("/api/guest-wifi-qr", headers=kh)
    assert r.status_code == 200 and r.content == PNG and ha.hits[-1] == "/api/camera_proxy/camera.door"


def test_cache_five_minutes(client, ha, monkeypatch):
    import familyquest.ha.service as svc
    ph, kh = _login(client)
    client.put("/api/parent/settings", json={"guest_wifi_qr": "image.guest_qr"}, headers=ph)
    now = [1000.0]
    monkeypatch.setattr(svc.time, "monotonic", lambda: now[0])
    for _ in range(3):
        assert client.get("/api/guest-wifi-qr", headers=kh).status_code == 200
    assert len(ha.hits) == 1
    now[0] += 299
    client.get("/api/guest-wifi-qr", headers=kh)
    assert len(ha.hits) == 1
    now[0] += 2                                                                          # older than 5 minutes: fetched again
    client.get("/api/guest-wifi-qr", headers=kh)
    assert len(ha.hits) == 2
    ha.down = True                                                                       # a failure is not kept
    now[0] += 301
    assert client.get("/api/guest-wifi-qr", headers=kh).status_code == 404
    ha.down = False
    assert client.get("/api/guest-wifi-qr", headers=kh).status_code == 200


def test_invite_has_wifi_flag_only_when_configured(client):
    ph, kh = _login(client)
    client.post("/api/community/bingo/start", json={}, headers=kh)
    r = client.post("/api/community/guests", json={"game": "bingo"}, headers=kh).json()
    assert r["invite"]["code"] and "wifi" not in r
    client.put("/api/parent/settings", json={"guest_wifi_qr": "image.guest_qr"}, headers=ph)
    assert client.post("/api/community/guests", json={"game": "bingo"}, headers=kh).json()["wifi"] is True


def test_image_entities_are_listed(client, ha):
    ph, _ = _login(client)
    assert client.get("/api/parent/ha/entities?domain=image", headers=ph).json() == [{"entity_id": "image.guest_qr", "name": "Gast QR"}]
