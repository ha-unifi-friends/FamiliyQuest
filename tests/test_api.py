def setup_family(client):
    r = client.post("/api/setup", json={"name": "Papa", "pin": "1234"})
    assert r.status_code == 200, r.text
    ph = {"X-FQ-Parent": r.json()["parent_token"]}
    r = client.post("/api/parent/profiles", json={"name": "Mia", "color": "#ff6b6b", "pin": "1111"}, headers=ph)
    assert r.status_code == 200, r.text
    kid_id = r.json()["id"]
    r = client.post("/api/parent/profiles", json={"name": "Leo"}, headers=ph)
    return ph, kid_id, r.json()["id"]


def test_setup_login_and_lesson(client):
    assert client.get("/api/info").json()["setup_needed"]
    ph, mia, leo = setup_family(client)
    assert client.post("/api/setup", json={"name": "X", "pin": "1234"}).status_code == 409
    profiles = client.get("/api/profiles").json()
    assert [p["name"] for p in profiles] == ["Mia", "Leo", "Papa"]
    assert client.post("/api/login", json={"profile_id": mia, "pin": "0000"}).status_code == 403
    tok = client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]
    leo_tok = client.post("/api/login", json={"profile_id": leo}).json()["token"]
    h = {"X-FQ-Token": tok}
    me = client.get("/api/me", headers=h).json()
    assert me["profile"]["name"] == "Mia" and me["subjects"]
    s = client.post("/api/me/session", json={"mode": "path", "pack": "mathe-5kl", "unit": "einmaleins"}, headers=h).json()
    step = s["steps"][0]
    assert "answer" not in step
    r = client.post(f"/api/me/session/{s['id']}/answer", json={"step": 0, "answer": "0"}, headers=h).json()
    assert "solution" in r
    # another child cannot touch Mia's session
    assert client.post(f"/api/me/session/{s['id']}/answer", json={"step": 1, "answer": "1"},
                       headers={"X-FQ-Token": leo_tok}).status_code == 400
    res = client.post(f"/api/me/session/{s['id']}/finish", headers=h).json()
    assert res["total"] == len(s["steps"])
    assert client.get("/api/family", headers=h).json()["members"]


def test_parent_requires_pin(client):
    ph, mia, _ = setup_family(client)
    assert client.get("/api/parent/overview").status_code == 401
    tok = client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]
    assert client.get("/api/parent/overview", headers={"X-FQ-Parent": tok}).status_code == 401
    assert client.post("/api/parent/login", json={"pin": "9999"}).status_code == 403
    ok = client.post("/api/parent/login", json={"pin": "1234"}).json()
    assert client.get("/api/parent/overview", headers={"X-FQ-Parent": ok["parent_token"]}).status_code == 200


def test_shop_flow_via_api(client):
    ph, mia, _ = setup_family(client)
    client.post("/api/parent/book", json={"profile_id": mia, "account": "coins", "amount": 200, "reason": "Start"}, headers=ph)
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    shop = client.get("/api/me/shop", headers=h).json()
    ice = next(o for o in shop["offers"] if o["name"] == "Ice cream")
    red = client.post("/api/me/redeem", json={"reward_id": ice["id"]}, headers=h).json()
    pending = client.get("/api/parent/redemptions?status=pending", headers=ph).json()
    assert pending[0]["id"] == red["id"]
    assert client.post(f"/api/parent/redemptions/{red['id']}", json={"approve": True}, headers=ph).json()["status"] == "approved"


