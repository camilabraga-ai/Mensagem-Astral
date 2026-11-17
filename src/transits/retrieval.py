"""Recuperação para a mensagem diária: trânsitos selecionados + mapa natal -> documentos da base.

Não existem textos de trânsito na base. Para cada trânsito selecionado usamos blocos GERAIS existentes:
  - significado geral do planeta em trânsito (planeta.X)
  - o planeta no signo em que está hoje (planeta_signo.X.signo)
  - o aspecto (aspecto.A)
  - o ponto natal alvo no signo natal (planeta_signo.sun.s / elemento_signo.ascendant.s)
Mais a Lua do dia (planeta_signo.moon.signo de hoje), que dá variação diária mesmo sem trânsitos marcantes.
Nenhum documento é criado: o que faltar na base é registrado em `missing`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from src.data.kb import KnowledgeBase
from src.rag.retriever import ChartAspect, Placement, RetrievedContext, extract_placements
from src.transits.calc import (NATAL_TARGETS, TransitPlanet, find_aspects, natal_targets,
                               transit_positions)
from src.transits.select import TOP_N, ScoredTransit, select_transits


@dataclass
class DailyContext:
    day: date
    natal: list[Placement]
    positions: dict[str, TransitPlanet]
    moon_today: TransitPlanet
    transits: list[ScoredTransit]
    docs: list[tuple[str, dict]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def doc_ids(self) -> list[str]:
        return [d["id"] for _, d in self.docs]

    def involved_planets(self) -> list[TransitPlanet]:
        keys = dict.fromkeys([t.aspect.transit for t in self.transits] + ["moon"])
        return [self.positions[k] for k in keys]

    def for_faithfulness(self) -> RetrievedContext:
        """Visão compatível com src.rag.generator.check_faithfulness: tudo que pode ser citado."""
        placements = list(self.natal) + [
            Placement(p.key, p.label, p.sign_pt, p.sign, p.degree, None, p.retrograde)
            for p in self.involved_planets()]
        aspects = [ChartAspect(t.aspect.transit, t.aspect.natal, t.aspect.aspect_pt, t.aspect.aspect, t.aspect.orb)
                   for t in self.transits]
        return RetrievedContext(placements, aspects, self.docs, self.missing)


def build_daily_context(kb: KnowledgeBase, chart: dict, day: date, recent=frozenset(),
                        top_n: int = TOP_N) -> DailyContext:
    positions = {p.key: p for p in transit_positions(chart, day)}
    natal = extract_placements(chart, NATAL_TARGETS)
    selected = select_transits(find_aspects(list(positions.values()), natal_targets(chart)), top_n, recent=recent)
    ctx = DailyContext(day, natal, positions, positions["moon"], selected)
    by_natal = {p.key: p for p in natal}
    seen: set[str] = set()

    def add(reason: str, **entidades):
        found = kb.lookup(**entidades)
        if not found:
            ctx.missing.append(f"{reason}: {entidades}")
        for d in found:
            if d["id"] not in seen:
                seen.add(d["id"])
                ctx.docs.append((reason, d))

    for t in selected:
        p, n = positions[t.aspect.transit], by_natal[t.aspect.natal]
        add(f"significado geral de {p.label} (em trânsito)", planeta=p.key)
        add(f"{p.label} em {p.sign_pt} hoje", planeta=p.key, signo=p.sign)
        add(f"aspecto {t.aspect.aspect_pt}", aspecto=t.aspect.aspect)
        if n.key == "ascendant":
            add(f"seu Ascendente natal em {n.sign_pt}", elemento="ascendant", signo=n.sign)
        else:
            add(f"seu {n.label} natal em {n.sign_pt}", planeta=n.key, signo=n.sign)
    m = ctx.moon_today
    add(f"Lua do dia em {m.sign_pt}", planeta="moon", signo=m.sign)
    return ctx
