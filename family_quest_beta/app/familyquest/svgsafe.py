"""Strict cleaning of SVG pictures that come from a family member or an AI (picture books, picturebooks.py).

Only plain drawing survives: an allow-list of shape elements and presentation attributes. Everything else is dropped –
<script>, <foreignObject>, <image>, <use>, <style>, <a>, animation, every `on…` event handler, every `href`, every
`style` attribute, every reference that is not an internal `url(#id)`. A DOCTYPE or an entity makes the whole picture
invalid (no entity tricks). The result is written out again from the cleaned tree (never the original text), so nothing
the parser did not understand can pass. The app shows these pictures only as an <img> (data URL) on top of that, where
a browser never runs scripts or loads anything.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape, quoteattr

SVG_NS = "http://www.w3.org/2000/svg"
SVG_MAX = 12_000                 # characters of one cleaned picture
RAW_MAX = 40_000                 # characters before cleaning (comments, white space and dropped parts included)
MAX_NODES = 600
MAX_DEPTH = 16

TAGS = {"svg", "g", "path", "circle", "ellipse", "rect", "line", "polyline", "polygon", "defs", "linearGradient",
        "radialGradient", "stop", "clipPath", "text", "tspan"}
ATTRS = {
    "id", "viewBox", "preserveAspectRatio", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "fx", "fy",
    "width", "height", "d", "points", "transform", "fill", "fill-opacity", "fill-rule", "stroke", "stroke-width",
    "stroke-opacity", "stroke-linecap", "stroke-linejoin", "stroke-dasharray", "stroke-dashoffset", "stroke-miterlimit",
    "opacity", "offset", "stop-color", "stop-opacity", "gradientUnits", "gradientTransform", "spreadMethod",
    "clip-path", "clip-rule", "clipPathUnits", "font-size", "font-weight", "font-style", "font-family", "text-anchor",
    "dominant-baseline", "letter-spacing", "dx", "dy", "rotate", "paint-order",
}
TEXT_TAGS = {"text", "tspan"}
_URL = re.compile(r"url\(\s*#[A-Za-z_][\w.-]*\s*\)")
_BAD = re.compile(r"javascript|vbscript|data:|expression|@import|\\|<|>|&|url\(", re.I)
_ID = re.compile(r"[A-Za-z_][\w.-]{0,40}")
_NUMS = re.compile(r"\s*-?[\d.]+(?:[\s,]+-?[\d.]+){3}\s*")


class SvgError(ValueError):
    pass


def _local(tag: str) -> str | None:
    """The element name without the SVG namespace – None for any other namespace."""
    if not isinstance(tag, str):
        return None                                   # comments, processing instructions
    if tag.startswith("{"):
        ns, _, name = tag[1:].partition("}")
        return name if ns == SVG_NS else None
    return tag


def _value(name: str, v: str) -> str | None:
    v = " ".join(str(v).split())
    if not v or len(v) > 6000:
        return None
    if name == "id":
        return v if _ID.fullmatch(v) else None
    if "url(" in v.lower():                           # only references inside the picture: fill="url(#sky)"
        if name not in ("fill", "stroke", "clip-path") or not _URL.fullmatch(v):
            return None
        return v
    if name == "font-family":
        v = re.sub(r"[^\w ,'-]", "", v)[:60]
        return v or None
    return None if _BAD.search(v) else v


def clean_svg(raw) -> str:
    """The cleaned picture (a string `<svg xmlns=… viewBox=…>…</svg>`) – or SvgError when it is not a usable SVG."""
    if not isinstance(raw, str):
        raise SvgError("not text")
    raw = raw.strip()
    if len(raw) > RAW_MAX:
        raise SvgError("too large")
    if re.search(r"<!DOCTYPE|<!ENTITY|<\?xml-stylesheet", raw, re.I):
        raise SvgError("DOCTYPE / entity")
    raw = re.sub(r"^<\?xml[^>]*\?>\s*", "", raw)
    try:
        root = ET.fromstring(raw)
    except (ET.ParseError, ValueError, RecursionError):
        raise SvgError("not valid XML") from None
    if _local(root.tag) != "svg":
        raise SvgError("not an SVG")
    count = 0

    def attrs(el, name: str) -> dict[str, str]:
        out = {}
        for k, v in el.attrib.items():
            if k.startswith("{") or k not in ATTRS:   # xlink:href, xml:base, on…, style, class, href …
                continue
            if name == "svg" and k in ("width", "height", "x", "y"):
                continue                              # the app sizes the picture
            cv = _value(k, v)
            if cv is not None:
                out[k] = cv
        return out

    def walk(el, depth: int) -> str:
        nonlocal count
        name = _local(el.tag)
        if name not in TAGS or depth > MAX_DEPTH:
            return ""
        count += 1
        if count > MAX_NODES:
            raise SvgError("too many parts")
        a = attrs(el, name)
        if name == "svg" and depth == 0:
            vb = a.get("viewBox") or ""
            if not _NUMS.fullmatch(vb):
                w, h = el.attrib.get("width", ""), el.attrib.get("height", "")
                if re.fullmatch(r"\d+(\.\d+)?", w) and re.fullmatch(r"\d+(\.\d+)?", h):
                    vb = f"0 0 {w} {h}"
                else:
                    raise SvgError("no viewBox")
            a["viewBox"] = " ".join(re.split(r"[\s,]+", vb.strip()))
        inner = []
        if name in TEXT_TAGS and el.text and el.text.strip():
            inner.append(escape(el.text.strip()[:200]))
        for c in el:
            inner.append(walk(c, depth + 1))
            if name in TEXT_TAGS and c.tail and c.tail.strip():
                inner.append(escape(c.tail.strip()[:200]))
        tag = "svg" if name == "svg" else name
        head = "<" + tag + ("" if depth else f' xmlns="{SVG_NS}"') + "".join(f" {k}={quoteattr(v)}" for k, v in a.items())
        body = "".join(inner)
        return head + (">" + body + f"</{tag}>" if body else "/>")

    out = walk(root, 0)
    if len(out) > SVG_MAX:
        raise SvgError("too large")
    return out


def safe_svg(raw) -> str | None:
    try:
        return clean_svg(raw)
    except SvgError:
        return None
