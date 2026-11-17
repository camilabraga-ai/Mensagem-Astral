"""Elementos gráficos decorativos (SVG puro, sem texto funcional, sem recursos externos).

Todos os desenhos usam `currentColor` para o traço e para o preenchimento dourado: a cor vem do CSS
(`.ma-gold { color: ... }`). Cada função devolve uma string `<svg>` escalável (width 100%).
Nada aqui conhece Streamlit nem o pipeline astrológico.
"""
from __future__ import annotations

import math

ZODIAC = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"]
_FONT = "'Apple Symbols','Segoe UI Symbol','Noto Sans Symbols 2','Noto Sans Symbols','DejaVu Sans',serif"
_STROKE = 'fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"'


def _svg(viewbox: str, body: str, cls: str = "", label: str = "") -> str:
    aria = f'role="img" aria-label="{label}"' if label else 'aria-hidden="true"'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" class="ma-orn {cls}" {aria} '
            f'preserveAspectRatio="xMidYMid meet">{body}</svg>')


def _pt(cx: float, cy: float, r: float, deg: float) -> tuple[float, float]:
    a = math.radians(deg)
    return cx + r * math.cos(a), cy - r * math.sin(a)


def star4(cx: float, cy: float, r: float, fill: bool = True) -> str:
    k = r * 0.16
    d = (f"M{cx},{cy - r} Q{cx + k},{cy - k} {cx + r},{cy} Q{cx + k},{cy + k} {cx},{cy + r} "
         f"Q{cx - k},{cy + k} {cx - r},{cy} Q{cx - k},{cy - k} {cx},{cy - r}Z")
    return f'<path d="{d}" fill="{"currentColor" if fill else "none"}" stroke="currentColor" stroke-width="0.6"/>'


def sparkle(cx: float, cy: float, r: float) -> str:
    return star4(cx, cy, r) + f'<circle cx="{cx}" cy="{cy}" r="{r * 0.16:.2f}" fill="#05050a"/>'


def crescent(cx: float, cy: float, r: float, flip: bool = False, k: float = 1.12) -> str:
    """Lua crescente de raio r. k > 1 é a razão entre o raio do arco interno e o externo: perto de 1 = bem fina,
    maior = mais gorda. flip=True espelha (minguante)."""
    sx = -1 if flip else 1
    d = f"M0,{-r} A{r},{r} 0 0,0 0,{r} A{r * k:.2f},{r * k:.2f} 0 0,1 0,{-r}Z"
    return (f'<path transform="translate({cx},{cy}) scale({sx},1)" d="{d}" fill="currentColor" fill-opacity=".9" '
            f'stroke="currentColor" stroke-width="0.8"/>')


def full_moon(cx: float, cy: float, r: float) -> str:
    craters = "".join(f'<circle cx="{cx + dx:.1f}" cy="{cy + dy:.1f}" r="{cr}" {_STROKE} stroke-width="0.5" opacity=".6"/>'
                      for dx, dy, cr in ((-0.3 * r, -0.2 * r, 0.18 * r), (0.25 * r, 0.1 * r, 0.14 * r),
                                         (-0.05 * r, 0.4 * r, 0.1 * r)))
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="currentColor" fill-opacity=".9"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r + 3}" {_STROKE} stroke-width="0.7"/>{craters}')


def _glyph(x: float, y: float, ch: str, size: float = 19) -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="middle" dominant-baseline="central" '
            f'font-family="{_FONT}" fill="currentColor" style="font-variant-emoji:text">{ch}&#xFE0E;</text>')


def starfield_dots(seed: int = 7, n: int = 26, w: int = 480, h: int = 300) -> str:
    """Pontinhos de estrelas determinísticos (sem aleatoriedade entre execuções)."""
    out, s = [], seed
    for _ in range(n):
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        x = s % w
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        y = s % h
        r = 0.5 + (s % 5) * 0.18
        out.append(f'<circle cx="{x}" cy="{y}" r="{r:.2f}" fill="currentColor" opacity="{0.35 + (s % 4) * 0.15:.2f}"/>')
    return "".join(out)