def test_avatar(client):
    ph, mia, _ = setup_family(client)
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    cat = client.get("/api/me/avatar", headers=h).json()
    assert cat["parts"]["hair"]
    r = client.post("/api/me/avatar", json={"avatar": {"hair": "curly", "items": {"hat": "crown"}}}, headers=h).json()
    assert r["avatar"]["hair"] == "curly" and "hat" not in r["avatar"]["items"]   # crown is locked
    assert client.post("/api/me/avatar/buy", json={"item": "cap"}, headers=h).status_code == 400
    client.post("/api/parent/book", json={"profile_id": mia, "account": "coins", "amount": 50}, headers=ph)
    assert client.post("/api/me/avatar/buy", json={"item": "cap"}, headers=h).status_code == 200
    r = client.post("/api/me/avatar", json={"avatar": {"items": {"hat": "cap"}}}, headers=h).json()
    assert r["avatar"]["items"] == {"hat": "cap"}
    # free for everybody from level 1: glasses, braces, hair clips – and pink clothes and hair
    r = client.post("/api/me/avatar", json={"avatar": {"outfitColor": "#f783ac", "hairColor": "#f06595",
        "items": {"eyewear": "glasses", "teeth": "braces", "hairclip": "clip_bow", "pet": "parrot"}}}, headers=h).json()
    assert r["avatar"]["items"] == {"eyewear": "glasses", "teeth": "braces", "hairclip": "clip_bow"}    # the parrot is still in the shop
    assert r["avatar"]["outfitColor"] == "#f783ac" and r["avatar"]["hairColor"] == "#f06595"


def test_web_and_i18n(client):
    r = client.get("/")
    assert r.status_code == 200 and "Family Quest" in r.text
    assert client.get("/eltern").status_code == 200
    assert client.get("/i18n/de-CH.json").status_code == 200
    assert client.get("/i18n/../secret.json").status_code == 404
    assert client.get("/shared/i18n.js").status_code == 200
    assert client.get("/../familyquest/main.py").status_code == 404
    # the planer page and the files next to its bundle (a rebuild once deleted them)
    for f in ("planer", "planer/host.js", "planer/mdi-icons.js", "planer/family-planer-cards.js"):
        assert client.get("/" + f).status_code == 200, f


