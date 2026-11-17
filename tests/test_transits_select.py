from datetime import date

import pytest

from src.transits.calc import MAX_ORB, TransitAspect
from src.transits.select import (ASPECT_WEIGHT, MIN_SCORE, PLANET_WEIGHT, RECENT_PENALTY, TARGET_WEIGHT,
                                 TOP_N, score, select_transits, transit_key)


def A(transit="mars", natal="sun", aspect="square", orb=0.0):
    return TransitAspect(transit, natal, aspect, orb)


def test_formula_documentada():
    a = A("saturn", "moon", "opposition", 1.0)
    esperado = ASPECT_WEIGHT["opposition"] * PLANET_WEIGHT["saturn"] * TARGET_WEIGHT["moon"] * (1 - 1.0 / MAX_ORB["saturn"])
    assert score(a) == pytest.approx(esperado, abs=1e-4)


def test_orbe_exato_vale_mais_que_orbe_largo():
    assert score(A(orb=0.0)) > score(A(orb=2.0)) > score(A(orb=3.9)) > 0
    assert score(A(orb=MAX_ORB["mars"])) == 0


def test_tipo_de_aspecto_pesa():
    assert score(A(aspect="conjunction")) > score(A(aspect="square")) > score(A(aspect="trine")) > score(A(aspect="sextile"))


def test_planeta_e_alvo_natal_pesam():
    assert score(A("saturn")) > score(A("mercury"))
    assert score(A(natal="sun")) > score(A(natal="ascendant"))


def test_limita_a_quantidade_e_ordena_por_pontuacao():
    aspectos = [A("saturn", "sun", "conjunction", 0.2), A("mars", "moon", "square", 0.5),
                A("venus", "sun", "trine", 1.0), A("mercury", "ascendant", "sextile", 0.5),
                A("jupiter", "moon", "opposition", 2.0)]
    sel = select_transits(aspectos)
    assert len(sel) == TOP_N
    assert [s.score for s in sel] == sorted((s.score for s in sel), reverse=True)
    assert sel[0].aspect.transit == "saturn"
    assert len(select_transits(aspectos, top_n=1)) == 1 and len(select_transits(aspectos, top_n=10)) == 5


def test_descarta_pontuacao_baixa_e_aceita_lista_vazia():
    fraco = A("mercury", "ascendant", "sextile", 2.9)
    assert score(fraco) < MIN_SCORE and select_transits([fraco]) == []
    assert select_transits([]) == []


def test_desempate_e_deterministico():
    a, b = A("mars", "sun", "square", 1.0), A("mars", "moon", "square", 1.0)
    assert select_transits([a, b]) == select_transits([b, a])


def test_marca_transito_exato():
    s = select_transits([A("saturn", "sun", "conjunction", 0.4), A("jupiter", "sun", "trine", 2.0)])
    assert s[0].exact and not s[1].exact


def test_com_trânsitos_reais_nunca_passa_do_limite():
    pytest.importorskip("kerykeion")
    from src.astrology.chart import BirthData, calculate_chart
    from src.transits.calc import find_aspects, natal_targets, transit_positions
    natal = calculate_chart(BirthData(2000, 1, 1, 12, 0, city="Greenwich", nation="GB",
                                      lat=51.4769, lng=0.0, tz_str="UTC"))
    for d in range(1, 29):
        asp = find_aspects(transit_positions(natal, date(2026, 11, d)), natal_targets(natal))
        sel = select_transits(asp)
        assert len(sel) <= TOP_N and all(s.score >= MIN_SCORE for s in sel)


def test_transito_recente_perde_prioridade_para_dar_variedade():
    lento = A("saturn", "sun", "square", 1.0)        # em destaque nos últimos dias
    novo = A("venus", "moon", "trine", 0.5)
    sem = select_transits([lento, novo], top_n=1)
    assert sem[0].aspect.transit == "saturn"
    com = select_transits([lento, novo], top_n=1, recent={transit_key(lento)})
    assert com[0].aspect.transit == "venus"


def test_penalidade_aplica_fator_documentado_e_pode_eliminar_fraco():
    a = A("mercury", "sun", "sextile", 1.0)
    base = select_transits([a], min_score=0.0)[0].score
    assert select_transits([a], min_score=0.0, recent={transit_key(a)})[0].score == pytest.approx(base * RECENT_PENALTY, abs=1e-4)