def cloud(x: float, y: float, scale: float = 1.0, flip: bool = False) -> str:
    """Nuvem em linhas finas, com enrolados internos."""
    sx = -scale if flip else scale
    body = ('<path d="M0,60 C-4,38 20,30 34,38 C38,16 70,8 86,26 C104,12 134,24 130,46 C150,46 156,66 138,70 Z"/>'
            '<path d="M18,60 C20,48 34,46 40,54 M52,52 C54,38 70,34 78,44 M92,54 C94,44 108,42 114,50"/>'
            '<path d="M6,66 L132,66 M14,72 L120,72 M26,78 L104,78" opacity=".55"/>'
            '<path d="M60,26 C66,20 76,22 76,30 M104,32 C110,28 118,32 116,38" opacity=".7"/>')
    return f'<g transform="translate({x},{y}) scale({sx},{scale})" {_STROKE} stroke-width="0.9">{body}</g>'


def sun_face(cx: float, cy: float, r: float = 34) -> str:
    rays = []
    for i in range(24):
        a = i * 15
        long_ = i % 2 == 0
        tip = r + (50 if long_ else 30)
        x1, y1 = _pt(cx, cy, r + 4, a - 5)
        x2, y2 = _pt(cx, cy, r + 4, a + 5)
        xt, yt = _pt(cx, cy, tip, a)
        rays.append(f'<path d="M{x1:.1f},{y1:.1f} L{xt:.1f},{yt:.1f} L{x2:.1f},{y2:.1f}" {_STROKE} stroke-width="0.9"/>')
        if long_:
            xm, ym = _pt(cx, cy, r + 6, a)
            xe, ye = _pt(cx, cy, tip - 6, a)
            rays.append(f'<path d="M{xm:.1f},{ym:.1f} L{xe:.1f},{ye:.1f}" {_STROKE} stroke-width="0.5" opacity=".7"/>')
    face = (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#0b0a14" stroke="currentColor" stroke-width="1.1"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r - 4}" {_STROKE} stroke-width="0.5" opacity=".6"/>'
            # sobrancelhas, olhos, nariz, boca
            f'<path d="M{cx - 15},{cy - 8} Q{cx - 9},{cy - 12} {cx - 3},{cy - 8} M{cx + 3},{cy - 8} Q{cx + 9},{cy - 12} {cx + 15},{cy - 8}" {_STROKE} stroke-width="0.9"/>'
            f'<path d="M{cx - 13},{cy - 4} Q{cx - 9},{cy - 7} {cx - 5},{cy - 4} M{cx + 5},{cy - 4} Q{cx + 9},{cy - 7} {cx + 13},{cy - 4}" {_STROKE} stroke-width="0.9"/>'
            f'<path d="M{cx},{cy - 6} L{cx - 2},{cy + 6} Q{cx},{cy + 8} {cx + 3},{cy + 6}" {_STROKE} stroke-width="0.9"/>'
            f'<path d="M{cx - 8},{cy + 14} Q{cx},{cy + 19} {cx + 8},{cy + 14}" {_STROKE} stroke-width="0.9"/>'
            f'<path d="M{cx - 14},{cy + 8} Q{cx - 10},{cy + 11} {cx - 7},{cy + 9} M{cx + 14},{cy + 8} Q{cx + 10},{cy + 11} {cx + 7},{cy + 9}" {_STROKE} stroke-width="0.5" opacity=".6"/>'
            + star4(cx, cy - 20, 3.2))
    return "".join(rays) + face


