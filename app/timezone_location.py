from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from importlib.resources import files
from zoneinfo import ZoneInfo

import geonamescache

from .calendar_ops import validate_demo_timezone
from .services import server_utc_now


_GC = geonamescache.GeonamesCache(min_city_population=15000)
_COMMON_COUNTRY_ALIASES = {
    "usa": "US",
    "u s a": "US",
    "united states of america": "US",
    "uk": "GB",
    "u k": "GB",
    "great britain": "GB",
    "britain": "GB",
    "uae": "AE",
    "u a e": "AE",
}


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", (value or "").strip().casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


@lru_cache(maxsize=1)
def _countries() -> dict[str, dict]:
    return _GC.get_countries()


@lru_cache(maxsize=1)
def _country_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for code, row in _countries().items():
        for value in (
            code,
            row.get("iso"),
            row.get("iso3"),
            row.get("fips"),
            row.get("name"),
        ):
            key = _normalize(str(value or ""))
            if key:
                aliases[key] = code
    aliases.update(_COMMON_COUNTRY_ALIASES)
    return aliases


@lru_cache(maxsize=1)
def _country_zones() -> dict[str, tuple[str, ...]]:
    mapping: dict[str, list[str]] = {}
    zone_tab = files("tzdata").joinpath("zoneinfo", "zone.tab").read_text(encoding="utf-8")
    for raw in zone_tab.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        country_code, timezone_name = parts[0].strip(), parts[2].strip()
        try:
            validate_demo_timezone(timezone_name)
        except ValueError:
            continue
        mapping.setdefault(country_code, []).append(timezone_name)
    return {code: tuple(sorted(set(zones))) for code, zones in mapping.items()}


@lru_cache(maxsize=1)
def _zone_country_codes() -> dict[str, tuple[str, ...]]:
    reverse: dict[str, list[str]] = {}
    for country_code, zones in _country_zones().items():
        for zone in zones:
            reverse.setdefault(zone, []).append(country_code)
    return {zone: tuple(sorted(set(codes))) for zone, codes in reverse.items()}


@lru_cache(maxsize=1)
def _us_states() -> dict[str, dict]:
    return _GC.get_us_states()


@lru_cache(maxsize=1)
def _us_state_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for code, row in _us_states().items():
        aliases[_normalize(code)] = code
        aliases[_normalize(str(row.get("name") or ""))] = code
    return aliases


def _country_name(code: str) -> str:
    row = _countries().get(code) or {}
    return str(row.get("name") or code)


def _country_code_for_token(value: str) -> str:
    return _country_aliases().get(_normalize(value), "")


