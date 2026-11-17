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


def resultado(lat, lng, nome, tipo, **addr):
    return NS(latitude=lat, longitude=lng, address=f"{nome}, rótulo confuso", raw={"name": nome, "addresstype": tipo, "address": addr})


def test_busca_devolve_candidatos_com_fuso_e_rotulo_limpo(monkeypatch):
    mesma = resultado(-21.4297, -45.9479, "Alfenas", "town", town="Alfenas", state="Minas Gerais", country="Brasil")
    fake_nominatim(monkeypatch, [mesma, mesma])
    p = search_places("Alfenas", "Brasil")
    assert len(p) == 1 and p[0].tz == "America/Sao_Paulo" and p[0].label == "Alfenas, Minas Gerais, Brasil"


def test_prefere_localidades_a_estados_e_condados(monkeypatch):
    cidade = resultado(38.71, -9.14, "Lisboa", "city", city="Lisboa", country="Portugal")
    distrito = resultado(39.0, -9.14, "Lisboa", "county", county="Lisboa", country="Portugal")
    fake_nominatim(monkeypatch, [distrito, cidade])
    p = search_places("Lisboa", "Portugal")
    assert [x.lat for x in p] == [38.71] and p[0].label == "Lisboa, Portugal" and p[0].tz == "Europe/Lisbon"


def test_homonimos_aparecem_distinguidos_pelo_estado(monkeypatch):
    fake_nominatim(monkeypatch, [
        resultado(39.8, -89.6, "Springfield", "city", city="Springfield", state="Illinois", country="Estados Unidos"),
        resultado(42.1, -72.6, "Springfield", "city", city="Springfield", state="Massachusetts", country="Estados Unidos")])
    labels = [x.label for x in search_places("Springfield", "Estados Unidos")]
    assert labels == ["Springfield, Illinois, Estados Unidos", "Springfield, Massachusetts, Estados Unidos"]


def test_sem_localidade_usa_o_que_o_servico_devolveu(monkeypatch):
    fake_nominatim(monkeypatch, [resultado(-22.0, -48.4, "Região X", "state", state="São Paulo", country="Brasil")])
    assert len(search_places("Região X", "Brasil")) == 1


def test_cidade_nao_encontrada(monkeypatch):
    fake_nominatim(monkeypatch, None)
    with pytest.raises(GeoError, match="Não encontramos"):
        search_places("Xyzabc", "Brasil")


def test_servico_de_localizacao_indisponivel(monkeypatch):
    from geopy.exc import GeocoderTimedOut
    fake_nominatim(monkeypatch, erro=GeocoderTimedOut("timeout"))
    with pytest.raises(GeoError, match="serviço de localização"):
        search_places("Alfenas", "Brasil")


# ---------- fusos e datas de várias regiões ----------
@pytest.mark.parametrize("tz,d,h,offset,utc_inicio", [
    ("America/Manaus", date(2019, 2, 10), time(8, 0), -4.0, "2019-02-10T12:00"),          # sem horário de verão
    ("America/Rio_Branco", date(2000, 7, 7), time(12, 0), -5.0, "2000-07-07T17:00"),
    ("Europe/Lisbon", date(2021, 7, 1), time(15, 0), 1.0, "2021-07-01T14:00"),            # verão europeu
    ("Asia/Tokyo", date(1990, 1, 1), time(0, 5), 9.0, "1989-12-31T15:05"),                # vira o dia em UTC
    ("Asia/Kolkata", date(1985, 3, 3), time(9, 15), 5.5, "1985-03-03T03:45"),             # deslocamento fracionado
])
def test_fusos_de_varias_regioes(tz, d, h, offset, utc_inicio):
    c = service.build_chart(Place("x", -10.0, -50.0, tz), d, h)
    assert c["nascimento"]["offset_utc_horas"] == offset and c["nascimento"]["horario_utc"].startswith(utc_inicio)


def test_data_antiga_usa_o_fuso_historico_do_local():
    c = service.build_chart(SP, date(1905, 6, 1), time(10, 0))          # antes do horário padrão: UTC-3:06
    assert c["nascimento"]["horario_utc"].startswith("1905-06-01T13:06")