def hero_sun() -> str:
    """Topo da tela do formulário: sol com rosto, arco zodiacal, luas e nuvens."""
    cx, cy = 240.0, 196.0
    arcs = "".join(f'<path d="M{cx - R},{cy} A{R},{R} 0 0 1 {cx + R},{cy}" {_STROKE} stroke-width="{w}" {dash}/>'
                   for R, w, dash in ((190, 0.7, ""), (164, 0.5, 'stroke-dasharray="1 4"'), (132, 0.5, 'stroke-dasharray="2 5"')))
    glyphs = ""
    for ch, ang in zip(["♈", "♊", "♋"], (141, 156, 170)):
        x, y = _pt(cx, cy, 177, ang)
        glyphs += _glyph(x, y, ch)
    for ch, ang in zip(["♒", "♑", "♐"], (39, 24, 10)):
        x, y = _pt(cx, cy, 177, ang)
        glyphs += _glyph(x, y, ch)
    moons = ""
    for kind, ang in (("c1", 126), ("c2", 108), ("full", 90), ("c3", 72), ("c4", 54)):
        x, y = _pt(cx, cy, 176, ang)
        if kind == "full":
            moons += full_moon(x, y - 4, 11)
        else:
            moons += crescent(x, y, 10 if kind in ("c2", "c3") else 9, flip=kind in ("c3", "c4"),
                              k=1.06 if kind in ("c1", "c4") else 1.22)
    ticks = "".join(
        f'<path d="M{_pt(cx, cy, 190, a)[0]:.1f},{_pt(cx, cy, 190, a)[1]:.1f} L{_pt(cx, cy, 196, a)[0]:.1f},{_pt(cx, cy, 196, a)[1]:.1f}" {_STROKE} stroke-width="0.5"/>'
        for a in range(0, 181, 6))
    stars = (star4(36, 120, 7) + star4(452, 70, 6) + star4(404, 148, 4) + star4(86, 74, 3.5)
             + sparkle(240, 24, 9) + star4(240, 38, 5))
    body = (starfield_dots(11, 24) + arcs + ticks + glyphs + moons + sun_face(cx, cy)
            + cloud(-6, 190, 1.05) + cloud(486, 190, 1.05, flip=True) + stars)
    return _svg("0 0 480 262", body, "ma-hero", "Sol e arco zodiacal")


def zodiac_wheel_moon() -> str:
    """Topo da tela da mensagem: roda zodiacal com lua crescente ao centro e nuvens."""
    cx, cy = 240.0, 140.0
    ring = "".join(f'<circle cx="{cx}" cy="{cy}" r="{r}" {_STROKE} stroke-width="{w}" {dash}/>'
                   for r, w, dash in ((118, 1.0, ""), (110, 0.5, ""), (76, 0.8, ""), (60, 0.5, 'stroke-dasharray="1 3"')))
    ticks = "".join(f'<path d="M{_pt(cx, cy, 118, a)[0]:.1f},{_pt(cx, cy, 118, a)[1]:.1f} L{_pt(cx, cy, 124, a)[0]:.1f},{_pt(cx, cy, 124, a)[1]:.1f}" {_STROKE} stroke-width="0.5"/>'
                    for a in range(0, 360, 5))
    glyphs = "".join(_glyph(*_pt(cx, cy, 93, 165 - i * 30), ch, 16) for i, ch in enumerate(ZODIAC))
    spokes = "".join(f'<path d="M{_pt(cx, cy, 60, a)[0]:.1f},{_pt(cx, cy, 60, a)[1]:.1f} L{_pt(cx, cy, 76, a)[0]:.1f},{_pt(cx, cy, 76, a)[1]:.1f}" {_STROKE} stroke-width="0.6"/>'
                     for a in range(0, 360, 15))
    moon = (f'<circle cx="{cx}" cy="{cy}" r="46" fill="#0b0a14" stroke="currentColor" stroke-width="0.8"/>'
            f'<circle cx="{cx}" cy="{cy}" r="38" {_STROKE} stroke-width="0.4" stroke-dasharray="1 3" opacity=".7"/>'
            + crescent(cx + 2, cy, 33, k=1.28).replace('transform="', f'transform="rotate(-24 {cx} {cy}) ')
            + f'<circle cx="{cx + 13}" cy="{cy - 14}" r="2" fill="#0b0a14" opacity=".4"/>'
            f'<circle cx="{cx - 5}" cy="{cy + 14}" r="2.6" fill="#0b0a14" opacity=".35"/>'
            + star4(cx + 22, cy - 22, 3.4) + star4(cx + 8, cy + 24, 2.4))
    stars = (star4(240, 12, 9) + star4(64, 110, 7) + star4(430, 66, 5) + star4(112, 52, 3.5) + star4(378, 128, 3.5))
    body = (starfield_dots(5, 26, 480, 260) + ring + ticks + spokes + glyphs + moon
            + cloud(-6, 150, 1.0) + cloud(486, 150, 1.0, flip=True) + stars)
    return _svg("0 0 480 262", body, "ma-hero", "Roda zodiacal com a Lua")


