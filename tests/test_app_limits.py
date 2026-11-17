"""Limite global de uso da API, configurações, concorrência e cache do ambiente de hospedagem. Sem rede e sem custo."""
import json
import threading
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

pytest.importorskip("kerykeion")
pytest.importorskip("jsonschema")

from src.app import limits, service
from src.app.limits import LimitReached, UsageLimiter
from src.astrology.chart import BirthData, calculate_chart
from src.common.env import REPO_ROOT
from src.data.kb import KnowledgeBase
from src.transits.cache import DailyCache, person_key
from tests.test_transits_daily import FakeLLM

kb = KnowledgeBase.load(REPO_ROOT / "kb")
DIA = date(2026, 11, 17)
SP = ZoneInfo("America/Sao_Paulo")


class Relogio:
    def __init__(self, dt):
        self.t = dt.timestamp()

    def __call__(self):
        return self.t

    def avanca(self, segundos):
        self.t += segundos


def agora(h=10, m=0, dia=17):
    return datetime(2026, 11, dia, h, m, tzinfo=SP)


@pytest.fixture()
def mapa():
    return calculate_chart(BirthData(2000, 1, 1, 12, 0, city="Greenwich", nation="GB", lat=51.4769, lng=0.0, tz_str="UTC"))


# ---------------- limite global ----------------
def test_limite_diario_bloqueia_a_partir_da_vaga_n_mais_um(tmp_path):
    lim = UsageLimiter(tmp_path, max_daily=3, max_hourly=99, clock=Relogio(agora()))
    for _ in range(3):
        lim.acquire()
    assert lim.check() == "day"
    with pytest.raises(LimitReached) as e:
        lim.acquire()
    assert e.value.reason == "day" and lim.snapshot()["hoje"] == 3          # a tentativa negada não conta


def test_limite_por_hora_desliza_com_o_tempo(tmp_path):
    rel = Relogio(agora())
    lim = UsageLimiter(tmp_path, max_daily=99, max_hourly=2, clock=rel)
    lim.acquire(); lim.acquire()
    assert lim.check() == "hour"
    rel.avanca(3601)
    assert lim.check() is None
    lim.acquire()


def test_contador_zera_na_virada_do_dia_em_sao_paulo(tmp_path):
    rel = Relogio(agora(23, 30))
    lim = UsageLimiter(tmp_path, max_daily=1, max_hourly=99, clock=rel)
    lim.acquire()
    assert lim.check() == "day"
    rel.avanca(3600)                                   # 00:30 do dia seguinte (no fuso de São Paulo)
    assert lim.check() is None


def test_chave_de_emergencia_pausa_a_geracao(tmp_path):
    lim = UsageLimiter(tmp_path, enabled=False, clock=Relogio(agora()))
    assert lim.check() == "off"
    with pytest.raises(LimitReached) as e:
        lim.acquire()
    assert e.value.reason == "off"


def test_contador_e_compartilhado_entre_instancias_e_sobrevive_ao_reinicio(tmp_path):
    rel = Relogio(agora())
    UsageLimiter(tmp_path, max_daily=2, clock=rel).acquire()
    outro = UsageLimiter(tmp_path, max_daily=2, clock=rel)            # outra sessão / outro objeto
    assert outro.snapshot()["hoje"] == 1
    limits._MEMORY.clear()                                            # simula novo processo: só resta o arquivo
    assert UsageLimiter(tmp_path, max_daily=2, clock=rel).snapshot()["hoje"] == 1


def test_arquivo_corrompido_nao_derruba_nem_libera_alem_da_memoria(tmp_path):
    rel = Relogio(agora())
    lim = UsageLimiter(tmp_path, max_daily=2, clock=rel)
    lim.acquire()
    next(tmp_path.glob("uso-*.json")).write_text("{quebrado", encoding="utf-8")
    assert lim.snapshot()["hoje"] == 1                                # usa a memória; não explode
    lim.acquire()
    assert lim.check() == "day"


def test_sem_disco_o_limite_continua_valendo_em_memoria(tmp_path, monkeypatch):
    def falha(*a, **k):
        raise OSError("disco cheio")
    monkeypatch.setattr("os.replace", falha)
    lim = UsageLimiter(tmp_path / "novo", max_daily=2, max_hourly=99, clock=Relogio(agora()))
    lim.acquire(); lim.acquire()
    with pytest.raises(LimitReached):
        lim.acquire()


