"""Geração: contexto recuperado -> mensagem em português via LLM (injetável, testável sem rede)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from src.data.kb import KnowledgeBase
from src.rag.prompt import build_prompt
from src.rag.retriever import DEFAULT_POINTS, RetrievedContext, retrieve

DEFAULT_MODEL = "claude-haiku-5-5"   # padrão de menor custo; troque via AnthropicLLM(model=...)


class LLMError(RuntimeError):
    pass


class LLM(Protocol):
    def complete(self, system: str, user: str) -> str: ...


class AnthropicLLM:
    """Chama a API da Anthropic. Credenciais vêm do ambiente (ANTHROPIC_API_KEY). CADA CHAMADA É PAGA."""

    def __init__(self, model: str = DEFAULT_MODEL, max_tokens: int = 2000, effort: str = "low", client=None):
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        self.client, self.model, self.max_tokens, self.effort = client, model, max_tokens, effort

    def complete(self, system: str, user: str) -> str:
        resp = self.client.messages.create(
            model=self.model, max_tokens=self.max_tokens, system=system,
            output_config={"effort": self.effort},
            messages=[{"role": "user", "content": user}],
        )
        if resp.stop_reason == "refusal":
            raise LLMError(f"A API recusou a solicitação: {getattr(resp, 'stop_details', None)}")
        if resp.stop_reason == "max_tokens":
            raise LLMError("Resposta truncada (max_tokens). Aumente max_tokens.")
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        if not text:
            raise LLMError("A API não devolveu texto.")
        return text


# --- checagem de fidelidade: a mensagem só pode citar o que foi calculado ou recuperado -------------
_SIGNS = ["Áries", "Touro", "Gêmeos", "Câncer", "Leão", "Virgem", "Libra", "Escorpião", "Sagitário",
          "Capricórnio", "Aquário", "Peixes"]
_BODIES = ["Sol", "Lua", "Mercúrio", "Vênus", "Marte", "Júpiter", "Saturno", "Urano", "Netuno", "Plutão",
           "Quíron", "Ascendente", "Meio do Céu", "Nodo Norte", "Nodo Sul"]
_ASPECTS = ["conjunção", "sextil", "quadratura", "trígono", "oposição"]
# "oposição", "conjunção" e "quadratura" também são palavras comuns ("simples oposição"). Elas só contam
# como aspecto quando aparecem perto do nome de um planeta/ponto; "sextil" e "trígono" valem em qualquer uso.
_AMBIGUOUS_ASPECTS = {"conjunção", "quadratura", "oposição"}
_ASPECT_WINDOW = 60   # caracteres


def _aspect_mentions(text: str) -> set[str]:
    found = _mentions(text, _ASPECTS)
    for term in found & _AMBIGUOUS_ASPECTS:
        near = False
        for m in re.finditer(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.IGNORECASE):
            around = text[max(0, m.start() - _ASPECT_WINDOW): m.end() + _ASPECT_WINDOW]
            if _mentions(around, _BODIES):
                near = True
                break
        if not near:
            found.discard(term)
    return found


def _mentions(text: str, terms: list[str]) -> set[str]:
    return {t for t in terms if re.search(rf"(?<!\w){re.escape(t)}(?!\w)", text, re.IGNORECASE)}


def check_faithfulness(message: str, ctx: RetrievedContext) -> list[str]:
    """Avisos para termos astrológicos citados que não estão nos dados calculados nem nos textos recuperados."""
    reference = " ".join(d["texto"] for _, d in ctx.docs)
    calculated = " ".join([p.label + " " + p.sign_pt for p in ctx.placements]
                          + [a.aspect_pt + " " + str(a.p1) for a in ctx.aspects])
    allowed_text = reference + " " + calculated
    warnings = []
    for group, name, finder in ((_SIGNS, "signo", _mentions), (_BODIES, "ponto/planeta", _mentions),
                                (_ASPECTS, "aspecto", None)):
        if finder is None:
            extra = _aspect_mentions(message) - _mentions(allowed_text, group)
        else:
            extra = finder(message, group) - finder(allowed_text, group)
        warnings += [f"{name} '{t}' citado sem estar nos dados calculados ou recuperados" for t in sorted(extra)]
    houses_ok = {p.house for p in ctx.placements if p.house} | {int(n) for n in re.findall(r"casa (\d+)", reference)}
    for n in sorted({int(n) for n in re.findall(r"casa (\d+)", message, re.IGNORECASE)} - houses_ok):
        warnings.append(f"casa {n} citada sem estar nos dados calculados ou recuperados")
    return warnings


@dataclass
class AstralMessage:
    text: str
    context: RetrievedContext
    warnings: list[str] = field(default_factory=list)
    system: str = ""
    user: str = ""


def generate_message(kb: KnowledgeBase, chart: dict, llm: LLM, keys=DEFAULT_POINTS) -> AstralMessage:
    """Pipeline: mapa -> recuperação -> prompt -> LLM -> checagem de fidelidade."""
    ctx = retrieve(kb, chart, keys)
    if ctx.missing:
        raise LLMError(f"Base sem documentos para: {ctx.missing}")
    system, user = build_prompt(ctx)
    text = llm.complete(system, user)
    return AstralMessage(text, ctx, check_faithfulness(text, ctx), system, user)


def message_from_birth(kb: KnowledgeBase, birth, llm: LLM, keys=DEFAULT_POINTS) -> AstralMessage:
    """Dados de nascimento -> mapa (Kerykeion) -> mensagem."""
    from src.astrology.chart import calculate_chart
    return generate_message(kb, calculate_chart(birth), llm, keys)