def mountains_sunrise() -> str:
    """Rodapé decorativo: montanhas em traço fino com sol nascente."""
    cx, cy = 240.0, 116.0
    rays = "".join(f'<path d="M{_pt(cx, cy, 36, a)[0]:.1f},{_pt(cx, cy, 36, a)[1]:.1f} L{_pt(cx, cy, 36 + (46 if i % 2 == 0 else 28), a)[0]:.1f},{_pt(cx, cy, 36 + (46 if i % 2 == 0 else 28), a)[1]:.1f}" {_STROKE} stroke-width="0.8"/>'
                   for i, a in enumerate(range(10, 171, 10)))
    sun = (f'<path d="M{cx - 26},{cy} A26,26 0 0,1 {cx + 26},{cy}Z" fill="currentColor" fill-opacity=".85"/>'
           f'<path d="M{cx - 18},{cy} A18,18 0 0,1 {cx + 18},{cy}" fill="none" stroke="#05050a" stroke-width="0.6" opacity=".5"/>')
    left = "M0,96 L26,74 L44,88 L72,56 L96,82 L120,68 L146,92 L172,84 L200,106 L222,112 L240,116"
    right = "M480,96 L454,74 L436,88 L408,56 L384,82 L360,68 L334,92 L308,84 L280,106 L258,112 L240,116"
    back_l = "M0,112 L40,98 L80,108 L120,96 L170,110 L214,114"
    back_r = "M480,112 L440,98 L400,108 L360,96 L310,110 L266,114"
    hatch = "".join(f'<path d="M{x},{y} l-6,14 M{x + 5},{y + 2} l-6,12" {_STROKE} stroke-width="0.4" opacity=".55"/>'
                    for x, y in ((58, 66), (110, 74), (66, 84), (172, 90), (422, 66), (370, 74), (414, 84), (308, 90)))
    body = (f'<path d="{left}" {_STROKE} stroke-width="1"/><path d="{right}" {_STROKE} stroke-width="1"/>'
            f'<path d="{back_l}" {_STROKE} stroke-width="0.6" opacity=".6"/><path d="{back_r}" {_STROKE} stroke-width="0.6" opacity=".6"/>'
            + hatch + rays + sun + f'<path d="M150,{cy + 4} L330,{cy + 4}" {_STROKE} stroke-width="0.6" opacity=".6"/>'
            + star4(76, 30, 5) + star4(410, 40, 4))
    return _svg("0 0 480 134", body, "ma-scene")


def moon_phases_row() -> str:
    """Pequena fileira de fases da Lua (divisor)."""
    xs = [150, 190, 240, 290, 330]
    body = (crescent(xs[0], 12, 5, flip=False, k=1.06) + crescent(xs[1], 12, 7, k=1.2)
            + full_moon(xs[2], 12, 9) + crescent(xs[3], 12, 7, flip=True, k=1.2)
            + crescent(xs[4], 12, 5, flip=True, k=1.06))
    return _svg("0 0 480 26", body, "ma-divider")


def divider_star() -> str:
    body = ('<path d="M120,10 H222 M258,10 H360" ' + _STROKE + ' stroke-width="0.8"/>'
            + star4(240, 10, 7) + f'<circle cx="112" cy="10" r="1.4" fill="currentColor"/><circle cx="368" cy="10" r="1.4" fill="currentColor"/>')
    return _svg("0 0 480 20", body, "ma-divider")


def corner_star(size_cls: str = "") -> str:
    return _svg("-14 -14 28 28", sparkle(0, 0, 12) + star4(0, 0, 4, False), f"ma-corner {size_cls}")


def frame_corners() -> str:
    """Quatro cantos ornamentais (colchetes finos + estrela) para a moldura da mensagem."""
    def one(rot: int) -> str:
        return _svg("0 0 40 40",
                    f'<g transform="rotate({rot} 20 20)"><path d="M3,34 V12 Q3,3 12,3 H34" {_STROKE} stroke-width="1"/>'
                    f'<path d="M8,30 V14 Q8,8 14,8 H30" {_STROKE} stroke-width="0.5" opacity=".7"/>{star4(34, 3, 3)}</g>',
                    f"ma-fc ma-fc-{rot}")
    return "".join(one(r) for r in (0, 90, 180, 270))


def lock_icon() -> str:
    return _svg("0 0 24 24", f'<rect x="5" y="10.5" width="14" height="10" rx="2" fill="currentColor" fill-opacity=".85"/>'
                f'<path d="M8,10.5 V7.5 A4,4 0 0 1 16,7.5 V10.5" {_STROKE} stroke-width="1.6"/>', "ma-lock")
