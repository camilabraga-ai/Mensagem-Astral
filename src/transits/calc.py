"""Trânsitos: posições dos planetas numa data (Kerykeion) e aspectos com pontos do mapa natal.

Posições: calculadas pelo Kerykeion para o MEIO-DIA local (fuso do local de nascimento), zodíaco tropical.
A Lua anda ~13°/dia, então a hora de referência importa para ela; o meio-dia é uma convenção documentada.
Aspectos: calculados aqui a partir das longitudes (separação angular vs. ângulos 0/60/90/120/180).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.astrology.chart import PLANETS, PLANETS_PT, SIGNS_PT
from src.data.kb import ASPECT_PT_TO_EN, SIGN_PT_TO_EN

NATAL_TARGETS = ("sun", "moon", "ascendant")
ASPECT_ANGLES = {"conjunction": 0, "sextile": 60, "square": 90, "trine": 120, "opposition": 180}
ASPECT_PT = {v: k for k, v in ASPECT_PT_TO_EN.items()}          # inglês -> português
# Orbe máximo (graus) por planeta em trânsito: luminares e planetas lentos têm orbes maiores.
MAX_ORB = {"sun": 5.0, "moon": 4.0, "mercury": 3.0, "venus": 3.0, "mars": 4.0,
           "jupiter": 4.0, "saturn": 4.0, "uranus": 3.0, "neptune": 3.0, "pluto": 3.0}


@dataclass(frozen=True)
class TransitPlanet:
    key: str
    label: str
    sign_pt: str
    sign: str                # inglês (chave da base)
    longitude: float
    degree: float            # grau dentro do signo
    retrograde: bool


@dataclass(frozen=True)
class TransitAspect:
    transit: str             # planeta em trânsito (chave)
    natal: str               # ponto natal (chave)
    aspect: str              # inglês (chave da base)
    orb: float

    @property
    def aspect_pt(self) -> str:
        return ASPECT_PT[self.aspect]


def transit_positions(chart: dict, day: date, hour: int = 12) -> list[TransitPlanet]:
    """Posições dos 10 planetas em `day` (meio-dia no fuso e local do nascimento descritos em `chart`)."""
    from kerykeion import AstrologicalSubjectFactory

    n = chart["nascimento"]
    s = AstrologicalSubjectFactory.from_birth_data(
        "transito", day.year, day.month, day.day, hour, 0,
        lng=n["longitude"], lat=n["latitude"], tz_str=n["fuso"], online=False)
    out = []
    for k in PLANETS:
        p = getattr(s, k)
        sign_pt = SIGNS_PT[p.sign]
        out.append(TransitPlanet(k, PLANETS_PT[k], sign_pt, SIGN_PT_TO_EN[sign_pt],
                                 round(p.abs_pos, 4), round(p.position, 4), bool(p.retrograde)))
    return out


def natal_targets(chart: dict, keys=NATAL_TARGETS) -> dict[str, float]:
    """Longitudes dos pontos natais escolhidos (Sol, Lua, Ascendente por padrão)."""
    pts = {p["id"]: p["longitude"] for p in chart["planetas"] + chart["angulos"]}
    missing = [k for k in keys if k not in pts]
    if missing:
        raise KeyError(f"pontos natais ausentes no mapa: {missing}")
    return {k: pts[k] for k in keys}


def separation(a: float, b: float) -> float:
    """Menor distância angular entre duas longitudes (0 a 180)."""
    d = abs(a - b) % 360
    return 360 - d if d > 180 else d


def find_aspects(positions: list[TransitPlanet], targets: dict[str, float]) -> list[TransitAspect]:
    out = []
    for p in positions:
        for nkey, nlon in targets.items():
            sep = separation(p.longitude, nlon)
            for name, angle in ASPECT_ANGLES.items():
                orb = abs(sep - angle)
                if orb <= MAX_ORB[p.key]:
                    out.append(TransitAspect(p.key, nkey, name, round(orb, 3)))
    return out
