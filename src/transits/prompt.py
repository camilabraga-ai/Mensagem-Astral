"""Prompt da mensagem diária: data + âncora natal + trânsitos calculados + referências + mensagens recentes."""
from __future__ import annotations

from datetime import date

from src.transits.retrieval import DailyContext

PROMPT_VERSION = "daily-1"      # mude ao alterar o prompt: invalida o cache e regera as mensagens

_WEEKDAYS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
_MONTHS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
           "outubro", "novembro", "dezembro"]
_NATAL_PT = {"sun": "Sol", "moon": "Lua", "ascendant": "Ascendente"}

DAILY_SYSTEM_PROMPT = """Você é a voz do Mensagem Astral e escreve a mensagem astrológica DIÁRIA de uma pessoa, em português do Brasil.

Regras:
1. Use SOMENTE os "Trânsitos do dia", o "Mapa natal" e as "Interpretações de referência" enviados. Não mencione outros planetas, signos, casas, aspectos ou pontos, nem datas ou fatos sobre a vida da pessoa.
2. O foco é o DIA: relacione os trânsitos calculados ao mapa natal. O mapa natal é só âncora; não recontar quem a pessoa é nem repetir descrições natais.
3. Use os textos de referência como fonte de ideias, não como texto: reescreva com suas palavras e não repita frases ou expressões características deles. Não cite IDs nem "base" ou "referências".
4. Se houver "Mensagens recentes", não repita ideias, aberturas, imagens nem estrutura delas.
5. Tom acolhedor e reflexivo, na segunda pessoa (você), sem determinismo: nada de previsões de eventos; prefira "pode", "convida a", "costuma".
6. Inclua uma reflexão para o dia e uma sugestão prática pequena e concreta (sem conselhos médicos, financeiros ou jurídicos).
7. Formato: 2 a 3 parágrafos curtos, cerca de 120 a 180 palavras, sem listas e sem títulos. Feche com uma menção breve de que é uma leitura simbólica, sem comprovação científica."""


def format_date_pt(d: date) -> str:
    return f"{_WEEKDAYS[d.weekday()]}, {d.day} de {_MONTHS[d.month - 1]} de {d.year}"


def _deg(x: float) -> str:
    return f"{x:.1f}".replace(".", ",") + "°"


def format_transits(ctx: DailyContext) -> str:
    m = ctx.moon_today
    lines = [f"- Lua do dia: {m.sign_pt}"]
    for t in ctx.transits:
        a, p = t.aspect, ctx.positions[t.aspect.transit]
        retro = ", retrógrado" if p.retrograde else ""
        exato = " (aspecto exato hoje)" if t.exact else ""
        lines.append(f"- {p.label} em {p.sign_pt}{retro}, em {a.aspect_pt} com o seu "
                     f"{_NATAL_PT[a.natal]} natal (orbe {_deg(a.orb)}){exato}")
    if not ctx.transits:
        lines.append("- Nenhum aspecto marcante de planetas em trânsito com o Sol, a Lua ou o Ascendente natais.")
    return "\n".join(lines)


def build_daily_prompt(ctx: DailyContext, recent_messages=()) -> tuple[str, str]:
    natal = "\n".join(f"- {p.label}: {p.sign_pt}" for p in ctx.natal)
    refs = "\n\n".join(f"### {reason}\n{d['texto']}" for reason, d in ctx.docs)
    recent = ""
    if recent_messages:
        quoted = "\n\n".join("> " + m.replace("\n", "\n> ") for m in recent_messages)
        recent = f"\n\n## Mensagens recentes (não repita ideias, aberturas nem estrutura)\n{quoted}"
    user = (f"## Data\n{format_date_pt(ctx.day)} (posições calculadas para o meio-dia, no fuso do local de nascimento)\n\n"
            f"## Mapa natal (âncora)\n{natal}\n\n"
            f"## Trânsitos do dia (calculados)\n{format_transits(ctx)}\n\n"
            f"## Interpretações de referência\n{refs}{recent}\n\n"
            "## Tarefa\nEscreva a mensagem diária de hoje, relacionando os trânsitos do dia ao mapa natal.")
    return DAILY_SYSTEM_PROMPT, user