# ---------- nascimento no futuro ----------
def test_nascimento_no_futuro_e_detectado_no_fuso_do_local():
    from datetime import datetime, timezone
    agora = datetime(2026, 11, 17, 3, 0, tzinfo=timezone.utc)            # 00:00 em São Paulo
    assert service.birth_in_future(SP, date(2026, 11, 17), time(0, 30), agora)       # 00:30 local = 03:30 UTC
    assert not service.birth_in_future(SP, date(2026, 11, 17), time(0, 0), agora)
    assert not service.birth_in_future(SP, date(1990, 6, 15), time(10, 30), agora)


# ---------- chamada à API: tempo limite ----------
def test_cliente_da_api_tem_tempo_limite_curto():
    llm = service.build_llm("sk-fake")
    assert llm.client.timeout == 60.0 and llm.client.max_retries == 2


# ---------- cache: reinicialização e falhas ----------
def test_cache_sobrevive_a_reinicializacao_do_processo(kb, tmp_path):
    import json, subprocess, sys
    chart = service.build_chart(SP, date(1990, 6, 15), time(10, 30))
    llm = FakeLLM("Mensagem guardada antes de reiniciar.")
    llm.model = "claude-haiku-5-5"
    service.generate_message(kb, chart, DIA, llm, DailyCache(tmp_path))
    codigo = (
        "import sys; sys.path.insert(0, %r)\n"
        "from datetime import date, time\n"
        "from src.app import service\n"
        "from src.app.geo import Place\n"
        "from src.transits.cache import DailyCache\n"
        "kb = service.load_kb()\n"
        "chart = service.build_chart(Place('x', -23.5505, -46.6333, 'America/Sao_Paulo'), date(1990, 6, 15), time(10, 30))\n"
        "m = service.cached_message(kb, chart, date(2026, 11, 17), DailyCache(%r))\n"
        "print('HIT' if m and m.from_cache else 'MISS', m.text if m else '')\n" % (str(service.REPO_ROOT), str(tmp_path)))
    saida = subprocess.run([sys.executable, "-I", "-c", codigo], capture_output=True, text=True, timeout=120)
    assert saida.stdout.strip().startswith("HIT Mensagem guardada antes de reiniciar."), saida.stderr[-400:]


def test_pequena_variacao_nas_coordenadas_nao_gera_nova_chamada(kb, tmp_path):
    p1 = Place("SP", -23.5505, -46.6333, "America/Sao_Paulo")
    p2 = Place("SP", -23.5507, -46.6334, "America/Sao_Paulo")           # o serviço de cidades variou na 4ª casa
    c1, c2 = (service.build_chart(p, date(1990, 6, 15), time(10, 30)) for p in (p1, p2))
    cache, llm = DailyCache(tmp_path), FakeLLM()
    llm.model = "claude-haiku-5-5"
    service.generate_message(kb, c1, DIA, llm, cache)
    assert service.cached_message(kb, c2, DIA, cache) is not None and len(llm.calls) == 1


def test_falha_ao_gravar_o_cache_nao_perde_a_mensagem_ja_gerada(kb, tmp_path, monkeypatch):
    chart = service.build_chart(SP, date(1990, 6, 15), time(10, 30))
    cache, llm = DailyCache(tmp_path), FakeLLM("Mensagem entregue mesmo sem cache.")
    llm.model = "claude-haiku-5-5"
    def disco_cheio(*a, **k):
        raise OSError("sem espaço")
    monkeypatch.setattr(DailyCache, "set", disco_cheio)
    out = service.generate_message(kb, chart, DIA, llm, cache)
    assert out.text.startswith("Mensagem entregue") and len(llm.calls) == 1


def test_cidade_com_mesmo_nome_do_estado_mostra_os_dois(monkeypatch):
    fake_nominatim(monkeypatch, [resultado(-23.55, -46.63, "São Paulo", "municipality", municipality="São Paulo",
                                           state="São Paulo", country="Brasil")])
    assert search_places("São Paulo, SP", "Brasil")[0].label == "São Paulo, São Paulo, Brasil"
