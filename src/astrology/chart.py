"""Motor astrológico: dados de nascimento -> mapa astral estruturado (dict/JSON).

Cálculos feitos pelo Kerykeion (Swiss Ephemeris). Zodíaco tropical, casas Placidus.
Fuso horário: resolvido pelo nome IANA (ex.: America/Sao_Paulo), que inclui o horário
de verão histórico. O horário informado é sempre o horário LOCAL do nascimento.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SIGNS_PT = {
    "Ari": "Áries", "Tau": "Touro", "Gem": "Gêmeos", "Can": "Câncer",
    "Leo": "Leão", "Vir": "Virgem", "Lib": "Libra", "Sco": "Escorpião",
    "Sag": "Sagitário", "Cap": "Capricórnio", "Aqu": "Aquário", "Pis": "Peixes",
}
PLANETS = ["sun", "moon", "mercury", "venus", "mars", "jupiter",
           "saturn", "uranus", "neptune", "pluto"]
PLANETS_PT = {
    "sun": "Sol", "moon": "Lua", "mercury": "Mercúrio", "venus": "Vênus",
    "mars": "Marte", "jupiter": "Júpiter", "saturn": "Saturno",
    "uranus": "Urano", "neptune": "Netuno", "pluto": "Plutão",
    "ascendant": "Ascendente", "medium_coeli": "Meio do Céu",
}
ASPECTS_PT = {"conjunction": "conjunção", "opposition": "oposição",
              "trine": "trígono", "square": "quadratura", "sextile": "sextil"}
HOUSES = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh",
          "eighth", "ninth", "tenth", "eleventh", "twelfth"]


@dataclass
class BirthData:
    year: int
    month: int
    day: int
    hour: int            # horário LOCAL (0-23)
    minute: int
    city: str
    nation: str
    lat: float | None = None
    lng: float | None = None
    tz_str: str | None = None   # nome IANA; se None, é descoberto pelas coordenadas


def geocode(city: str, nation: str) -> tuple[float, float, str]:
    """Cidade/país -> (latitude, longitude, fuso IANA). Requer internet (Nominatim/OSM)."""
    from geopy.geocoders import Nominatim
    from timezonefinder import TimezoneFinder

    loc = Nominatim(user_agent="mensagem-astral-estudo").geocode(f"{city}, {nation}", timeout=15)
    if loc is None:
        raise ValueError(f"Local não encontrado: {city}, {nation}")
    tz = TimezoneFinder().timezone_at(lat=loc.latitude, lng=loc.longitude)
    if tz is None:
        raise ValueError("Não foi possível determinar o fuso horário.")
    return loc.latitude, loc.longitude, tz


def resolve_birth(b: BirthData) -> BirthData:
    """Completa lat/lng/fuso se faltarem."""
    if b.lat is None or b.lng is None or b.tz_str is None:
        lat, lng, tz = geocode(b.city, b.nation)
        b = BirthData(**{**asdict(b), "lat": b.lat if b.lat is not None else lat,
                         "lng": b.lng if b.lng is not None else lng,
                         "tz_str": b.tz_str or tz})
    return b


def _point(p, key: str) -> dict:
    return {
        "id": key,
        "nome": PLANETS_PT.get(key, key),
        "signo": SIGNS_PT[p.sign],
        "grau_no_signo": round(p.position, 4),
        "longitude": round(p.abs_pos, 4),
        "casa": HOUSES.index(p.house.replace("_House", "").lower()) + 1 if p.house else None,
        "retrogrado": p.retrograde,
    }


def calculate_chart(b: BirthData) -> dict:
    """Retorna o mapa astral em dict serializável em JSON."""
    from kerykeion import AspectsFactory, AstrologicalSubjectFactory

    b = resolve_birth(b)
    local = datetime(b.year, b.month, b.day, b.hour, b.minute, tzinfo=ZoneInfo(b.tz_str))
    subject = AstrologicalSubjectFactory.from_birth_data(
        "mapa", b.year, b.month, b.day, b.hour, b.minute,
        lng=b.lng, lat=b.lat, tz_str=b.tz_str, online=False,
        city=b.city, nation=b.nation,
    )
    aspects = AspectsFactory.single_chart_aspects(subject).aspects
    pt = {k.lower(): v for k, v in PLANETS_PT.items()}
    pt.update({"chiron": "Quíron", "mean_north_lunar_node": "Nodo Norte", "true_north_lunar_node": "Nodo Norte"})
    return {
        "nascimento": {
            "horario_local": local.isoformat(),
            "horario_utc": subject.iso_formatted_utc_datetime,
            "fuso": b.tz_str,
            "offset_utc_horas": local.utcoffset().total_seconds() / 3600,
            "horario_verao": bool(local.dst()),
            "local": f"{b.city}, {b.nation}",
            "latitude": round(b.lat, 4),
            "longitude": round(b.lng, 4),
        },
        "configuracao": {"zodiaco": "tropical", "casas": "Placidus"},
        "resumo": {
            "signo_solar": SIGNS_PT[subject.sun.sign],
            "signo_lunar": SIGNS_PT[subject.moon.sign],
            "ascendente": SIGNS_PT[subject.ascendant.sign],
        },
        "planetas": [_point(getattr(subject, k), k) for k in PLANETS],
        "angulos": [_point(subject.ascendant, "ascendant"),
                    _point(subject.medium_coeli, "medium_coeli")],
        "casas": [
            {"casa": i + 1, "signo_cuspide": SIGNS_PT[getattr(subject, f"{h}_house").sign],
             "grau_cuspide": round(getattr(subject, f"{h}_house").position, 4)}
            for i, h in enumerate(HOUSES)
        ],
        "aspectos": [
            {"planeta_1": pt.get(a.p1_name.lower(), a.p1_name),
             "planeta_2": pt.get(a.p2_name.lower(), a.p2_name),
             "aspecto": ASPECTS_PT.get(a.aspect, a.aspect),
             "orbe": round(abs(a.orbit), 3)}
            for a in aspects
        ],
    }


def save_chart_json(chart: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(chart, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
