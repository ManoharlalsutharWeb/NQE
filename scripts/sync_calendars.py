#!/usr/bin/env python3
"""Build public, static calendar JSON from official BLS and BEA iCalendar feeds."""
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "site" / "data" / "events.json"
MAX_BYTES = 4 * 1024 * 1024
SOURCES = {
    "BLS": {"url": "https://www.bls.gov/schedule/news_release/bls.ics", "page": "https://www.bls.gov/schedule/news_release/"},
    "BEA": {"url": "https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics", "page": "https://www.bea.gov/news/schedule"},
}


def unfold(text: str) -> list[str]:
    lines, out = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").split("\n"), []
    for line in lines:
        if line.startswith((" ", "\t")) and out:
            out[-1] += line[1:]
        else:
            out.append(line)
    return out


def unescape(value: str) -> str:
    return value.replace("\\n", " ").replace("\\N", " ").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def parse_start(property_part: str, value: str):
    params = {}
    for item in property_part.split(";")[1:]:
        if "=" in item:
            k, v = item.split("=", 1)
            params[k.upper()] = v.strip('"')
    if params.get("VALUE", "").upper() == "DATE" or re.fullmatch(r"\d{8}", value.strip()):
        return None  # no invented time for all-day items
    value = value.strip()
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    try:
        zone = ZoneInfo(params.get("TZID", "America/New_York"))
    except Exception:
        zone = ZoneInfo("America/New_York")
    return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=zone).astimezone(timezone.utc)


def category_for(title: str):
    text = title.casefold()
    if any(x in text for x in ("consumer price index", "producer price index", "personal income and outlays", "personal consumption expenditures", "pce price", "price index")):
        return "inflation"
    if any(x in text for x in ("employment situation", "employment cost index", "job openings", "real earnings", "payroll", "wage", "unemployment")):
        return "labor"
    if any(x in text for x in ("gross domestic product", "gdp", "international trade in goods and services", "personal income", "retail sales", "business inventories")):
        return "growth"
    return None


def parse_ics(text: str, source_name: str, now_utc=None):
    now_utc = now_utc or datetime.now(timezone.utc)
    out, current = [], None
    for line in unfold(text):
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current is None:
                continue
            title = unescape(current.get("SUMMARY", ("", ""))[1]).replace("\n", " ").strip()
            uid = unescape(current.get("UID", ("", ""))[1]).strip()
            start = current.get("DTSTART")
            status = current.get("STATUS", ("", ""))[1].upper()
            when = parse_start(*start) if start else None
            category = category_for(title)
            if status != "CANCELLED" and category and when and when >= now_utc - timedelta(days=14):
                if not uid:
                    uid = hashlib.sha256(f"{source_name}|{title}|{when.isoformat()}".encode()).hexdigest()
                url = current.get("URL", ("", ""))[1].strip()
                if not re.match(r"^https?://", url, re.I):
                    url = SOURCES[source_name]["page"]
                out.append({
                    "id": f"{source_name}:{uid}", "uid": uid, "source": source_name,
                    "title": title[:180], "category": category,
                    "start_utc": when.isoformat(timespec="seconds"), "source_url": url,
                })
            current = None
            continue
        if current is None or ":" not in line:
            continue
        prop, value = line.split(":", 1)
        name = prop.split(";", 1)[0].upper()
        if name in {"SUMMARY", "UID", "URL", "STATUS"}:
            current[name] = (prop, value)
        elif name == "DTSTART":
            current[name] = (prop, value)
    return out


def fetch_ics(url: str) -> str:
    request = Request(url, headers={"User-Agent": "NQ-Gold-Calendar/0.2", "Accept": "text/calendar, text/plain;q=0.9"})
    with urlopen(request, timeout=25) as response:
        payload = response.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise ValueError("Calendar file exceeded 4 MB limit")
    text = payload.decode("utf-8-sig", "replace")
    if "BEGIN:VCALENDAR" not in text:
        raise ValueError("Source did not return an iCalendar feed")
    return text


def update_calendar(now_utc=None):
    now_utc = now_utc or datetime.now(timezone.utc)
    prior = {"events": [], "sources": []}
    if DATA_FILE.exists():
        try:
            prior = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    prior_events = prior.get("events", [])
    statuses, by_source = [], {}
    for name, config in SOURCES.items():
        try:
            parsed = parse_ics(fetch_ics(config["url"]), name, now_utc)
            by_source[name] = parsed
            statuses.append({"name": name, "status": "ok", "message": f"{len(parsed)} relevant items checked", "checked_utc": now_utc.isoformat(timespec="seconds"), "source_url": config["page"]})
        except Exception as exc:
            by_source[name] = [e for e in prior_events if e.get("source") == name]
            statuses.append({"name": name, "status": "error", "message": str(exc)[:250], "checked_utc": now_utc.isoformat(timespec="seconds"), "source_url": config["page"]})
    events = {}
    for source_events in by_source.values():
        for event in source_events:
            events[event["id"]] = event
    result = {
        "generated_utc": now_utc.isoformat(timespec="seconds"),
        "timezone_display": "Asia/Kolkata",
        "sources": statuses,
        "events": sorted(events.values(), key=lambda x: x["start_utc"]),
    }
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result

if __name__ == "__main__":
    data = update_calendar()
    print(f"Saved {len(data['events'])} events to {DATA_FILE}")
    for source in data["sources"]:
        print(f"{source['name']}: {source['status']} — {source['message']}")
