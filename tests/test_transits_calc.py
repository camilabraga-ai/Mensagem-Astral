from datetime import date

import pytest

pytest.importorskip("kerykeion")

from src.astrology.chart import BirthData, calculate_chart
from src.transits.calc import (MAX_ORB, TransitPlanet, find_aspects, natal_targets, separation,
                               transit_positions)


@pytest.fixture(scope="module")
def natal():
    """Mapa natal de referência não pessoal (J2000, Greenwich), calculado pelo motor real."""
    return calculate_chart(BirthData(2000, 1, 1, 12, 0, city="Greenwich", nation="GB",
                                     lat=51.4769, lng=0.0, tz_str="UTC"))


def tp(key, lon):
    return TransitPlanet(key, key, "Áries", "aries", lon, lon % 30, False)


def test_posicoes_dos_dez_planetas(natal):
    pos = transit_positions(natal, date(2000, 1, 1))
    assert [p.key for p in pos] == ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn",
                                    "uranus", "neptune", "pluto"]
    assert all(0 <= p.longitude < 360 and 0 <= p.degree < 30 for p in pos)


def test_sol_em_j2000_fato_astronomico(natal):
    sol = transit_positions(natal, date(2000, 1, 1))[0]      # meio-dia UTC em Greenwich
    assert sol.longitude == pytest.approx(280.4, abs=0.3) and sol.sign_pt == "Capricórnio"
    assert sol.sign == "capricorn"


def test_lua_anda_cerca_de_13_graus_por_dia(natal):
    a = transit_positions(natal, date(2026, 11, 17))[1].longitude
    b = transit_positions(natal, date(2026, 11, 18))[1].longitude
    assert 10 < (b - a) % 360 < 16


def test_posicoes_sao_deterministicas(natal):
    assert transit_positions(natal, date(2026, 11, 17)) == transit_positions(natal, date(2026, 11, 17))


def test_separacao_angular_com_virada_de_360():
    assert separation(359, 1) == 2 and separation(10, 190) == 180 and separation(0, 0) == 0


@pytest.mark.parametrize("transit_lon,natal_lon,aspect", [
    (10.0, 10.0, "conjunction"), (70.0, 10.0, "sextile"), (100.0, 10.0, "square"),
    (130.0, 10.0, "trine"), (190.0, 10.0, "opposition"), (359.0, 1.0, "conjunction"),
    (11.0, 281.0, "square"),
])
def test_identifica_cada_aspecto(transit_lon, natal_lon, aspect):
    got = find_aspects([tp("mars", transit_lon)], {"sun": natal_lon})
    assert [(a.aspect, a.orb) for a in got][0][0] == aspect


def test_orbe_calculado_e_limite_respeitado():
    got = find_aspects([tp("mars", 101.5)], {"sun": 10.0})
    assert got[0].aspect == "square" and got[0].orb == 1.5
    assert find_aspects([tp("mars", 10.0 + 90 + MAX_ORB["mars"] + 0.1)], {"sun": 10.0}) == []
    assert find_aspects([tp("mars", 10.0 + 90 + MAX_ORB["mars"])], {"sun": 10.0})   # no limite: entra


def test_planeta_lento_tem_orbe_menor_que_o_sol():
    assert MAX_ORB["sun"] > MAX_ORB["pluto"]
    assert find_aspects([tp("pluto", 14.0)], {"sun": 10.0}) == []           # 4° > orbe de Plutão (3)
    assert find_aspects([tp("sun", 14.0)], {"sun": 10.0})                   # 4° < orbe do Sol (5)


def test_aspecto_em_portugues_para_prompt():
    a = find_aspects([tp("mars", 190.0)], {"sun": 10.0})[0]
    assert a.aspect_pt == "oposição"


def test_alvos_natais_do_mapa(natal):
    t = natal_targets(natal)
    assert set(t) == {"sun", "moon", "ascendant"} and all(0 <= v < 360 for v in t.values())
    with pytest.raises(KeyError):
        natal_targets(natal, keys=("sun", "ceres"))


def test_aspectos_reais_envolvem_apenas_alvos_pedidos(natal):
    asp = find_aspects(transit_positions(natal, date(2026, 11, 17)), natal_targets(natal))
    assert asp and all(a.natal in {"sun", "moon", "ascendant"} for a in asp)
