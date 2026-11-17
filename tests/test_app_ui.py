"""Interface Streamlit testada de ponta a ponta com AppTest. Sem rede e sem chamadas pagas:
a busca de cidades e o LLM são simulados."""
from datetime import date, time

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("kerykeion")
pytest.importorskip("jsonschema")

from streamlit.testing.v1 import AppTest

from src.app import geo, service
from src.app.geo import GeoError, Place
from src.common.env import REPO_ROOT
from tests.test_transits_daily import FakeLLM

APP = str(REPO_ROOT / "app" / "streamlit_app.py")
SP = Place("São Paulo, Região Metropolitana de São Paulo, Brasil", -23.5505, -46.6333, "America/Sao_Paulo")
HOJE = date(2026, 11, 17)
MSG = "Hoje a conversa fica mais fácil. Vale mandar aquela mensagem que você vem adiando."


@pytest.fixture()
def ambiente(monkeypatch, tmp_path):
    """Ambiente isolado: cache em pasta temporária, chave falsa, LLM e geocodificação simulados."""
    import streamlit as st
    st.cache_data.clear()                           # a busca de cidades é cacheada entre execuções
    monkeypatch.setenv("MENSAGEM_ASTRAL_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-teste-falsa")
    llm = FakeLLM(MSG)
    llm.model = "claude-haiku-5-5"
    monkeypatch.setattr(service, "build_llm", lambda key: llm)
    monkeypatch.setattr(service, "today_local", lambda: HOJE)
    monkeypatch.setattr(geo, "search_places", lambda c, p, **kw: [SP])
    return llm


def novo():
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    return at


def botao(at, rotulo):
    achados = [b for b in at.button if b.label == rotulo]
    assert achados, f"botão '{rotulo}' não encontrado; há: {[b.label for b in at.button]}"
    return achados[0]


def preencher_e_enviar(at, nome="Ana", data=date(1990, 6, 15), hora=time(10, 30), cidade="São Paulo", pais="Brasil"):
    at.text_input[0].set_value(nome)
    at.date_input[0].set_value(data)
    at.time_input[0].set_value(hora)
    at.text_input[1].set_value(cidade)
    at.text_input[2].set_value(pais)
    botao(at, "Continuar").click()
    return at.run()


def ate_resultado(at, **kw):
    botao(at, "Começar").click(); at.run()
    preencher_e_enviar(at, **kw)
    botao(at, "Ver minha mensagem de hoje").click()
    return at.run()


def textos(at):
    return " ".join([m.value for m in at.markdown] + [e.value for e in at.error] + [i.value for i in at.info]
                    + [w.value for w in at.warning] + [t.value for t in at.title])


# ------------------------------------------------------------------ telas
def test_tela_inicial_apresenta_o_produto(ambiente):
    at = novo()
    assert not at.exception
    assert any("Mensagem Astral" in t.value for t in at.title)
    assert "70 a 100 palavras" in textos(at) and "Não pedimos login" in textos(at)
    assert botao(at, "Começar")


def test_formulario_tem_os_campos_esperados(ambiente):
    at = novo(); botao(at, "Começar").click(); at.run()
    assert [t.label for t in at.text_input] == ["Nome (opcional)", "Cidade de nascimento", "País"]
    assert at.date_input[0].label == "Data de nascimento" and at.time_input[0].label == "Horário de nascimento"
    assert at.text_input[2].value == "Brasil"


def test_formulario_vazio_mostra_erros_claros(ambiente):
    at = novo(); botao(at, "Começar").click(); at.run()
    botao(at, "Continuar").click(); at.run()
    msg = textos(at)
    assert "data de nascimento" in msg and "horário de nascimento" in msg and "cidade de nascimento" in msg
    assert not at.exception


def test_cidade_nao_encontrada_mostra_erro_e_nao_avanca(ambiente, monkeypatch):
    def nao_acha(c, p, **kw):
        raise GeoError("Não encontramos 'Xyz' em Brasil. Confira a grafia.")
    monkeypatch.setattr(geo, "search_places", nao_acha)
    at = novo(); botao(at, "Começar").click(); at.run()
    preencher_e_enviar(at, cidade="Xyz")
    assert "Não encontramos" in textos(at) and not at.exception
    assert not [b for b in at.button if b.label == "Ver minha mensagem de hoje"]


def test_horario_inexistente_bloqueia_o_avanco(ambiente):
    at = novo(); botao(at, "Começar").click(); at.run()
    preencher_e_enviar(at, data=date(2018, 11, 4), hora=time(0, 30))
    assert "não existiu" in textos(at)
    assert botao(at, "Ver minha mensagem de hoje").disabled


