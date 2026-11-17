"""rewards.engine.emit with `amounts` (a pack's own XP / coins): booked once per account, with the smallest daily limit."""


def booked(fq, pid, account):
    return fq.db.val("SELECT SUM(amount) FROM ledger WHERE profile_id=? AND account=? AND event='lesson_done'", pid, account, default=0) or 0


def test_pack_amount_once_per_account_even_with_two_rules(fq, kid):
    fq.db.x("INSERT INTO rule(event, account, amount, daily_limit, label) VALUES('lesson_done', 'xp', 5, 100, 'second')")
    out = fq.rewards.emit(kid, "lesson_done", ref="s1", amounts={"xp": 30, "coins": 7})
    assert [b["amount"] for b in out if b["account"] == "xp" and b["event"] == "lesson_done"] == [30]
    assert booked(fq, kid, "xp") == 30 and booked(fq, kid, "coins") == 7
    # the smallest daily limit of the matching rules counts (coins: 50 by default)
    fq.rewards.emit(kid, "lesson_done", ref="s2", amounts={"coins": 40})
    assert booked(fq, kid, "coins") == 47
    fq.rewards.emit(kid, "lesson_done", ref="s3", amounts={"coins": 40})
    assert booked(fq, kid, "coins") == 50


def test_pack_amount_without_a_rule_and_with_a_rule_switched_off(fq, kid):
    fq.db.x("DELETE FROM rule WHERE event='lesson_done' AND account='xp'")
    fq.db.x("UPDATE rule SET active=0 WHERE event='lesson_done' AND account='coins'")
    fq.rewards.emit(kid, "lesson_done", ref="s1", amounts={"xp": 25, "coins": 9})
    assert booked(fq, kid, "xp") == 25                 # no rule: the pack's amount, without a limit
    assert booked(fq, kid, "coins") == 0               # the parents switched the rule off: nothing
    # without amounts the rules work as before
    fq.db.x("UPDATE rule SET active=1 WHERE event='lesson_done' AND account='coins'")
    fq.rewards.emit(kid, "lesson_done", ref="s2")
    assert booked(fq, kid, "coins") == 10 and booked(fq, kid, "xp") == 25
