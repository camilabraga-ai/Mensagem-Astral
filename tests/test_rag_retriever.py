import copy

import pytest

pytest.importorskip("jsonschema")

from src.common.env import REPO_ROOT
from src.data.kb import KnowledgeBase
from src.rag.retriever import DEFAULT_POINTS, extract_aspects, extract_placements, retrieve


@pytest.fixture(scope="module")
def kb():
    return KnowledgeBase.load(REPO_ROOT / "kb")


def fake_chart(sun=("Áries", 3), moon=("Gêmeos", 5), asc="Aquário", aspectos=None):
    """Mapa sintético NO FORMATO do motor, só para testar a recuperação (não é cálculo astrológico)."""
    pt = lambda i, n, s, c: {"id": i, "nome": n, "signo": s, "grau_no_signo": 10.5, "longitude": 0.0,
                             "casa": c, "retrogrado": False}
    return {
        "planetas": [pt("sun", "Sol", sun[0], sun[1]), pt("moon", "Lua", moon[0], moon[1]),
                     pt("mercury", "Mercúrio", "Touro", 2)],
        "angulos": [dict(pt("ascendant", "Ascendente", asc, 1), casa="first"),
                    pt("medium_coeli", "Meio do Céu", "Escorpião", 10)],
        "aspectos": aspectos or [],
    }


def test_recupera_documentos_esperados(kb):
    ctx = retrieve(kb, fake_chart())
    ids = ctx.doc_ids
    assert {"planeta_signo.sun.aries", "planeta.sun", "casa.3",
            "planeta_signo.moon.gemini", "planeta.moon", "casa.5",
            "elemento_signo.ascendant.aquarius", "elemento.ascendant",
            "signo.aries", "signo.gemini", "signo.aquarius"} <= set(ids)
    assert ctx.missing == []


def test_nao_recupera_pontos_nao_pedidos(kb):
    ids = retrieve(kb, fake_chart()).doc_ids
    assert not any("mercury" in i or "midheaven" in i or "taurus" in i or "scorpio" in i for i in ids)


def test_sem_documentos_repetidos_quando_sol_e_lua_no_mesmo_signo(kb):
    ctx = retrieve(kb, fake_chart(sun=("Leão", 1), moon=("Leão", 1)))
    assert len(ctx.doc_ids) == len(set(ctx.doc_ids))
    assert ctx.doc_ids.count("signo.leo") == 1 and ctx.doc_ids.count("casa.1") == 1


def test_aspectos_apenas_entre_pontos_escolhidos(kb):
    asp = [{"planeta_1": "Sol", "planeta_2": "Lua", "aspecto": "sextil", "orbe": 0.95},
           {"planeta_1": "Sol", "planeta_2": "Mercúrio", "aspecto": "trígono", "orbe": 2.0},
           {"planeta_1": "Lua", "planeta_2": "Ascendente", "aspecto": "oposição", "orbe": 1.2}]
    chart = fake_chart(aspectos=asp)
    got = extract_aspects(chart)
    assert [(a.p1, a.p2, a.aspect) for a in got] == [("sun", "moon", "sextile"), ("moon", "ascendant", "opposition")]
    ids = retrieve(kb, chart).doc_ids
    assert "aspecto.sextile" in ids and "aspecto.opposition" in ids and "aspecto.trine" not in ids


def test_ascendente_nao_tem_casa(kb):
    p = {x.key: x for x in extract_placements(fake_chart())}
    assert p["ascendant"].house is None and p["sun"].house == 3


def test_ponto_ausente_levanta_erro():
    with pytest.raises(KeyError):
        extract_placements(fake_chart(), keys=("sun", "pluto_inexistente"))


def test_documento_ausente_e_registrado_sem_quebrar():
    kb_vazia = KnowledgeBase([])
    ctx = retrieve(kb_vazia, fake_chart())
    assert ctx.docs == [] and len(ctx.missing) >= 9


@pytest.mark.parametrize("signo", ["Áries", "Touro", "Gêmeos", "Câncer", "Leão", "Virgem", "Libra",
                                    "Escorpião", "Sagitário", "Capricórnio", "Aquário", "Peixes"])
@pytest.mark.parametrize("casa", range(1, 13))
def test_toda_combinacao_possivel_tem_documentos(kb, signo, casa):
    ctx = retrieve(kb, fake_chart(sun=(signo, casa), moon=(signo, casa), asc=signo))
    assert ctx.missing == []


def test_pipeline_com_mapa_real_do_motor(kb):
    from src.astrology.chart import BirthData, calculate_chart
    chart = calculate_chart(BirthData(2000, 1, 1, 12, 0, city="Greenwich", nation="GB",
                                      lat=51.4769, lng=0.0, tz_str="UTC"))
    ctx = retrieve(kb, chart)
    assert ctx.missing == []
    sol = next(p for p in ctx.placements if p.key == "sun")
    assert sol.sign_pt == "Capricórnio" and f"planeta_signo.sun.{sol.sign}" in ctx.doc_ids
    assert all(k in {p.key for p in ctx.placements} for k in DEFAULT_POINTS)
