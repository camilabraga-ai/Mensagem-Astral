"""Montagem do prompt: dados calculados + interpretações recuperadas -> (system, user)."""
from __future__ import annotations

from src.astrology.chart import PLANETS_PT
from src.rag.retriever import RetrievedContext

SYSTEM_PROMPT = """Você é a voz do Mensagem Astral e escreve mensagens personalizadas de astrologia em português do Brasil.

Regras:
1. Use SOMENTE os "Dados calculados" e as "Interpretações de referência" que a pessoa usuária enviar. Não mencione nenhum outro planeta, signo, casa, aspecto ou ponto do mapa, nem trânsitos, datas, previsões de eventos ou fatos sobre a vida da pessoa.
2. Sintetize. Encontre o fio condutor entre Sol, Lua e Ascendente (convergências e tensões, incluindo os aspectos calculados, se houver) em vez de descrever cada posição em sequência ou copiar trechos. Reescreva com suas próprias palavras.
3. Não cite IDs, nem a existência de "documentos", "base" ou "referências".
4. Tom acolhedor e reflexivo, na segunda pessoa (você), sem determinismo: prefira "costuma", "pode", "convida a" a afirmações categóricas.
5. Apresente como leitura simbólica, conhecimento astrológico, sem afirmar comprovação científica. Uma menção breve e natural, ao final.
6. Não dê conselhos médicos, financeiros ou jurídicos.
7. Formato: 3 a 5 parágrafos, cerca de 250 a 350 palavras, sem listas e sem títulos."""


def _fmt_degree(x: float) -> str:
    return f"{x:.1f}".replace(".", ",") + "°"


def format_calculated(ctx: RetrievedContext) -> str:
    lines = []
    for p in ctx.placements:
        extra = f", casa {p.house}" if p.house else ""
        retro = ", retrógrado" if p.retrograde else ""
        lines.append(f"- {p.label}: {p.sign_pt}, {_fmt_degree(p.degree)}{extra}{retro}")
    if ctx.aspects:
        lines.append("- Aspectos calculados entre esses pontos:")
        for a in ctx.aspects:
            lines.append(f"  - {PLANETS_PT[a.p1]} em {a.aspect_pt} com {PLANETS_PT[a.p2]} "
                         f"(orbe {_fmt_degree(a.orb)})")
    else:
        lines.append("- Nenhum aspecto calculado entre esses pontos.")
    return "\n".join(lines)


def build_prompt(ctx: RetrievedContext) -> tuple[str, str]:
    refs = "\n\n".join(f"### {reason}\n{d['texto']}" for reason, d in ctx.docs)
    user = (f"## Dados calculados\n{format_calculated(ctx)}\n\n"
            f"## Interpretações de referência\n{refs}\n\n"
            "## Tarefa\nEscreva a mensagem personalizada, integrando Sol, Lua e Ascendente.")
    return SYSTEM_PROMPT, user