def test_muitas_sessoes_ao_mesmo_tempo_nunca_passam_do_limite(tmp_path):
    rel = Relogio(agora())
    ok, negadas = [], []

    def sessao():
        try:
            UsageLimiter(tmp_path, max_daily=10, max_hourly=99, clock=rel).acquire()
            ok.append(1)
        except LimitReached:
            negadas.append(1)

    threads = [threading.Thread(target=sessao) for _ in range(60)]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert len(ok) == 10 and len(negadas) == 50


# ---------------- configuração (Secrets / ambiente) ----------------
def test_configuracao_padrao_e_por_ambiente(monkeypatch, tmp_path):
    monkeypatch.setenv("MENSAGEM_ASTRAL_CACHE_DIR", str(tmp_path / "cache"))
    for v in ("MAX_DAILY_GENERATIONS", "MAX_HOURLY_GENERATIONS", "GENERATION_ENABLED"):
        monkeypatch.delenv(v, raising=False)
    lim = service.usage_limiter()
    assert (lim.max_daily, lim.max_hourly, lim.enabled) == (limits.DEFAULT_MAX_DAILY, limits.DEFAULT_MAX_HOURLY, True)
    assert lim.root == tmp_path / "uso"
    monkeypatch.setenv("MAX_DAILY_GENERATIONS", "7"); monkeypatch.setenv("MAX_HOURLY_GENERATIONS", "3")
    lim = service.usage_limiter()
    assert (lim.max_daily, lim.max_hourly) == (7, 3)


def test_configuracao_vem_dos_secrets_e_o_ambiente_tem_prioridade(monkeypatch):
    monkeypatch.delenv("MAX_DAILY_GENERATIONS", raising=False)
    secrets = {"MAX_DAILY_GENERATIONS": "5"}
    assert service.usage_limiter(secrets).max_daily == 5
    monkeypatch.setenv("MAX_DAILY_GENERATIONS", "9")
    assert service.usage_limiter(secrets).max_daily == 9


@pytest.mark.parametrize("valor", ["abc", "-4", "", "1.5"])
def test_valor_invalido_cai_no_padrao_seguro(monkeypatch, valor):
    monkeypatch.setenv("MAX_DAILY_GENERATIONS", valor)
    assert service.usage_limiter().max_daily == limits.DEFAULT_MAX_DAILY


@pytest.mark.parametrize("valor,ativo", [("false", False), ("0", False), ("OFF", False), ("não", False),
                                          ("true", True), ("1", True), ("", True)])
def test_chave_de_emergencia_por_configuracao(monkeypatch, valor, ativo):
    monkeypatch.setenv("GENERATION_ENABLED", valor)
    assert service.usage_limiter().enabled is ativo


# ---------------- geração com limite ----------------
def test_geracao_nova_conta_uma_vaga_e_cache_hit_nao_conta(mapa, tmp_path):
    cache, llm = DailyCache(tmp_path / "c"), FakeLLM()
    lim = UsageLimiter(tmp_path / "u", max_daily=5, clock=Relogio(agora()))
    a = service.generate_message(kb, mapa, DIA, llm, cache, lim)
    b = service.generate_message(kb, mapa, DIA, llm, cache, lim)
    assert not a.from_cache and b.from_cache and len(llm.calls) == 1 and lim.snapshot()["hoje"] == 1


def test_limite_atingido_nao_chama_a_api_nem_grava_cache(mapa, tmp_path):
    cache, llm = DailyCache(tmp_path / "c"), FakeLLM()
    lim = UsageLimiter(tmp_path / "u", max_daily=0, clock=Relogio(agora()))
    with pytest.raises(LimitReached):
        service.generate_message(kb, mapa, DIA, llm, cache, lim)
    assert llm.calls == [] and not list((tmp_path / "c").rglob("*.json"))


def test_mensagem_ja_guardada_continua_disponivel_com_a_geracao_pausada(mapa, tmp_path):
    cache, llm = DailyCache(tmp_path / "c"), FakeLLM()
    service.generate_message(kb, mapa, DIA, llm, cache)
    pausado = UsageLimiter(tmp_path / "u", enabled=False)
    assert service.generate_message(kb, mapa, DIA, llm, cache, pausado).from_cache and len(llm.calls) == 1