def test_translations_complete():
    """Every English UI text has a translation in every language, with the same placeholders."""
    import importlib.util
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("i18n_extract", root / "tools" / "i18n_extract.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.check(mod.keys()) == 0


def test_second_parent(client):
    ph, mia, _ = setup_family(client)
    me = client.get("/api/parent/meta", headers=ph).json()["me"]["id"]
    assert client.post("/api/parent/profiles", json={"name": "Mama", "role": "parent"}, headers=ph).status_code == 400   # PIN missing
    r = client.post("/api/parent/profiles", json={"name": "Mama", "role": "parent", "pin": "5678",
                                                  "settings": {"notify_service": "notify.mobile_app_mama"}}, headers=ph)
    assert r.status_code == 200, r.text
    mama = r.json()["id"]
    bad = client.post("/api/parent/profiles", json={"name": "X", "role": "parent", "pin": "5679", "settings": {"notify_service": "rm -rf"}}, headers=ph)
    assert bad.status_code == 400
    # Mama logs into the parent area with her own PIN
    tok = client.post("/api/parent/login", json={"pin": "5678"}).json()
    assert tok["profile"]["name"] == "Mama"
    mh = {"X-FQ-Parent": tok["parent_token"]}
    profs = {p["id"]: p for p in client.get("/api/parent/profiles", headers=mh).json()}
    assert profs[mama]["settings"]["notify_service"] == "notify.mobile_app_mama"
    # Mama can remove Papa – but not the last parent afterwards
    assert client.delete(f"/api/parent/profiles/{me}", headers=mh).status_code == 400            # name not typed
    assert client.delete(f"/api/parent/profiles/{me}?name=papa", headers=mh).status_code == 200
    assert client.put(f"/api/parent/profiles/{mama}", json={"name": "Mama", "role": "kid"}, headers=mh).status_code == 400
    # a child cannot become a parent without a PIN
    assert client.put(f"/api/parent/profiles/{mia}", json={"name": "Mia", "role": "parent"}, headers=mh).status_code == 200  # Mia has a PIN


def test_sad_mood_tells_parents(client):
    ph, mia, _ = setup_family(client)
    fq = client.app.state.fq
    told = []
    fq.on_mood.append(lambda p, sad, text: told.append(p["name"]) if sad and not text else told.append(text))
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    client.post("/api/me/avatar", json={"avatar": {"eyes": "sad", "mouth": "sad"}}, headers=h)
    assert told == ["Mia"]
    kid = next(k for k in client.get("/api/parent/overview", headers=ph).json()["kids"] if k["profile"]["id"] == mia)
    assert kid["sad_since"]
    client.post("/api/me/avatar", json={"avatar": {"eyes": "happy", "mouth": "grin"}}, headers=h)
    client.post("/api/me/avatar", json={"avatar": {"eyes": "sad"}}, headers=h)
    assert told == ["Mia"]                                    # only once per day
    client.post("/api/me/avatar", json={"avatar": {"eyes": "happy", "mouth": "smile"}}, headers=h)
    kid = next(k for k in client.get("/api/parent/overview", headers=ph).json()["kids"] if k["profile"]["id"] == mia)
    assert kid["sad_since"] is None



def test_mood_text(client):
    ph, mia, _ = setup_family(client)
    fq = client.app.state.fq
    told = []
    fq.on_mood.append(lambda p, sad, text: told.append((sad, text)))
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    client.post("/api/me/avatar", json={"avatar": {"eyes": "sad"}, "mood_text": "  müde,   weil ich schlecht geschlafen habe "}, headers=h)
    assert told == [(True, "müde, weil ich schlecht geschlafen habe")]
    assert client.get("/api/me/avatar", headers=h).json()["mood_text"] == "müde, weil ich schlecht geschlafen habe"
    kid = next(k for k in client.get("/api/parent/overview", headers=ph).json()["kids"] if k["profile"]["id"] == mia)
    assert kid["mood_text"] == "müde, weil ich schlecht geschlafen habe" and kid["mood_text_at"]
    client.post("/api/me/avatar", json={"avatar": {"eyes": "happy"}, "mood_text": "wieder gut"}, headers=h)
    assert len(told) == 1                                      # second text within 10 minutes: stored, no new note
    client.post("/api/me/avatar", json={"avatar": {"eyes": "happy"}, "mood_text": "x" * 500}, headers=h)
    assert len(client.get("/api/me/avatar", headers=h).json()["mood_text"]) == 200


PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")


def test_own_photos_for_pairs(client, settings):
    ph, mia, _ = setup_family(client)
    pid = "franz-5kl-la-maison"
    # only real pictures are accepted
    bad = client.post(f"/api/parent/packs/{pid}/media", files={"file": ("x.jpg", b"<svg/>", "image/jpeg")}, headers=ph)
    assert bad.status_code == 400
    names = []
    for i in range(4):
        r = client.post(f"/api/parent/packs/{pid}/media", files={"file": (f"f{i}.png", PNG + bytes([i]), "image/png")}, headers=ph)
        assert r.status_code == 200, r.text
        names.append(r.json()["name"])
        assert client.get(r.json()["url"]).status_code == 200
    data = client.get(f"/api/parent/packs/{pid}/raw", headers=ph).json()["data"]
    data["einheiten"].append({"id": "familie", "titel": "Familie", "uebungen": ["paare", "auswahl"],
                              "karten": [{"bild": n, "antwort": a} for n, a in zip(names, ["Oma", "Opa", "Tante", "Onkel"])]})
    assert client.put(f"/api/parent/packs/{pid}/raw", json={"data": data}, headers=ph).status_code == 200
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    s = client.post("/api/me/session", json={"mode": "path", "pack": pid, "unit": "familie"}, headers=h).json()
    assert s["steps"]
    for st in s["steps"]:
        if st["kind"] == "paare":
            assert all(x["image"].startswith(f"media/{pid}/foto-") for x in st["left"])
        else:
            assert st["image"].startswith(f"media/{pid}/foto-") and "" not in st["options"]
    # a photo no card uses any more is removed when saving
    data["einheiten"][-1]["karten"].pop()
    client.put(f"/api/parent/packs/{pid}/raw", json={"data": data}, headers=ph)
    assert not (settings.media_dir / pid / names[3]).exists() and (settings.media_dir / pid / names[0]).exists()


def test_direct_access_info(client):
    ph, _, _ = setup_family(client)
    d = client.get("/api/parent/direct-access", headers=ph).json()
    assert d == {"enabled": False, "port": None, "default_port": 8099, "ips": []}
    assert client.get("/shared/qrcode.js").status_code == 200
    # without login: where the parent area in Home Assistant links the app to (no direct access → no port)
    assert client.get("/api/app-link").json() == {"port": None, "ips": []}


def test_picture_pin_for_children(client):
    from familyquest.symbols import SYMBOLS
    ph, mia, _ = setup_family(client)
    sset = list(SYMBOLS)[:12]
    secret = [sset[3], sset[0], sset[11], sset[9]]
    # parents cannot have a picture PIN, a child needs 4 different symbols out of its 12
    assert client.put(f"/api/parent/profiles/{mia}", json={"name": "Mia", "pin_symbols": secret[:3], "symbol_set": sset}, headers=ph).status_code == 400
    assert client.put(f"/api/parent/profiles/{mia}", json={"name": "Mia", "pin_symbols": [secret[0]] * 4, "symbol_set": sset}, headers=ph).status_code == 400
    assert client.put(f"/api/parent/profiles/{mia}", json={"name": "Mia", "pin_symbols": secret, "symbol_set": sset[:11] + ["nope"]}, headers=ph).status_code == 400
    # parents may use a picture PIN too – for the parent area they choose their profile first
    ma = client.post("/api/parent/profiles", json={"name": "Ma", "role": "parent", "pin_symbols": secret, "symbol_set": sset}, headers=ph)
    assert ma.status_code == 200, ma.text
    assert client.post("/api/parent/login", json={"pin": "sym:" + ",".join(secret), "profile_id": ma.json()["id"]}).status_code == 200
    assert client.post("/api/parent/login", json={"pin": "sym:" + ",".join(secret[::-1]), "profile_id": ma.json()["id"]}).status_code == 403
    r = client.put(f"/api/parent/profiles/{mia}", json={"name": "Mia", "pin_symbols": secret, "symbol_set": sset}, headers=ph)
    assert r.status_code == 200, r.text
    pub = next(p for p in client.get("/api/profiles").json() if p["id"] == mia)
    assert pub["pin_kind"] == "symbols" and sorted(pub["symbol_set"]) == sorted(sset)      # same set, any order
    # wrong order or wrong symbols → no
    assert client.post("/api/login", json={"profile_id": mia, "pin": "sym:" + ",".join(secret[::-1])}).status_code == 403
    assert client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).status_code == 403
    assert client.post("/api/login", json={"profile_id": mia, "pin": "sym:" + ",".join(secret)}).status_code == 200
    # other settings are saved without touching the picture PIN; a digit PIN replaces it
    assert client.put(f"/api/parent/profiles/{mia}", json={"name": "Mia M."}, headers=ph).status_code == 200
    assert client.post("/api/login", json={"profile_id": mia, "pin": "sym:" + ",".join(secret)}).status_code == 200
    client.put(f"/api/parent/profiles/{mia}", json={"name": "Mia", "pin": "2468"}, headers=ph)
    pub = next(p for p in client.get("/api/profiles").json() if p["id"] == mia)
    assert pub["pin_kind"] == "digits" and "symbol_set" not in pub
    assert client.post("/api/login", json={"profile_id": mia, "pin": "2468"}).status_code == 200


