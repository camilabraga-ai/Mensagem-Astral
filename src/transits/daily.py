"""Pipeline da mensagem diária: mapa natal + data -> trânsitos -> RAG -> LLM -> cache."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from src.data.kb import KnowledgeBase
from src.rag.generator import LLM, LLMError, check_faithfulness
from src.transits import prompt as prompt_mod
from src.transits.cache import DailyCache, person_key
from src.transits.prompt import build_daily_prompt
from src.transits.retrieval import DailyContext, build_daily_context
from src.transits.select import TOP_N, transit_key


@dataclass
class DailyMessage:
    text: str
    day: date
    context: DailyContext
    warnings: list[str] = field(default_factory=list)
    from_cache: bool = False
    usage: dict | None = None
    system: str = ""
    user: str = ""


def daily_message(kb: KnowledgeBase, chart: dict, day: date, llm: LLM, cache: DailyCache | None = None,
                  force: bool = False, top_n: int = TOP_N, recent_days: int = 2) -> DailyMessage:
    """Mensagem do dia. Com `cache`, a segunda consulta do mesmo dia não chama o LLM (nem custa nada)."""
    person = person_key(chart)
    model = getattr(llm, "model", type(llm).__name__)
    recents = cache.recent(person, day, recent_days) if cache else []
    recent_keys = {tuple(k) for r in recents for k in r.get("transits", [])}

    ctx = build_daily_context(kb, chart, day, recent=recent_keys, top_n=top_n)
    if ctx.missing:
        raise LLMError(f"Base sem documentos para: {ctx.missing}")
    system, user = build_daily_prompt(ctx, [r["message"] for r in recents])

    if cache and not force:
        hit = cache.get(person, day, model, prompt_mod.PROMPT_VERSION)
        if hit:
            return DailyMessage(hit["message"], day, ctx, hit.get("warnings", []), True, hit.get("usage"), system, user)

    text = llm.complete(system, user)
    warnings = check_faithfulness(text, ctx.for_faithfulness())
    usage = getattr(llm, "last_usage", None)
    if cache:
        try:
            cache.set(person, day, {
                "date": day.isoformat(), "model": model, "prompt_version": prompt_mod.PROMPT_VERSION,
                "message": text, "warnings": warnings, "usage": usage,
                "transits": [list(transit_key(t.aspect)) for t in ctx.transits]})
        except OSError:
            pass        # disco cheio ou sem permissão: a mensagem já foi gerada (e paga), então ainda é entregue
    return DailyMessage(text, day, ctx, warnings, False, usage, system, user)
