import pytest

from familyquest.rewards.shop import ShopError


def test_redeem_with_approval(fq, kid):
    fq.rewards.book(kid, "coins", 100, "test")
    ice = next(o for o in fq.shop.offers(kid) if o["name"] == "Ice cream")
    red = fq.shop.redeem(kid, ice["id"])
    assert red["status"] == "pending"
    assert fq.rewards.balance(kid, "coins") == 20
    fq.shop.decide(red["id"], False)
    assert fq.rewards.balance(kid, "coins") == 100
    red = fq.shop.redeem(kid, ice["id"])
    assert fq.shop.decide(red["id"], True)["status"] == "approved"
    assert fq.rewards.balance(kid, "coins") == 20


def test_not_enough_and_weekly_limit(fq, kid):
    ice = next(o for o in fq.shop.offers(kid) if o["name"] == "Ice cream")
    with pytest.raises(ShopError):
        fq.shop.redeem(kid, ice["id"])
    fq.rewards.book(kid, "coins", 1000, "test")
    fq.shop.redeem(kid, ice["id"])
    fq.shop.redeem(kid, ice["id"])
    with pytest.raises(ShopError):
        fq.shop.redeem(kid, ice["id"])          # weekly limit 2


def test_internet_minutes_needs_entity_and_ha(fq, kid):
    import json
    assert not any(o["kind"] == "internet_minutes" for o in fq.shop.offers(kid))
    fq.db.x("UPDATE profile SET settings=? WHERE id=?", json.dumps({"internet_entity": "input_number.mia_internet"}), kid)
    fq.rewards.book(kid, "coins", 100, "test")
    o = next(o for o in fq.shop.offers(kid) if o["kind"] == "internet_minutes")
    red = fq.shop.redeem(kid, o["id"])            # no approval needed → executes immediately
    assert red["status"] == "failed"              # Home Assistant not connected → refunded
    assert fq.rewards.balance(kid, "coins") == 100

    calls = []
    fq.shop.executor = lambda kind, p, r, rid: (calls.append(kind) or (True, "ok"))
    red = fq.shop.redeem(kid, o["id"])
    assert red["status"] == "approved" and calls == ["internet_minutes"]
    assert fq.rewards.balance(kid, "coins") == 85
