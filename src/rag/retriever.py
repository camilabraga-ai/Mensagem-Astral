"""Recuperação estruturada (sem embeddings): posicionamentos do mapa -> documentos da base.

Entrada: dict do mapa gerado por src.astrology.chart.calculate_chart.
Saída: RetrievedContext com (a) os fatos CALCULADOS e (b) os documentos recuperados por metadados.
Nada aqui chama LLM. Tudo que a geração pode afirmar vem destes dois conjuntos.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.astrology.chart import PLANETS_PT
from src.data.kb import ASPECT_PT_TO_EN, SIGN_PT_TO_EN, KnowledgeBase

DEFAULT_POINTS = ("sun", "moon", "ascendant")
_LABEL_TO_KEY = {v: k for k, v in PLANETS_PT.items()}   # "Sol" -> "sun", "Ascendente" -> "ascendant"


@dataclass(frozen=True)
class Placement:
    key: str                 # sun, moon, ascendant
    label: str               # Sol, Lua, Ascendente
    sign_pt: str
    sign: str                # em inglês, chave da base
    degree: float            # grau dentro do signo
    house: int | None        # None para o Ascendente
    retrograde: bool | None


@dataclass(frozen=True)
class ChartAspect:
    p1: str
    p2: str
    aspect_pt: str
    aspect: str              # em inglês, chave da base
    orb: float


@dataclass
class RetrievedContext:
    placements: list[Placement]
    aspects: list[ChartAspect]
    docs: list[tuple[str, dict]] = field(default_factory=list)   # (motivo, documento), sem repetição
    missing: list[str] = field(default_factory=list)             # consultas sem documento na base

    @property
    def doc_ids(self) -> list[str]:
        return [d["id"] for _, d in self.docs]

    def signs(self) -> set[str]:
        return {p.sign_pt for p in self.placements}


def extract_placements(chart: dict, keys=DEFAULT_POINTS) -> list[Placement]:
    points = {p["id"]: p for p in chart["planetas"] + chart["angulos"]}
    out = []
    for k in keys:
        if k not in points:
            raise KeyError(f"'{k}' não está no mapa (disponíveis: {sorted(points)})")
        p = points[k]
        out.append(Placement(
            key=k, label=p["nome"], sign_pt=p["signo"], sign=SIGN_PT_TO_EN[p["signo"]],
            degree=p["grau_no_signo"], house=None if k == "ascendant" else p["casa"],
            retrograde=None if k == "ascendant" else p["retrogrado"]))
    return out


def extract_aspects(chart: dict, keys=DEFAULT_POINTS) -> list[ChartAspect]:
    """Aspectos calculados entre os pontos escolhidos (nomes em português do motor -> chaves)."""
    wanted, out = set(keys), []
    for a in chart["aspectos"]:
        k1, k2 = _LABEL_TO_KEY.get(a["planeta_1"]), _LABEL_TO_KEY.get(a["planeta_2"])
        if k1 in wanted and k2 in wanted and a["aspecto"] in ASPECT_PT_TO_EN:
            out.append(ChartAspect(k1, k2, a["aspecto"], ASPECT_PT_TO_EN[a["aspecto"]], a["orbe"]))
    return out


def retrieve(kb: KnowledgeBase, chart: dict, keys=DEFAULT_POINTS) -> RetrievedContext:
    ctx = RetrievedContext(extract_placements(chart, keys), extract_aspects(chart, keys))
    seen: set[str] = set()

    def add(reason: str, **entidades):
        found = kb.lookup(**entidades)
        if not found:
            ctx.missing.append(f"{reason}: {entidades}")
        for d in found:
            if d["id"] not in seen:
                seen.add(d["id"])
                ctx.docs.append((reason, d))

    for p in ctx.placements:
        if p.key == "ascendant":
            add(f"{p.label} em {p.sign_pt}", elemento="ascendant", signo=p.sign)
            add(f"significado geral de {p.label}", elemento="ascendant")
        else:
            add(f"{p.label} em {p.sign_pt}", planeta=p.key, signo=p.sign)
            add(f"significado geral de {p.label}", planeta=p.key)
            add(f"{p.label} na casa {p.house}", casa=p.house)
    for sign in dict.fromkeys(p.sign for p in ctx.placements):   # ordem estável, sem repetir
        add(f"signo de {next(p.sign_pt for p in ctx.placements if p.sign == sign)}", signo=sign)
    for a in ctx.aspects:
        add(f"aspecto {a.aspect_pt} ({PLANETS_PT[a.p1]}-{PLANETS_PT[a.p2]})", aspecto=a.aspect)
    return ctx
