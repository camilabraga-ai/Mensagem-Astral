"""Parte visual: ornamentos SVG, tema CSS, fontes locais e componentes. Sem navegador e sem rede."""
import re
import xml.dom.minidom as minidom
from pathlib import Path

import pytest

from app.ui import components as ui
from app.ui import ornaments as orn
from src.common.env import REPO_ROOT

CSS = (REPO_ROOT / "app" / "ui" / "theme.css").read_text(encoding="utf-8")
ORNAMENTOS = ["hero_sun", "zodiac_wheel_moon", "mountains_sunrise", "moon_phases_row", "divider_star",
              "frame_corners", "lock_icon"]


@pytest.mark.parametrize("nome", ORNAMENTOS)
def test_svg_e_xml_valido_escalavel_e_decorativo(nome):
    svg = getattr(orn, nome)()
    minidom.parseString(f"<raiz>{svg}</raiz>")                   # XML bem formado
    assert "viewBox" in svg and "currentColor" in svg             # escala e herda a cor dourada do CSS
    assert "<script" not in svg.lower() and "onload" not in svg.lower() and "href" not in svg
    assert "http" not in svg.replace("http://www.w3.org/2000/svg", "")      # nenhum recurso externo


def test_hero_do_formulario_tem_sol_arco_zodiacal_luas_e_nuvens():
    svg = orn.hero_sun()
    assert svg.count("&#xFE0E;") == 6                              # seis signos, como no mockup
    assert svg.count("<circle") > 30 and "stroke-dasharray" in svg   # sol, estrelas e arcos pontilhados
    assert svg.count("scale(-") >= 1                               # nuvem e luas espelhadas


def test_roda_zodiacal_tem_os_12_signos_e_lua():
    svg = orn.zodiac_wheel_moon()
    assert svg.count("&#xFE0E;") == 12
    for signo in orn.ZODIAC:
        assert signo in svg


def test_ornamentos_sao_deterministicos():
    assert orn.hero_sun() == orn.hero_sun() and orn.starfield_dots(3) == orn.starfield_dots(3)


def test_crescente_tem_area_visivel():
    # o raio do arco interno precisa ser MAIOR que o do externo, senão o desenho degenera em um contorno fino
    d = re.search(r'd="M0,-(\d+(?:\.\d+)?) A\d+(?:\.\d+)?,\d+(?:\.\d+)? 0 0,0 0,\d+(?:\.\d+)? A(\d+(?:\.\d+)?)', orn.crescent(0, 0, 10))
    assert float(d.group(2)) > float(d.group(1))


# ---------- componentes: escape de HTML ----------
def test_moldura_escapa_o_texto_e_separa_paragrafos():
    html = ui.message_frame("Primeiro <b>parágrafo</b>.\n\nSegundo & último.")
    assert "<b>" not in html and "&lt;b&gt;" in html and "&amp;" in html
    assert html.count("<p>") == 2 and 'class="ma-frame"' in html


def test_moldura_sem_texto_mostra_o_aviso_em_estilo_vazio():
    assert 'class="ma-empty"' in ui.message_frame(None, "Ainda não gerada.") and "Ainda não gerada." in ui.message_frame(None, "Ainda não gerada.")


def test_nome_e_escapado_na_saudacao():
    assert "<script>" not in ui.greeting("<script>x</script>")


def test_nota_de_privacidade_com_cadeado():
    html = ui.privacy_note("Seus dados são usados apenas para calcular seu mapa astral e gerar sua mensagem diária.")
    assert "ma-lock" in html and "Seus dados são usados apenas" in html


# ---------- tema CSS ----------
def test_paleta_preta_e_dourada():
    assert "--ma-gold: #d9b05b" in CSS and "--ma-ink: #05050a" in CSS


def test_tipografia_serifada_para_titulos_e_corpo():
    assert "--ma-serif-title: 'Cinzel'" in CSS and "--ma-serif-body: 'Cormorant Garamond'" in CSS
    assert "text-transform: uppercase" in CSS


def test_layout_mobile_first_com_adaptacao_ao_desktop():
    assert "max-width: 520px" in CSS                               # cartão central no desktop
    assert "@media (max-width: 560px)" in CSS                      # ocupa a tela no celular
    assert "clamp(" in CSS                                         # tipografia fluida


def test_botao_dourado_em_pilula_e_campos_com_moldura_dourada():
    assert 'button[kind="primary"]' in CSS and "999px" in CSS and "linear-gradient(180deg, #f1d28f" in CSS
    assert "stTextInputRootElement" in CSS and "stDateInputField" in CSS and "stTimeInputTimeDisplay" in CSS


def test_icones_dos_campos_sao_svg_embutidos_sem_recursos_externos():
    for tag in ("Nome", "Cidade"):
        assert f'aria-label^="{tag}"' in CSS
    externos = re.findall(r"https?://[^\s\"')]+", CSS)
    assert set(externos) <= {"http://www.w3.org/2000/svg"}


def test_estados_de_foco_e_botao_desabilitado_estilizados():
    assert ":focus-within" in CSS and "button:disabled" in CSS


def test_legibilidade_da_mensagem_em_moldura():
    assert ".ma-frame p" in CSS and "line-height: 1.5" in CSS and "text-align: center" in CSS


# ---------- fontes locais (sem serviços externos) ----------
def test_fontes_hospedadas_localmente_com_licenca():
    pasta = REPO_ROOT / "app" / "static" / "fonts"
    for arquivo in re.findall(r"url\('app/static/fonts/([^']+)'\)", CSS):
        assert (pasta / arquivo).is_file(), arquivo
    assert "SIL Open Font License" in (pasta / "LICENSE.md").read_text(encoding="utf-8")


def test_servir_arquivos_estaticos_esta_habilitado():
    assert "enableStaticServing = true" in (REPO_ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")


def test_decoracao_separada_da_logica():
    ornamentos = (REPO_ROOT / "app" / "ui" / "ornaments.py").read_text(encoding="utf-8")
    assert "streamlit" not in ornamentos and "src." not in ornamentos       # só desenho


def test_cartao_principal_nao_encolhe_para_a_altura_da_janela():
    """Mensagens longas não podem ser cortadas (o 'Seu mapa' sumia): o cartão tem overflow oculto, então não pode encolher."""
    from pathlib import Path
    css = (Path(__file__).resolve().parents[1] / "app" / "ui" / "theme.css").read_text(encoding="utf-8")
    bloco = css[css.index(".block-container {"):css.index(".block-container::before")]
    assert "flex-shrink: 0" in bloco
