from datetime import date, time

import pytest

from src.app.validation import check_local_time, fixed_offset_tz, validate_form

HOJE = date(2026, 11, 17)


def ok(**kw):
    base = dict(nome="Ana", data=date(1990, 5, 1), hora=time(10, 30), cidade="São Paulo", pais="Brasil", today=HOJE)
    return validate_form(**{**base, **kw})


def test_dados_validos():
    assert ok() == [] and ok(nome=None) == [] and ok(nome="") == []


@pytest.mark.parametrize("kw,trecho", [
    ({"data": None}, "data de nascimento"), ({"data": date(2027, 1, 1)}, "futuro"),
    ({"data": date(1850, 1, 1)}, "1900"), ({"hora": None}, "horário"),
    ({"cidade": "  "}, "cidade"), ({"cidade": "a"}, "curto"), ({"pais": ""}, "país"),
    ({"nome": "x" * 61}, "60 caracteres"),
])
def test_erros_em_portugues(kw, trecho):
    assert any(trecho in e for e in ok(**kw))


def test_varios_erros_de_uma_vez():
    assert len(ok(data=None, hora=None, cidade="")) == 3


def test_data_de_hoje_e_valida():
    assert ok(data=HOJE) == []


@pytest.mark.parametrize("d,h,tz,status", [
    (date(1990, 6, 15), time(10, 30), "America/Sao_Paulo", "ok"),
    (date(1991, 1, 15), time(2, 10), "America/Sao_Paulo", "ok"),                 # verão, sem ambiguidade
    (date(2018, 11, 4), time(0, 30), "America/Sao_Paulo", "nonexistent"),        # relógio adiantado 00:00 -> 01:00
    (date(2019, 2, 16), time(23, 30), "America/Sao_Paulo", "ambiguous"),         # relógio atrasado 00:00 -> 23:00
    (date(2021, 3, 28), time(1, 30), "Europe/Lisbon", "nonexistent"),
    (date(2021, 10, 31), time(1, 30), "Europe/Lisbon", "ambiguous"),
    (date(2000, 1, 1), time(12, 0), "UTC", "ok"),
])
def test_horario_local_e_horario_de_verao(d, h, tz, status):
    assert check_local_time(d, h, tz).status == status


def test_ambiguo_traz_os_dois_deslocamentos_verao_primeiro():
    c = check_local_time(date(2019, 2, 16), time(23, 30), "America/Sao_Paulo")
    assert c.offsets_hours == (-2.0, -3.0) and "duas vezes" in c.message()
    assert "não existiu" in check_local_time(date(2018, 11, 4), time(0, 30), "America/Sao_Paulo").message()
    assert check_local_time(date(2000, 1, 1), time(12, 0), "UTC").message() == ""


@pytest.mark.parametrize("h,nome", [(-3, "Etc/GMT+3"), (-2, "Etc/GMT+2"), (0, "Etc/GMT"), (1, "Etc/GMT-1")])
def test_fuso_fixo_por_deslocamento(h, nome):
    assert fixed_offset_tz(h) == nome


def test_fuso_fracionado_nao_suportado():
    with pytest.raises(ValueError):
        fixed_offset_tz(5.5)