def test_horario_ambiguo_pede_escolha_e_usa_a_opcao(ambiente):
    at = novo(); botao(at, "Começar").click(); at.run()
    preencher_e_enviar(at, data=date(2019, 2, 16), hora=time(23, 30))
    assert "duas vezes" in textos(at)
    assert [r.label for r in at.radio][-1] == "Qual vale?"
    at.radio[-1].set_value("Horário padrão (UTC-3)"); at.run()
    botao(at, "Ver minha mensagem de hoje").click(); at.run()
    assert not at.exception and at.session_state["chart"]["nascimento"]["horario_utc"].startswith("2019-02-17T02:30")


def test_varias_cidades_pedem_confirmacao(ambiente, monkeypatch):
    outra = Place("São Paulo, Filipinas", 14.0, 121.0, "Asia/Manila")
    monkeypatch.setattr(geo, "search_places", lambda c, p, **kw: [SP, outra])
    at = novo(); botao(at, "Começar").click(); at.run()
    preencher_e_enviar(at)
    assert at.radio[0].label.startswith("Encontramos mais de um lugar")
    at.radio[0].set_value(1); at.run()          # escolhe a segunda
    botao(at, "Ver minha mensagem de hoje").click(); at.run()
    assert at.session_state["chart"]["nascimento"]["fuso"] == "Asia/Manila"


# ------------------------------------------------------------------ mensagem, cache e custo
def test_nenhuma_chamada_paga_ao_carregar_a_pagina_de_resultado(ambiente):
    at = ate_resultado(novo())
    assert not at.exception and ambiente.calls == []
    assert botao(at, "Gerar mensagem de hoje") and "ainda não foi gerada" in textos(at)


def test_clicar_em_gerar_mostra_a_mensagem_e_chama_a_api_uma_vez(ambiente):
    at = ate_resultado(novo())
    botao(at, "Gerar mensagem de hoje").click(); at.run()
    assert not at.exception and len(ambiente.calls) == 1
    assert MSG.split(". ")[0] in textos(at) and at.session_state["gen_count"] == 1
    assert "leitura simbólica" not in textos(at).lower() and "comprovação científica" not in textos(at)


def test_mensagem_em_cache_aparece_sem_nova_chamada(ambiente):
    at = ate_resultado(novo())
    botao(at, "Gerar mensagem de hoje").click(); at.run()
    assert len(ambiente.calls) == 1
    outro = ate_resultado(novo())                   # nova sessão, mesmos dados e mesmo dia
    assert MSG.split(". ")[0] in textos(outro) and len(ambiente.calls) == 1
    assert not [b for b in outro.button if b.label == "Gerar mensagem de hoje"]


def test_nome_aparece_na_saudacao_e_nao_vai_para_o_llm(ambiente):
    at = ate_resultado(novo(), nome="Marina")
    assert any(t.value == "Olá, Marina" for t in at.title)
    botao(at, "Gerar mensagem de hoje").click(); at.run()
    sistema, usuario = ambiente.calls[0]
    assert "Marina" not in sistema and "Marina" not in usuario and "1990" not in usuario


def test_sem_chave_a_geracao_fica_desativada(ambiente, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    at = ate_resultado(novo())
    assert "desativada" in textos(at) and not [b for b in at.button if b.label == "Gerar mensagem de hoje"]
    assert ambiente.calls == []


def test_limite_de_geracoes_por_sessao(ambiente):
    at = ate_resultado(novo())
    at.session_state["gen_count"] = service.MAX_GENERATIONS_PER_SESSION
    at.run()
    assert "limite" in textos(at) and not [b for b in at.button if b.label == "Gerar mensagem de hoje"]


def test_erro_da_api_vira_mensagem_clara_sem_vazar_chave(ambiente, monkeypatch):
    def quebra(key):
        raise type("AuthenticationError", (Exception,), {})("401 sk-teste-falsa")
    monkeypatch.setattr(service, "build_llm", quebra)
    at = ate_resultado(novo())
    botao(at, "Gerar mensagem de hoje").click(); at.run()
    erros = " ".join(e.value for e in at.error)
    assert "chave de acesso" in erros and "sk-teste" not in erros and "401" not in erros
    assert not at.exception and at.session_state["gen_count"] == 0


def test_seu_mapa_mostra_sol_lua_e_ascendente(ambiente):
    at = ate_resultado(novo())
    assert any("Sol:" in m.value and "Ascendente:" in m.value for m in at.markdown)


def test_acesso_direto_ao_resultado_sem_dados_volta_ao_inicio(ambiente):
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["page"] = "result"
    at.run()
    assert not at.exception and botao(at, "Começar")


def test_chave_da_api_nunca_aparece_na_tela(ambiente):
    at = ate_resultado(novo())
    botao(at, "Gerar mensagem de hoje").click(); at.run()
    tudo = textos(at) + " ".join(str(w.value) for w in at.text_input)
    assert "sk-teste-falsa" not in tudo
