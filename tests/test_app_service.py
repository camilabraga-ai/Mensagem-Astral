from datetime import date, time
from types import SimpleNamespace as NS

import pytest

pytest.importorskip("kerykeion")
pytest.importorskip("jsonschema")

from src.app import geo, service
from src.app.geo import GeoError, Place, search_places
from src.rag.generator import LLMError
from src.transits.cache import DailyCache
from tests.test_transits_daily import FakeLLM

SP = Place("São Paulo, Brasil", -23.5505, -46.6333, "America/Sao_Paulo")
DIA = date(2026, 11, 17)


@pytest.fixture(scope="module")
def kb():
    return service.load_kb()


# ---------- chave da API e cache ----------
def test_chave_vem_do_ambiente_ou_dos_secrets(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert service.get_api_key() is None
    assert service.get_api_key({"ANTHROPIC_API_KEY": "sk-secreto"}) == "sk-secreto"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env")
    assert service.get_api_key({"ANTHROPIC_API_KEY": "sk-secreto"}) == "sk-env"


def test_secrets_ausentes_nao_quebram(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    class SemArquivo:
        def get(self, k):
            raise FileNotFoundError("secrets.toml")
    assert service.get_api_key(SemArquivo()) is None


def test_diretorio_de_cache_configuravel(monkeypatch, tmp_path):
    monkeypatch.setenv("MENSAGEM_ASTRAL_CACHE_DIR", str(tmp_path / "c"))
    assert service.cache_dir() == tmp_path / "c"
    monkeypatch.delenv("MENSAGEM_ASTRAL_CACHE_DIR")
    assert service.cache_dir().parts[-2:] == (".cache", "mensagens")


def test_modelo_padrao_do_app_e_haiku(monkeypatch):
    llm = service.build_llm("sk-fake")
    assert llm.model == "claude-haiku-5-5"


# ---------- mapa natal e horário de verão ----------
def test_mapa_natal_com_fuso_normal():
    c = service.build_chart(SP, date(1990, 6, 15), time(10, 30))
    assert c["nascimento"]["horario_utc"].startswith("1990-06-15T13:30") and not c["nascimento"]["horario_verao"]


def test_mapa_natal_em_horario_de_verao():
    c = service.build_chart(SP, date(1991, 1, 15), time(2, 10))
    assert c["nascimento"]["horario_utc"].startswith("1991-01-15T04:10") and c["nascimento"]["horario_verao"]


def test_horario_inexistente_e_recusado():
    with pytest.raises(ValueError):
        service.build_chart(SP, date(2018, 11, 4), time(0, 30))


def test_horario_ambiguo_usa_a_escolha_da_pessoa():
    verao = service.build_chart(SP, date(2019, 2, 16), time(23, 30), offset_hours=-2)
    padrao = service.build_chart(SP, date(2019, 2, 16), time(23, 30), offset_hours=-3)
    assert verao["nascimento"]["horario_utc"].startswith("2019-02-17T01:30")
    assert padrao["nascimento"]["horario_utc"].startswith("2019-02-17T02:30")


def test_horario_ambiguo_sem_escolha_e_recusado():
    with pytest.raises(ValueError):
        service.build_chart(SP, date(2019, 2, 16), time(23, 30))


# ---------- mensagem do dia e cache ----------
def test_sem_cache_nao_chama_a_api_e_devolve_none(kb, tmp_path):
    chart = service.build_chart(SP, date(1990, 6, 15), time(10, 30))
    assert service.cached_message(kb, chart, DIA, DailyCache(tmp_path)) is None


def test_gerar_guarda_no_cache_e_consulta_posterior_nao_chama_a_api(kb, tmp_path):
    chart = service.build_chart(SP, date(1990, 6, 15), time(10, 30))
    cache, llm = DailyCache(tmp_path), FakeLLM()
    llm.model = "claude-haiku-5-5"                 # mesmo modelo do app, para o cache coincidir
    gerada = service.generate_message(kb, chart, DIA, llm, cache)
    achada = service.cached_message(kb, chart, DIA, cache)
    assert achada is not None and achada.from_cache and achada.text == gerada.text
    assert len(llm.calls) == 1


def test_cache_de_outro_dia_nao_vale(kb, tmp_path):
    chart = service.build_chart(SP, date(1990, 6, 15), time(10, 30))
    cache, llm = DailyCache(tmp_path), FakeLLM()
    llm.model = "claude-haiku-5-5"
    service.generate_message(kb, chart, DIA, llm, cache)
    assert service.cached_message(kb, chart, date(2026, 11, 18), cache) is None


# ---------- erros amigáveis ----------
@pytest.mark.parametrize("nome,trecho", [
    ("AuthenticationError", "chave de acesso"), ("RateLimitError", "muitas solicitações"),
    ("APIConnectionError", "conectar"), ("APITimeoutError", "conectar"), ("BadRequestError", "indisponível"),
])
def test_erros_da_api_viram_mensagens_em_portugues(nome, trecho):
    exc = type(nome, (Exception,), {})("detalhe técnico com sk-ant-SEGREDO")
    msg = service.friendly_error(exc)
    assert trecho in msg and "sk-ant" not in msg and "detalhe técnico" not in msg


def test_erro_do_pipeline_e_erro_generico():
    assert "Tente novamente" in service.friendly_error(LLMError("x"))
    assert "Algo deu errado" in service.friendly_error(RuntimeError("qualquer"))


# ---------- busca de cidades (sem rede) ----------
def fake_nominatim(monkeypatch, resultado=None, erro=None):
    class N:
        def __init__(self, **kw): pass
        def geocode(self, q, **kw):
            if erro: raise erro
            return resultado
    import geopy.geocoders
    monkeypatch.setattr(geopy.geocoders, "Nominatim", N)


def test_busca_devolve_candidatos_com_fuso(monkeypatch):
    fake_nominatim(monkeypatch, [NS(latitude=-21.4297, longitude=-45.9479, address="Alfenas, Minas Gerais, Brasil"),
                                 NS(latitude=-21.4297, longitude=-45.9479, address="Alfenas, Minas Gerais, Brasil")])
    p = search_places("Alfenas", "Brasil")
    assert len(p) == 1 and p[0].tz == "America/Sao_Paulo" and p[0].label.startswith("Alfenas")


def test_cidade_nao_encontrada(monkeypatch):
    fake_nominatim(monkeypatch, None)
    with pytest.raises(GeoError, match="Não encontramos"):
        search_places("Xyzabc", "Brasil")


def test_servico_de_localizacao_indisponivel(monkeypatch):
    from geopy.exc import GeocoderTimedOut
    fake_nominatim(monkeypatch, erro=GeocoderTimedOut("timeout"))
    with pytest.raises(GeoError, match="serviço de localização"):
        search_places("Alfenas", "Brasil")
