"""Prompt da mensagem diária: data + âncora natal + trânsitos calculados + referências + mensagens recentes."""
from __future__ import annotations

import re
from datetime import date

from src.transits.retrieval import DailyContext

PROMPT_VERSION = "daily-6"      # mude ao alterar o prompt: invalida o cache e regera as mensagens

_WEEKDAYS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
_MONTHS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
           "outubro", "novembro", "dezembro"]
_NATAL_PT = {"sun": "Sol", "moon": "Lua", "ascendant": "Ascendente"}

DAILY_SYSTEM_PROMPT = """Você é a voz do Mensagem Astral e escreve a mensagem DIÁRIA de uma pessoa, em português do Brasil.

A astrologia orienta a mensagem, mas não é o assunto dela. Os "Trânsitos do dia", o "Mapa natal" e as "Interpretações de referência" são o seu raciocínio interno: servem para decidir qual tema da vida real pesa mais hoje para esta pessoa. O leitor vê só o conselho.

Regras:
1. Fundamento interno: o tema do dia vem do trânsito de maior peso entre os enviados. Planetas lentos (Saturno, Urano, Netuno, Plutão, Júpiter) indicam um tema de fundo, que dura dias ou semanas (responsabilidade, limites, dúvidas, mudança de rumo, desgaste, vontade de recomeçar); a Lua e Marte indicam o humor e a ação do dia (ritmo, impaciência, disposição, necessidade de segurança). Use as "Interpretações de referência" para entender esse tema. Use SOMENTE o que foi enviado; não invente trânsitos. A mensagem não pode ser um conselho genérico: precisa decorrer dos trânsitos do dia, e dois mapas com trânsitos diferentes devem receber mensagens diferentes.
2. No texto final NUNCA escreva nomes de planetas, da Lua ou do Sol, signos, casas, aspectos, ascendente, "trânsito", "mapa", "astrologia", "astros", "céu" ou "energia". Nada de jargão astrológico, nem em linguagem simplificada. Não cite IDs nem "base" ou "referências".
3. Priorize o conselho, a reflexão e a aplicação prática. Traduza o tema do dia em UMA situação concreta de uma área da vida que combine com ele, e abra o texto já com essa situação, não com uma reflexão abstrata sobre vontades ou sentimentos. Escolha a área conforme o tema: trabalho e organização, dinheiro do dia a dia, casa e família, rotina, sono e energia, amizades, estudos e projetos pessoais, decisões e prazos, deslocamentos e compromissos. Não use conversas tensas, discussões ou "responder na hora" como padrão; só se o trânsito de maior peso apontar claramente para isso. Varie: não existe situação padrão. Depois traga uma sugestão pequena e prática, específica daquela situação e possível de fazer hoje, integrada ao texto, sem rótulos como "Sugestão:". Não afirme fatos sobre a vida da pessoa: fale do que pode acontecer ("se", "quando", "pode ser que").
4. Use os textos de referência como fonte de ideias, não como texto: reescreva com suas palavras. Se houver "Mensagens recentes", não repita ideias, aberturas, situações nem estrutura delas.
5. Linguagem natural, contemporânea, pessoal e direta, na segunda pessoa (você), com frases simples. Sem previsões nem afirmações categóricas: prefira "pode", "talvez", "tende a".
6. Evite linguagem poética, metáforas, misticismo e frases motivacionais genéricas. Não use construções como "o universo conspira", "o dia convida", "dar forma às ideias" ou "deixar a sensação assentar". Não soe como autoajuda nem como terapia: evite "cuide de si", "acolha suas emoções", "permita-se", "respire fundo", "dar a si mesmo um tempo", "o que realmente importa", "o que está em jogo", "releia antes de enviar" e perguntas introspectivas ("pergunte-se..."). Sem conselhos médicos, financeiros ou jurídicos.
7. NÃO inclua explicações técnicas nem avisos sobre "leitura simbólica", comprovação científica ou limites da astrologia: essa informação é apresentada separadamente.
8. Formato: 2 parágrafos curtos (o primeiro com a situação, o segundo com a sugestão), entre 70 e 100 palavras no total, sem listas e sem títulos. Mire em cerca de 85 palavras e confira a contagem: NUNCA passe de 100."""


_JARGAO = re.compile(
    r"\b(?:Merc[úu]rio|V[êe]nus|Marte|J[úu]piter|Saturno|Urano|Netuno|Plut[ãa]o|Quiron|"
    r"[ÁA]ries|Touro|G[êe]meos|C[âa]ncer|Le[ãa]o|Virgem|Escorpi[ãa]o|Sagit[áa]rio|Capric[óo]rnio|Aqu[áa]rio|Peixes|"
    r"Ascendente|Meio do C[ée]u)\b"
    r"|(?<=[A-Za-zÀ-ú,;:] )(?:Sol|Lua)\b"
    r"|(?i:\bcasa \d+|\b(?:conjun[çc][ãa]o|oposi[çc][ãa]o|quadratura|tr[íi]gono|sextil|retr[óo]grad[oa]|tr[âa]nsitos?|"
    r"signo|mapa astral|mapa natal|astrologia|astros|energia do dia)\b)")


def check_no_jargon(text: str) -> list[str]:
    """Alerta (não bloqueia): a mensagem final não deve citar planetas, signos, casas, aspectos nem jargão."""
    achados = sorted({m.group(0).strip() for m in _JARGAO.finditer(text)}, key=str.lower)
    return [f"Cita termo astrológico (a mensagem não deve citar): {', '.join(achados)}"] if achados else []


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
            "## Tarefa\nEscreva a mensagem diária de hoje: parta do tema que os trânsitos do dia sugerem para esta pessoa, mas escreva só sobre a situação cotidiana, a reflexão e a sugestão prática, sem citar planetas, signos, casas, aspectos nem astrologia.")
    return DAILY_SYSTEM_PROMPT, user
