"""Log of logins: failed ones are shown in the parent area with IP, MAC and device name.

IP: through Home Assistant ingress every request comes from the Supervisor proxy (172.30.32.2); Home Assistant
passes the real address in X-Forwarded-For. With direct access the connection's address is used.
Device: the UniFi integration has a device_tracker per client with the attributes ip, mac, host_name – the
app mirrors the Home Assistant states (planer host), so the device is looked up there.
Successful logins are logged too: they tell who normally logs in from an address.
"""
from __future__ import annotations

from .api.auth import INGRESS_IP

KEEP_DAYS = 180


def client_ip(request) -> str:
    host = request.client.host if request.client else ""
    if host == INGRESS_IP:
        # the proxies of Home Assistant append the address they saw – the right-most outside address is the real
        # client; the left-most could have been sent by the client itself
        parts = [x.strip() for x in request.headers.get("x-forwarded-for", "").split(",") if x.strip()]
        for ip in reversed(parts):
            if not ip.startswith(("172.30.32.", "172.30.33.")):
                return ip
        if parts:
            return parts[0]
    return host


def device(fq, ip: str) -> tuple[str | None, str | None]:
    """(device name, MAC) of the address from the UniFi device trackers in Home Assistant."""
    host = getattr(fq, "planer_host", None)
    if not ip or host is None:
        return None, None
    best = None
    for st in host.hass.states.async_all("device_tracker"):
        a = st.attributes or {}
        if str(a.get("ip") or a.get("ip_address") or "") != ip:
            continue
        cand = (a.get("friendly_name") or a.get("host_name") or a.get("hostname") or st.entity_id,
                a.get("mac") or a.get("mac_address"))
        if st.state == "home" or best is None:          # an online tracker wins over an old one with the same IP
            best = cand
    return best or (None, None)


def record(fq, request, kind: str, profile_id: int | None, ok: bool) -> None:
    ip = client_ip(request)
    name, mac = device(fq, ip)
    fq.db.x("INSERT INTO login_log(kind, profile_id, ok, ip, device, mac) VALUES(?,?,?,?,?,?)",
            kind, profile_id, int(bool(ok)), ip or None, name, mac)
    from .privacy import login_cap_days                 # kept longer when the parents keep the login log longer (Privacy)
    keep = login_cap_days(fq.db, KEEP_DAYS)
    if keep is not None:
        fq.db.x("DELETE FROM login_log WHERE at < datetime('now','localtime',?)", f"-{keep} days")


def failures(fq, days: int = 30, limit: int = 100) -> list[dict]:
    """Failed logins, newest first, with the profile that normally logs in successfully from that address."""
    rows = fq.db.q(
        """SELECT l.*, p.name AS profile_name FROM login_log l LEFT JOIN profile p ON p.id = l.profile_id
           WHERE l.ok = 0 AND l.at >= datetime('now','localtime',?) ORDER BY l.id DESC LIMIT ?""", f"-{days} days", limit)
    usual: dict[str, dict | None] = {}
    for r in rows:
        ip = r["ip"] or ""
        if ip not in usual:
            u = fq.db.q1(
                """SELECT p.name, COUNT(*) AS n, MAX(l.at) AS last FROM login_log l JOIN profile p ON p.id = l.profile_id
                   WHERE l.ok = 1 AND l.ip = ? GROUP BY l.profile_id ORDER BY n DESC, last DESC LIMIT 1""", ip) if ip else None
            usual[ip] = u
        r["usual"] = usual[ip]
    return rows