def _offset_label(timezone_name: str) -> str:
    try:
        local_now = server_utc_now().astimezone(ZoneInfo(timezone_name))
    except Exception:
        return ""
    offset = local_now.utcoffset()
    if offset is None:
        return ""
    minutes = int(offset.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    minutes = abs(minutes)
    hours, remainder = divmod(minutes, 60)
    return f"UTC{sign}{hours}" + (f":{remainder:02d}" if remainder else "")


def _result(*, location: str, country_code: str, timezone_name: str, kind: str, population: int = 0) -> dict:
    country = _country_name(country_code) if country_code else ""
    display = location.strip()
    if country and _normalize(country) not in _normalize(display):
        display = f"{display}, {country}" if display else country
    return {
        "location": display,
        "country": country,
        "country_code": country_code,
        "timezone": timezone_name,
        "offset": _offset_label(timezone_name),
        "kind": kind,
        "population": int(population or 0),
    }


def timezone_display_location(timezone_name: str) -> str:
    result = _iana_fallback_result(timezone_name)
    return str(result.get("location") or timezone_name) if result else (timezone_name or "")


def timezone_offset_label(timezone_name: str) -> str:
    return _offset_label(timezone_name)


def _iana_fallback_result(query: str) -> dict | None:
    candidate = (query or "").strip()
    if not candidate:
        return None
    try:
        timezone_name = validate_demo_timezone(candidate)
    except ValueError:
        return None
    if not timezone_name:
        return None
    codes = _zone_country_codes().get(timezone_name, ())
    country_code = codes[0] if len(codes) == 1 else ""
    city = timezone_name.split("/")[-1].replace("_", " ")
    if timezone_name == "UTC":
        city = "UTC"
    return _result(
        location=city,
        country_code=country_code,
        timezone_name=timezone_name,
        kind="timezone",
    )


def _split_location_query(query: str) -> tuple[str, str]:
    raw = (query or "").strip()
    if "," in raw:
        left, right = raw.rsplit(",", 1)
        country_code = _country_code_for_token(right)
        if country_code:
            return left.strip(), country_code

    normalized = _normalize(raw)
    alias_items = sorted(_country_aliases().items(), key=lambda item: len(item[0]), reverse=True)
    for alias, country_code in alias_items:
        if normalized == alias:
            return "", country_code
        suffix = " " + alias
        if normalized.endswith(suffix):
            city_text = normalized[: -len(suffix)].strip()
            if city_text:
                return city_text, country_code
    return raw, ""


def _city_exact(record: dict, query: str) -> bool:
    wanted = _normalize(query)
    if not wanted:
        return False
    values = [record.get("name")]
    values.extend(record.get("alternatenames") or [])
    return any(_normalize(str(value or "")) == wanted for value in values)


def _city_result(record: dict) -> dict | None:
    timezone_name = str(record.get("timezone") or "").strip()
    country_code = str(record.get("countrycode") or "").strip()
    name = str(record.get("name") or "").strip()
    if not timezone_name or not name:
        return None
    try:
        validate_demo_timezone(timezone_name)
    except ValueError:
        return None

    location = name
    if country_code == "US":
        state_code = str(record.get("admin1code") or "").strip()
        state = _us_states().get(state_code) or {}
        state_name = str(state.get("name") or "").strip()
        if state_name and _normalize(state_name) != _normalize(name):
            location = f"{name}, {state_name}"
    return _result(
        location=location,
        country_code=country_code,
        timezone_name=timezone_name,
        kind="city",
        population=int(record.get("population") or 0),
    )


def _state_results(state_code: str) -> list[dict]:
    state = _us_states().get(state_code) or {}
    state_name = str(state.get("name") or state_code)
    zone_populations: dict[str, int] = {}
    for city in _GC.get_cities().values():
        if city.get("countrycode") != "US" or str(city.get("admin1code") or "") != state_code:
            continue
        timezone_name = str(city.get("timezone") or "")
        if not timezone_name:
            continue
        zone_populations[timezone_name] = zone_populations.get(timezone_name, 0) + int(city.get("population") or 0)
    return [
        _result(
            location=state_name,
            country_code="US",
            timezone_name=zone,
            kind="state",
            population=population,
        )
        for zone, population in sorted(zone_populations.items(), key=lambda item: (-item[1], item[0]))
    ]


def _country_choices(country_code: str, limit: int = 12) -> list[dict]:
    best_by_zone: dict[str, dict] = {}
    for city in _GC.get_cities().values():
        if str(city.get("countrycode") or "") != country_code:
            continue
        result = _city_result(city)
        if not result:
            continue
        existing = best_by_zone.get(result["timezone"])
        if existing is None or result["population"] > existing["population"]:
            best_by_zone[result["timezone"]] = result

    ordered = sorted(best_by_zone.values(), key=lambda item: (-item["population"], item["location"]))
    if ordered:
        return ordered[:limit]

    return [
        _result(
            location=_country_name(country_code),
            country_code=country_code,
            timezone_name=zone,
            kind="country-zone",
        )
        for zone in _country_zones().get(country_code, ())[:limit]
    ]


def _country_result(country_code: str) -> dict:
    country = _countries().get(country_code) or {}
    country_name = _country_name(country_code)
    zones = _country_zones().get(country_code, ())
    if len(zones) == 1:
        capital = str(country.get("capital") or "").strip()
        location = capital or country_name
        result = _result(
            location=location,
            country_code=country_code,
            timezone_name=zones[0],
            kind="country",
        )
        return {
            "status": "resolved",
            "message": "",
            "auto_select": True,
            "results": [result],
        }

    if len(zones) > 1:
        return {
            "status": "ambiguous",
            "message": "Add a city or state/province to identify the exact time zone.",
            "auto_select": False,
            "results": _country_choices(country_code),
        }

    return {
        "status": "not_found",
        "message": "No time zone could be identified for this country.",
        "auto_select": False,
        "results": [],
    }


@lru_cache(maxsize=256)
def resolve_location_query(query: str) -> dict:
    raw = (query or "").strip()
    if len(raw) < 2:
        return {
            "status": "empty",
            "message": "Type a city, state/province, or country.",
            "auto_select": False,
            "results": [],
        }

    iana_result = _iana_fallback_result(raw)
    if iana_result:
        return {
            "status": "resolved",
            "message": "",
            "auto_select": True,
            "results": [iana_result],
        }

    city_text, country_code = _split_location_query(raw)
    if not city_text and country_code:
        return _country_result(country_code)

    whole_country_code = _country_code_for_token(raw)
    whole_state_code = _us_state_aliases().get(_normalize(raw))
    if whole_country_code and whole_state_code:
        country_result = _country_result(whole_country_code)
        combined = list(country_result.get("results") or []) + _state_results(whole_state_code)
        return {
            "status": "matches",
            "message": "Choose the correct country or state.",
            "auto_select": False,
            "results": combined[:12],
        }
    if whole_country_code:
        return _country_result(whole_country_code)

    normalized_city = _normalize(city_text)
    exact_results: list[dict] = []

    state_code = _us_state_aliases().get(normalized_city)
    if state_code and (not country_code or country_code == "US"):
        exact_results.extend(_state_results(state_code))

    city_matches = []
    city_matches.extend(
        _GC.search_cities(
            city_text,
            attribute="name",
            case_sensitive=False,
            contains_search=True,
        )
    )
    city_matches.extend(
        _GC.search_cities(
            city_text,
            attribute="alternatenames",
            case_sensitive=False,
            contains_search=True,
        )
    )
    city_matches = sorted(city_matches, key=lambda row: int(row.get("population") or 0), reverse=True)

    seen = set()
    matching_results: list[dict] = []
    for city in city_matches:
        if country_code and str(city.get("countrycode") or "") != country_code:
            continue
        result = _city_result(city)
        if not result:
            continue
        key = (result["location"], result["timezone"])
        if key in seen:
            continue
        seen.add(key)
        matching_results.append(result)
        if _city_exact(city, city_text):
            exact_results.append(result)
        if len(matching_results) >= 30:
            break

    if exact_results:
        deduped: list[dict] = []
        exact_seen = set()
        for item in sorted(exact_results, key=lambda item: (-item["population"], item["location"])):
            key = (item["location"], item["timezone"])
            if key not in exact_seen:
                exact_seen.add(key)
                deduped.append(item)

        unique_timezones = {item["timezone"] for item in deduped}
        unique_countries = {item["country_code"] for item in deduped}
        if len(unique_timezones) == 1 and len(unique_countries) == 1:
            return {
                "status": "resolved",
                "message": "",
                "auto_select": True,
                "results": [deduped[0]],
            }
        return {
            "status": "matches",
            "message": "Choose the correct location.",
            "auto_select": False,
            "results": deduped[:12],
        }

    if matching_results:
        return {
            "status": "matches",
            "message": "Choose the correct location.",
            "auto_select": False,
            "results": matching_results[:12],
        }

    return {
        "status": "not_found",
        "message": "No matching location found. Try adding the city and country.",
        "auto_select": False,
        "results": [],
    }
