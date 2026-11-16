"""Testes do motor astrológico (offline: coordenadas e fuso informados)."""
import json

import pytest

pytest.importorskip("kerykeion")

from src.astrology.chart import BirthData, calculate_chart, save_chart_json

SP = dict(city="São Paulo", nation="BR", lat=-23.5505, lng=-46.6333, tz_str="America/Sao_Paulo")


def chart(y, m, d, h, mi, **kw):
    return calculate_chart(BirthData(y, m, d, h, mi, **{**SP, **kw}))


def test_estrutura_completa():
    c = chart(1991, 3, 15, 2, 10)
    assert len(c["planetas"]) == 10 and len(c["casas"]) == 12
    assert {"signo_solar", "signo_lunar", "ascendente"} <= c["resumo"].keys()
    assert c["aspectos"]
    json.dumps(c, ensure_ascii=False)  # serializável


def test_conversao_utc_sem_horario_de_verao():
    # Mar/1991 em SP: sem horário de verão (terminou em fev/1991) -> UTC-3
    n = chart(1991, 3, 15, 2, 10)["nascimento"]
    assert n["offset_utc_horas"] == -3 and not n["horario_verao"]
    assert n["horario_utc"].startswith("1991-03-15T05:10")


def test_conversao_utc_com_horario_de_verao():
    # Jan/1991 em SP: horário de verão ativo -> UTC-2
    n = chart(1991, 1, 15, 2, 10)["nascimento"]
    assert n["offset_utc_horas"] == -2 and n["horario_verao"]
    assert n["horario_utc"].startswith("1991-01-15T04:10")


def test_sol_em_j2000():
    # Fato astronômico: em 2000-01-01 12:00 UTC a longitude eclíptica do Sol é ~280,4°
    c = calculate_chart(BirthData(2000, 1, 1, 12, 0, city="Greenwich", nation="GB",
                                  lat=51.4769, lng=0.0, tz_str="UTC"))
    sol = next(p for p in c["planetas"] if p["id"] == "sun")
    assert sol["longitude"] == pytest.approx(280.4, abs=0.3)
    assert sol["signo"] == "Capricórnio"


def test_signo_coerente_com_longitude():
    signos = ["Áries", "Touro", "Gêmeos", "Câncer", "Leão", "Virgem", "Libra",
              "Escorpião", "Sagitário", "Capricórnio", "Aquário", "Peixes"]
    for p in chart(1991, 3, 15, 2, 10)["planetas"]:
        assert signos[int(p["longitude"] // 30)] == p["signo"]


def test_salvar_json(tmp_path):
    out = save_chart_json(chart(1991, 3, 15, 2, 10), tmp_path / "x" / "mapa.json")
    assert json.loads(out.read_text(encoding="utf-8"))["resumo"]["signo_solar"]


def test_mapa_de_referencia_local():
    """Compara com mapa conferido em fonte externa. O arquivo é local (gitignored, dado pessoal)."""
    from pathlib import Path
    ref_file = Path(__file__).parent / "reference_local.json"
    if not ref_file.exists():
        pytest.skip("reference_local.json ausente (dado pessoal, não versionado)")
    ref = json.loads(ref_file.read_text(encoding="utf-8"))
    c = calculate_chart(BirthData(**ref["birth"]))
    pontos = {p["nome"]: p for p in c["planetas"] + c["angulos"]}
    for nome, (signo, grau, retro) in ref["pontos"].items():
        p = pontos[nome]
        assert p["signo"] == signo, nome
        assert int(p["grau_no_signo"]) == grau, nome   # a fonte exibe o grau truncado
        if nome not in ("Ascendente", "Meio do Céu"):
            assert p["retrogrado"] == retro, nome