def test_failed_logins_with_device(client):
    from types import SimpleNamespace
    from familyquest import loginlog
    ph, mia, leo = setup_family(client)
    # the UniFi device tracker of the tablet (mirrored Home Assistant states); TestClient's address is "testclient"
    client.app.state.fq.planer_host.hass.states.set("device_tracker.tablet_mia", "home",
                                                    {"ip": "testclient", "mac": "aa:bb:cc:dd:ee:ff", "friendly_name": "Tablet Mia"})
    assert client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).status_code == 200
    assert client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).status_code == 200
    assert client.post("/api/login", json={"profile_id": mia, "pin": "9999"}).status_code == 403
    assert client.post("/api/parent/login", json={"pin": "0000"}).status_code == 403
    failed = client.get("/api/parent/logins/failed", headers=ph).json()
    assert [f["kind"] for f in failed] == ["parent", "profile"]
    f = failed[1]
    assert f["profile_name"] == "Mia" and f["ip"] == "testclient" and f["mac"] == "aa:bb:cc:dd:ee:ff" and f["device"] == "Tablet Mia"
    assert f["usual"]["name"] == "Mia" and f["usual"]["n"] == 2
    assert client.get("/api/parent/logins/failed").status_code == 401
    # behind Home Assistant ingress the real address comes from X-Forwarded-For
    req = SimpleNamespace(client=SimpleNamespace(host="172.30.32.2"), headers={"x-forwarded-for": "192.168.1.23, 172.30.32.1"})
    assert loginlog.client_ip(req) == "192.168.1.23"
    req = SimpleNamespace(client=SimpleNamespace(host="192.168.1.50"), headers={"x-forwarded-for": "1.2.3.4"})
    assert loginlog.client_ip(req) == "192.168.1.50"           # direct access: the header is not trusted


