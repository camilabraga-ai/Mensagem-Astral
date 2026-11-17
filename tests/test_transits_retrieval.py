from datetime import date

import pytest

pytest.importorskip("kerykeion")
pytest.importorskip("jsonschema")

from src.astrology.chart import BirthData, calculate_chart
from src.common.env import REPO_ROOT
from src.data.kb import KnowledgeBase
from src.rag.generator import check_faithfulness
from src.transits.retrieval import build_daily_context
from src.transits.select import transit_key

kb = KnowledgeBase.load(REPO_ROOT / "kb")
DAY = date(2026, 11, 17)


@pytest.fixture(scope="module")
def natal():
    return calculate_chart(BirthData(2000, 1, 1, 12, 0, city="Greenwich", nation="GB",
                                     lat=51.4769, lng=0.0, tz_str="UTC"))


@pytest.fixture(scope="module")
def ctx(natal):
    return build_daily_context(kb, natal, DAY)


def test_recupera_blocos_esperados_para_cada_transito(ctx):
    assert ctx.transits and ctx.missing == []
    ids = set(ctx.doc_ids)
    for t in ctx.transits:
        a, p = t.aspect, ctx.positions[t.aspect.transit]
        assert f"planeta.{a.transit}" in ids
        assert f"planeta_signo.{a.transit}.{p.sign}" in ids
        assert f"aspecto.{a.aspect}" in ids
        n = next(x for x in ctx.natal if x.key == a.natal)
        assert (f"elemento_signo.ascendant.{n.sign}" if n.key == "ascendant" else f"planeta_signo.{n.key}.{n.sign}") in ids
    assert f"planeta_signo.moon.{ctx.moon_today.sign}" in ids          # Lua do dia, sempre


def test_todos_os_documentos_existem_na_base_e_sem_repeticao(ctx):
    base = {d["id"]: d for d in kb.docs}
    assert len(ctx.doc_ids) == len(set(ctx.doc_ids))
    assert all(i in base and base[i]["texto"] == d["texto"] for (_, d), i in zip(ctx.docs, ctx.doc_ids))


def test_quantidade_de_documentos_e_limitada(ctx):
    assert len(ctx.docs) <= 4 * 3 + 1


def test_base_vazia_registra_faltas_sem_inventar(natal):
    c = build_daily_context(KnowledgeBase([]), natal, DAY)
    assert c.docs == [] and len(c.missing) >= 4


def test_trânsitos_recentes_mudam_a_selecao(natal, ctx):
    recent = {transit_key(t.aspect) for t in ctx.transits[:1]}
    c2 = build_daily_context(kb, natal, DAY, recent=recent)
    assert transit_key(ctx.transits[0].aspect) != transit_key(c2.transits[0].aspect)


def test_contexto_de_fidelidade_permite_so_o_que_foi_calculado_ou_recuperado(ctx):
    f = ctx.for_faithfulness()
    primeiro = ctx.transits[0].aspect
    nome = ctx.positions[primeiro.transit].label
    ok = f"{nome} forma um {primeiro.aspect_pt} com o seu {'Ascendente' if primeiro.natal == 'ascendant' else 'Sol' if primeiro.natal == 'sun' else 'Lua'} natal."
    assert check_faithfulness(ok, f) == []
    envolvidos = {p.label for p in ctx.involved_planets()}
    fora = next(n for n in ("Mercúrio", "Vênus", "Marte", "Júpiter", "Saturno", "Urano", "Netuno", "Plutão")
                if n not in envolvidos and n not in " ".join(d["texto"] for _, d in ctx.docs))
    assert any(fora in w for w in check_faithfulness(f"Hoje {fora} pede atenção.", f))


def test_lua_do_dia_varia_entre_dias(natal):
    sinais = {build_daily_context(kb, natal, date(2026, 11, d)).moon_today.sign for d in range(1, 15)}
    assert len(sinais) >= 4
