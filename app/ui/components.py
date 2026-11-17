"""Componentes visuais reutilizáveis: montam HTML (com os SVGs de ornaments.py) para o st.markdown.

Nenhuma regra de negócio aqui. Todo texto dinâmico (mensagem, nome) é escapado antes de virar HTML.
"""
from __future__ import annotations

from html import escape
from pathlib import Path

from app.ui import ornaments as orn

CSS_PATH = Path(__file__).with_name("theme.css")


def theme_css() -> str:
    return CSS_PATH.read_text(encoding="utf-8")


def theme_style_tag() -> str:
    return f"<style>{theme_css()}</style>"


def corners() -> str:
    """Estrelas ornamentais nos quatro cantos do cartão."""
    return "".join(orn.corner_star(c) for c in ("tl", "tr", "bl", "br"))


def hero_form() -> str:
    return orn.hero_sun()


def hero_result() -> str:
    return orn.zodiac_wheel_moon()


def scene() -> str:
    return orn.mountains_sunrise()


def divider() -> str:
    return orn.divider_star()


def moon_row() -> str:
    return orn.moon_phases_row()


def subtitle(text: str) -> str:
    return f'<p class="ma-sub">{escape(text)}</p>'


def date_line(text: str) -> str:
    return f'<div class="ma-date">{escape(text)}</div>'


def greeting(name: str) -> str:
    return f'<p class="ma-greeting">Olá, {escape(name)}</p>'


def privacy_note(text: str) -> str:
    return f'<div class="ma-privacy">{orn.lock_icon()}<span>{escape(text)}</span></div>'


def footer_note(text: str) -> str:
    return f'<div class="ma-foot">{escape(text)}</div>'


def message_frame(text: str | None, placeholder: str = "") -> str:
    """Moldura ornamental com a mensagem. `text` é escapado; parágrafos separados por linha em branco."""
    if text:
        paras = "".join(f"<p>{escape(p.strip())}</p>" for p in text.split("\n\n") if p.strip())
    else:
        paras = f'<p class="ma-empty">{escape(placeholder)}</p>'
    star = orn.star4(11, 11, 9)
    small = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 22 22" class="ma-orn ma-{{k}}" aria-hidden="true">{star}</svg>'
    return (f'<div class="ma-frame">{orn.frame_corners()}{small.format(k="tstar")}{paras}{small.format(k="bstar")}</div>')