def test_network_filter(client):
    from familyquest import netfilter
    ph, mia, _ = setup_family(client)
    assert netfilter.allowed("192.168.35.20", ["192.168.35.0/24"]) and not netfilter.allowed("192.168.36.20", ["192.168.35.0/24"])
    assert netfilter.allowed("10.1.2.3", []) and netfilter.allowed("::ffff:192.168.35.9", ["192.168.35.0/24"])
    assert netfilter.parse(["192.168.35.0-192.168.35.255", " 10.0.0.5 - 10.0.0.9 "]) == ["192.168.35.0/24", "10.0.0.5-10.0.0.9"]
    assert netfilter.allowed("10.0.0.7", ["10.0.0.5-10.0.0.9"]) and not netfilter.allowed("10.0.0.10", ["10.0.0.5-10.0.0.9"])
    assert netfilter.allowed("::ffff:10.0.0.5", ["10.0.0.5-10.0.0.9"])
    assert netfilter.parse([" 192.168.35.7/24 ", "", "10.0.0.5"]) == ["192.168.35.0/24", "10.0.0.5/32"]
    # bad entries and lists that would lock out the parent who saves are refused
    assert client.put("/api/parent/settings", json={"parent_networks": ["192.168.300.0/24"]}, headers=ph).status_code == 400
    r = client.put("/api/parent/settings", json={"allowed_networks": ["192.168.35.0/24"]}, headers=ph)
    assert r.status_code == 400 and "lock you out" in r.json()["detail"]
    # a restriction in place (set directly): the app refuses requests from other networks and logs them
    fq = client.app.state.fq
    fq.db.set_setting("parent_networks", ["192.168.35.0/24"])
    assert client.get("/api/profiles").status_code == 200                     # the learning app is still open
    assert client.get("/api/parent/overview", headers=ph).status_code == 403
    assert client.get("/eltern").status_code == 403
    fq.db.set_setting("allowed_networks", ["192.168.35.0/24"])
    assert client.get("/api/profiles").status_code == 403
    assert fq.db.val("SELECT COUNT(*) FROM login_log WHERE kind='blocked'") >= 1


def test_crown_for_a_day_and_mood(client):
    ph, mia, _ = setup_family(client)
    r = client.post(f"/api/parent/profiles/{mia}/crown", json={"on": True}, headers=ph).json()
    assert r["crown"] and r["avatar"]["items"]["hat"] == "royal"
    pub = next(p for p in client.get("/api/profiles").json() if p["id"] == mia)
    assert pub["crown"] and pub["avatar"]["items"]["hat"] == "royal"
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    av = client.get("/api/me/avatar", headers=h).json()
    assert "royal" not in (av["avatar"].get("items") or {}).values()             # not part of the own avatar
    assert any(i["id"] == "pirate_hat" and i["rule"]["cost"] == 90 for i in av["items"])
    # the child picks a mood: parents see the emoji, «sick» is told quietly like «sad»
    client.post("/api/me/avatar", json={"avatar": {**av["avatar"], "eyes": "round", "mouth": "wavy"}, "mood": "🤢", "mood_text": "Bauchweh"}, headers=h)
    kid = next(k for k in client.get("/api/parent/overview", headers=ph).json()["kids"] if k["profile"]["id"] == mia)
    assert kid["mood"] == "🤢" and kid["mood_text"] == "Bauchweh" and kid["sad_since"]
    client.post(f"/api/parent/profiles/{mia}/crown", json={"on": False}, headers=ph)
    assert not next(p for p in client.get("/api/profiles").json() if p["id"] == mia)["crown"]