def test_duas_sessoes_da_mesma_pessoa_ao_mesmo_tempo_pagam_uma_vez_so(mapa, tmp_path):
    cache, llm = DailyCache(tmp_path / "c"), FakeLLM()
    lim = UsageLimiter(tmp_path / "u", max_daily=99, max_hourly=99)
    textos = []
    threads = [threading.Thread(target=lambda: textos.append(service.generate_message(kb, mapa, DIA, llm, cache, lim).text))
               for _ in range(8)]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert len(llm.calls) == 1 and len(set(textos)) == 1 and lim.snapshot()["hoje"] == 1


# ---------------- cache no ambiente de hospedagem ----------------
def test_gravacao_do_cache_e_atomica_e_nao_deixa_temporarios(mapa, tmp_path):
    cache = DailyCache(tmp_path)
    service.generate_message(kb, mapa, DIA, FakeLLM(), cache)
    assert not list(tmp_path.rglob("*.tmp")) and len(list(tmp_path.rglob("*.json"))) == 1


def test_leitores_nunca_veem_arquivo_pela_metade(mapa, tmp_path):
    cache, llm = DailyCache(tmp_path), FakeLLM()
    service.generate_message(kb, mapa, DIA, llm, cache)
    person, parar, quebrados = person_key(mapa), threading.Event(), []

    def escreve():
        while not parar.is_set():
            cache.set(person, DIA, {"date": DIA.isoformat(), "model": "fake-model", "prompt_version": "x",
                                    "message": "m" * 5000})

    def le():
        for _ in range(300):
            for f in tmp_path.rglob("*.json"):
                try:
                    json.loads(f.read_text(encoding="utf-8"))
                except FileNotFoundError:
                    pass
                except ValueError:
                    quebrados.append(f)

    w, r = threading.Thread(target=escreve), threading.Thread(target=le)
    w.start(); r.start(); r.join(); parar.set(); w.join()
    assert quebrados == []


def test_sal_secreto_muda_o_codigo_da_pessoa_e_e_estavel(mapa, monkeypatch):
    monkeypatch.delenv("MENSAGEM_ASTRAL_CACHE_SALT", raising=False)
    sem_sal = person_key(mapa)
    monkeypatch.setenv("MENSAGEM_ASTRAL_CACHE_SALT", "segredo-a")
    a = person_key(mapa)
    assert a != sem_sal and a == person_key(mapa) and len(a) == 16
    monkeypatch.setenv("MENSAGEM_ASTRAL_CACHE_SALT", "segredo-b")
    assert person_key(mapa) != a


def test_sal_vem_dos_secrets(monkeypatch):
    for v in ("MENSAGEM_ASTRAL_CACHE_SALT", "CACHE_SALT"):
        monkeypatch.delenv(v, raising=False)
    service.apply_secret_settings({"CACHE_SALT": "do-secret"})
    import os
    assert os.environ["MENSAGEM_ASTRAL_CACHE_SALT"] == "do-secret"
    monkeypatch.delenv("MENSAGEM_ASTRAL_CACHE_SALT")


def test_cache_nao_guarda_nome_nem_dados_de_nascimento_nem_sal(mapa, tmp_path, monkeypatch):
    monkeypatch.setenv("MENSAGEM_ASTRAL_CACHE_SALT", "segredo-que-nao-pode-vazar")
    service.generate_message(kb, mapa, DIA, FakeLLM(), DailyCache(tmp_path))
    conteudo = " ".join(f.read_text(encoding="utf-8") + str(f) for f in tmp_path.rglob("*") if f.is_file())
    for proibido in ("segredo-que-nao-pode-vazar", "Greenwich", "2000-01-01", "51.47", "12:00"):
        assert proibido not in conteudo


def test_pessoas_diferentes_nao_acessam_a_mensagem_uma_da_outra(mapa, tmp_path):
    outro = calculate_chart(BirthData(1985, 6, 15, 8, 30, city="Greenwich", nation="GB", lat=51.4769, lng=0.0, tz_str="UTC"))
    cache, llm = DailyCache(tmp_path), FakeLLM("Mensagem da primeira pessoa.")
    service.generate_message(kb, mapa, DIA, llm, cache)
    assert service.cached_message(kb, outro, DIA, cache) is None
