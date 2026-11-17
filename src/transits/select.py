"""Seleção dos trânsitos mais relevantes do dia (critérios simples, documentados e testáveis).

pontuação = peso_do_aspecto x peso_do_planeta x peso_do_ponto_natal x fator_de_orbe
  - aspecto: conjunção/oposição são os mais fortes; sextil, o mais suave.
  - planeta em trânsito: planetas lentos e Marte pesam mais (marcam o período); Mercúrio pesa menos.
  - ponto natal: Sol e Lua são o núcleo do mapa; o Ascendente vem logo depois.
  - fator de orbe: 1.0 quando exato, cai linearmente até 0 no orbe máximo do planeta (MAX_ORB).
Novidade: trânsitos lentos duram semanas e dominariam todos os dias. Os que já foram destaque nos dias recentes
(`recent`) têm a pontuação multiplicada por RECENT_PENALTY, abrindo espaço para outros trânsitos.
Seleciona os `top_n` melhores com pontuação >= MIN_SCORE. Desempate: maior pontuação, menor orbe, ordem estável.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.transits.calc import MAX_ORB, TransitAspect

ASPECT_WEIGHT = {"conjunction": 1.0, "opposition": 1.0, "square": 0.9, "trine": 0.7, "sextile": 0.5}
PLANET_WEIGHT = {"sun": 0.8, "moon": 0.7, "mercury": 0.6, "venus": 0.7, "mars": 0.9,
                 "jupiter": 1.0, "saturn": 1.0, "uranus": 0.9, "neptune": 0.8, "pluto": 0.9}
TARGET_WEIGHT = {"sun": 1.0, "moon": 1.0, "ascendant": 0.9}
MIN_SCORE = 0.15
TOP_N = 3
RECENT_PENALTY = 0.6


@dataclass(frozen=True)
class ScoredTransit:
    aspect: TransitAspect
    score: float

    @property
    def exact(self) -> bool:
        return self.aspect.orb < 1.0


def score(a: TransitAspect) -> float:
    orb_factor = max(0.0, 1.0 - a.orb / MAX_ORB[a.transit])
    return round(ASPECT_WEIGHT[a.aspect] * PLANET_WEIGHT[a.transit] * TARGET_WEIGHT[a.natal] * orb_factor, 4)


def transit_key(a: TransitAspect) -> tuple[str, str, str]:
    return (a.transit, a.natal, a.aspect)


def select_transits(aspects: list[TransitAspect], top_n: int = TOP_N, min_score: float = MIN_SCORE,
                    recent: frozenset | set = frozenset()) -> list[ScoredTransit]:
    scored = [ScoredTransit(a, round(score(a) * (RECENT_PENALTY if transit_key(a) in recent else 1.0), 4))
              for a in aspects]
    scored = [s for s in scored if s.score >= min_score]
    scored.sort(key=lambda s: (-s.score, s.aspect.orb, s.aspect.transit, s.aspect.natal, s.aspect.aspect))
    return scored[:top_n]