def test_child_changes_own_pin(client):
    ph, mia, _ = setup_family(client)
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    assert client.post("/api/me/pin", json={"old_pin": "0000", "pin": "2222"}, headers=h).status_code == 403
    assert client.post("/api/me/pin", json={"old_pin": "1111", "pin": "22222"}, headers=h).status_code == 400
    r = client.post("/api/me/pin", json={"old_pin": "1111", "pin": "2222"}, headers=h)
    assert r.status_code == 200
    assert client.get("/api/me", headers=h).status_code == 401                 # the old login ends with the new PIN
    h = {"X-FQ-Token": r.json()["token"]}
    assert client.post("/api/login", json={"profile_id": mia, "pin": "2222"}).status_code == 200
    # picture PIN
    from familyquest import symbols
    sset = list(symbols.SYMBOLS)[:12]
    r = client.post("/api/me/pin", json={"old_pin": "2222", "pin_symbols": sset[:4], "symbol_set": sset}, headers=h)
    assert r.status_code == 200 and r.json()["profile"]["pin_kind"] == "symbols"
    assert client.post("/api/login", json={"profile_id": mia, "pin": "sym:" + ",".join(sset[:4])}).status_code == 200


def test_remove_profile_archive_or_delete(client):
    ph, mia, leo = setup_family(client)
    assert client.delete(f"/api/parent/profiles/{mia}?name=Leo", headers=ph).status_code == 400
    assert client.delete(f"/api/parent/profiles/{mia}?name=Mia&mode=archive", headers=ph).json()["mode"] == "archive"
    assert [p["name"] for p in client.get("/api/parent/profiles/archived", headers=ph).json()] == ["Mia"]
    assert mia not in [p["id"] for p in client.get("/api/profiles").json()]
    client.post(f"/api/parent/profiles/{mia}/restore", headers=ph)
    assert mia in [p["id"] for p in client.get("/api/profiles").json()]
    client.post(f"/api/parent/weather/{leo}", json={"level": "rain"}, headers=ph)
    assert client.delete(f"/api/parent/profiles/{leo}?name=leo&mode=delete", headers=ph).status_code == 200
    assert leo not in [p["id"] for p in client.get("/api/parent/profiles", headers=ph).json()]
    assert client.get("/api/parent/profiles/archived", headers=ph).json() == []


def test_perfect_lesson_gives_coins(client):
    ph, mia, leo = setup_family(client)
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    client.post("/api/me/courses/franz-5kl-la-maison", json={"on": True}, headers=h)
    def lesson(answer):
        s = client.post("/api/me/session", json={"mode": "cards", "pack": "franz-5kl-la-maison"}, headers=h).json()
        for i, _ in enumerate(s["steps"]):
            client.post(f"/api/me/session/{s['id']}/answer", json={"step": i, "answer": answer}, headers=h)
        client.post(f"/api/me/session/{s['id']}/finish", headers=h)
        return s["id"]
    fq = client.app.state.fq
    sid = lesson("correct")
    assert fq.db.val("SELECT SUM(amount) FROM ledger WHERE profile_id=? AND event='lesson_perfect' AND ref=?", mia, sid) == 5
    sid = lesson("wrong")
    assert not fq.db.val("SELECT COUNT(*) FROM ledger WHERE event='lesson_perfect' AND ref=?", sid)
    client.put("/api/parent/settings", headers=ph, json={"lesson_perfect_coins": 12})
    sid = lesson("correct")
    assert fq.db.val("SELECT SUM(amount) FROM ledger WHERE event='lesson_perfect' AND ref=?", sid) == 12


def test_start_page_asks_for_new_games(client):
    ph, mia, leo = setup_family(client)
    h = {"X-FQ-Token": client.post("/api/login", json={"profile_id": mia, "pin": "1111"}).json()["token"]}
    hl = {"X-FQ-Token": client.post("/api/login", json={"profile_id": leo}).json()["token"]}
    before = client.get("/api/me/community", headers=h).json()
    client.post("/api/community/cards/tschau/start", json={}, headers=hl)        # Leo opens a family table
    after = client.get("/api/me/community", headers=h).json()
    assert before != after and after["tschau"]["status"] == "lobby"
