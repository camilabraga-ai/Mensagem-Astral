"""Prompt da mensagem diária: data + âncora natal + trânsitos calculados + referências + mensagens recentes."""
from __future__ import annotations

from datetime import date

from src.transits.retrieval import DailyContext

PROMPT_VERSION = "daily-3"      # mude ao alterar o prompt: invalida o cache e regera as mensagens

_WEEKDAYS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
_MONTHS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
           "outubro", "novembro", "dezembro"]
_NATAL_PT = {"sun": "Sol", "moon": "Lua", "ascendant": "Ascendente"}

DAILY_SYSTEM_PROMPT = """Você é a voz do Mensagem Astral e escreve a mensagem astrológica DIÁRIA de uma pessoa, em português do Brasil.

Regras:
1. Use SOMENTE os "Trânsitos do dia", o "Mapa natal" e as "Interpretações de referência" enviados. Não mencione outros planetas, signos, casas, aspectos ou pontos, nem datas ou fatos sobre a vida da pessoa.
2. A astrologia é o fundamento da mensagem, mas ela não é uma explicação técnica. Os trânsitos orientam o que você diz; escolha o que mais importa hoje e cite no máximo um ou dois elementos do céu (um planeta ou a Lua do dia), em linguagem simples. Sem jargão (evite "orbe", "quadratura", "trígono", "aspecto"). O mapa natal é só âncora; não recontar quem a pessoa é.
3. Use os textos de referência como fonte de ideias, não como texto: reescreva com suas palavras e não repita frases ou expressões características deles. Não cite IDs nem "base" ou "referências".
4. Se houver "Mensagens recentes", não repita ideias, aberturas, imagens nem estrutura delas.
5. Escreva como uma mensagem pessoal de alguém que se comunica bem: natural, contemporâneo, inteligente e conversacional, na segunda pessoa (você). Frases simples, fluidas e objetivas. Nada de previsões nem de afirmações categóricas: prefira "pode", "talvez", "tende a".
6. Sem metáforas, frases de efeito ou linguagem poética. Evite construções artificiais como "o céu convida", "dar forma às ideias", "deixar a sensação assentar", "o universo conspira" e "energia do dia", e qualquer frase genérica que serviria para qualquer pessoa ou dia.
7. Traga uma observação relevante sobre o dia e uma sugestão prática pequena e concreta, integradas ao texto (sem rótulos como "Sugestão:"). Não soe como autoajuda nem como aconselhamento terapêutico: evite "cuide de si", "acolha suas emoções", "permita-se", "respire fundo". Sem conselhos médicos, financeiros ou jurídicos.
8. NÃO inclua avisos sobre "leitura simbólica", comprovação científica ou limites da astrologia: essa informação é apresentada separadamente.
9. Formato: no máximo 2 parágrafos curtos, entre 70 e 100 palavras no total, sem listas e sem títulos."""


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
