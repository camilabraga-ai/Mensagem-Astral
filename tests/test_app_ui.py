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
    botao(at, "Receber minha mensagem").click()
    return at.run()


def ate_resultado(at, **kw):
    """Preenche e envia. No caso comum vai direto à mensagem; se houver dúvida (cidades/horário), confirma."""
    preencher_e_enviar(at, **kw)
    if [b for b in at.button if b.label == "Ver minha mensagem de hoje"]:
        botao(at, "Ver minha mensagem de hoje").click()
        at.run()
    return at


def textos(at):
    return " ".join([m.value for m in at.markdown] + [e.value for e in at.error] + [i.value for i in at.info]
                    + [w.value for w in at.warning] + [t.value for t in at.title])


# ------------------------------------------------------------------ telas
def test_tela_inicial_e_o_formulario_do_mockup(ambiente):
    at = novo()
    assert not at.exception
    assert [x.value for x in at.title] == ["Mensagem Astral"]
    assert "Uma mensagem do universo para você" in textos(at)
    assert "Seus dados são usados apenas para calcular seu mapa astral" in textos(at)
    assert botao(at, "Receber minha mensagem")


def test_formulario_tem_os_campos_esperados(ambiente):
    at = novo()
    assert [t.label for t in at.text_input] == ["Nome (opcional)", "Cidade de nascimento", "País"]
    assert at.date_input[0].label == "Data de nascimento" and at.time_input[0].label == "Horário de nascimento"
    assert at.text_input[2].value == "Brasil"
    assert at.text_input[0].placeholder == "Seu nome (opcional)"


def test_aviso_sobre_astrologia_fica_na_tela_inicial_e_nao_na_mensagem(ambiente):
    at = novo()
    assert any(e.label.startswith("Sobre a astrologia") for e in at.expander)
    assert "Não é uma ciência nem uma previsão" in textos(at)


def test_formulario_vazio_mostra_erros_claros(ambiente):
    at = novo()
    botao(at, "Receber minha mensagem").click(); at.run()
    msg = textos(at)
    assert "data de nascimento" in msg and "horário de nascimento" in msg and "cidade de nascimento" in msg
    assert not at.exception


def test_cidade_nao_encontrada_mostra_erro_e_nao_avanca(ambiente, monkeypatch):
    def nao_acha(c, p, **kw):
        raise GeoError("Não encontramos 'Xyz' em Brasil. Confira a grafia.")
    monkeypatch.setattr(geo, "search_places", nao_acha)
    at = novo()
    preencher_e_enviar(at, cidade="Xyz")
    assert "Não encontramos" in textos(at) and not at.exception
    assert not [b for b in at.button if b.label == "Ver minha mensagem de hoje"]


def test_horario_inexistente_bloqueia_o_avanco(ambiente):
    at = novo()
    preencher_e_enviar(at, data=date(2018, 11, 4), hora=time(0, 30))
    assert "não existiu" in textos(at)
    assert botao(at, "Ver minha mensagem de hoje").disabled


def test_horario_ambiguo_pede_escolha_e_usa_a_opcao(ambiente):
    at = novo()
    preencher_e_enviar(at, data=date(2019, 2, 16), hora=time(23, 30))
    assert "duas vezes" in textos(at)
    assert [r.label for r in at.radio][-1] == "Qual vale?"
    at.radio[-1].set_value("Horário padrão (UTC-3)"); at.run()
    botao(at, "Ver minha mensagem de hoje").click(); at.run()
    assert not at.exception and at.session_state["chart"]["nascimento"]["horario_utc"].startswith("2019-02-17T02:30")


def test_varias_cidades_pedem_confirmacao(ambiente, monkeypatch):
    outra = Place("São Paulo, Filipinas", 14.0, 121.0, "Asia/Manila")
    monkeypatch.setattr(geo, "search_places", lambda c, p, **kw: [SP, outra])
    at = novo()
    preencher_e_enviar(at)
    assert at.radio[0].label.startswith("Encontramos mais de um lugar")
    at.radio[0].set_value(1); at.run()          # escolhe a segunda
    botao(at, "Ver minha mensagem de hoje").click(); at.run()
    assert at.session_state["chart"]["nascimento"]["fuso"] == "Asia/Manila"


# ------------------------------------------------------------------ mensagem, cache e custo
def sem_botao(at, rotulo):
    return not [b for b in at.button if b.label == rotulo]


def test_botao_principal_gera_a_mensagem_real_na_segunda_tela(ambiente):
    at = ate_resultado(novo())
    assert not at.exception and len(ambiente.calls) == 1 and at.session_state["gen_count"] == 1
    assert [x.value for x in at.title] == ["Sua mensagem de hoje"]
    assert MSG.split(". ")[0] in textos(at) and "ainda não foi gerada" not in textos(at)
    assert sem_botao(at, "Gerar mensagem de hoje") and sem_botao(at, "Tentar novamente")
    assert "leitura simbólica" not in textos(at).lower() and "comprovação científica" not in textos(at)


def test_nada_e_gerado_ao_abrir_a_tela_inicial_nem_ao_chegar_na_confirmacao(ambiente):
    at = novo()
    assert ambiente.calls == []
    preencher_e_enviar(at, data=date(2019, 2, 16), hora=time(23, 30))        # horário ambíguo: pede confirmação
    assert at.session_state["page"] == "confirm" and ambiente.calls == []
    botao(at, "Ver minha mensagem de hoje").click(); at.run()
    assert len(ambiente.calls) == 1


def test_repetir_a_consulta_usa_o_cache_e_nao_chama_a_api(ambiente):
    ate_resultado(novo())
    assert len(ambiente.calls) == 1
    segunda = ate_resultado(novo())                  # nova sessão: mesmos dados, mesmo dia
    assert MSG.split(". ")[0] in textos(segunda) and len(ambiente.calls) == 1 and segunda.session_state["gen_count"] == 0


def test_interagir_com_a_segunda_tela_nao_gera_de_novo(ambiente):
    at = ate_resultado(novo())
    at.run(); at.run()                                # reruns (cliques em expander, etc.)
    assert len(ambiente.calls) == 1 and MSG.split(". ")[0] in textos(at)


def test_dia_seguinte_gera_nova_mensagem(ambiente, monkeypatch):
    ate_resultado(novo())
    monkeypatch.setattr(service, "today_local", lambda: date(2026, 11, 18))
    ate_resultado(novo())
    assert len(ambiente.calls) == 2


def test_pessoa_diferente_nao_reaproveita_a_mensagem_de_outra(ambiente):
    ate_resultado(novo())
    ate_resultado(novo(), data=date(1985, 6, 15), hora=time(8, 30))
    assert len(ambiente.calls) == 2


def test_nome_aparece_na_saudacao_e_nao_vai_para_o_llm(ambiente):
    at = ate_resultado(novo(), nome="Marina")
    assert any("Olá, Marina" in m.value for m in at.markdown)
    sistema, usuario = ambiente.calls[0]
    assert "Marina" not in sistema and "Marina" not in usuario and "1990" not in usuario


def test_sem_chave_a_geracao_fica_desativada_e_nada_e_enviado(ambiente, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    at = ate_resultado(novo())
    assert "desativada" in textos(at) and ambiente.calls == [] and not at.exception
    assert sem_botao(at, "Gerar mensagem de hoje")


def test_limite_de_geracoes_por_sessao(ambiente):
    at = novo()
    at.session_state["gen_count"] = service.MAX_GENERATIONS_PER_SESSION
    ate_resultado(at)
    assert "limite" in textos(at) and ambiente.calls == []


def test_erro_da_api_mostra_mensagem_clara_sem_vazar_chave_e_permite_tentar_de_novo(ambiente, monkeypatch):
    def quebra(key):
        raise type("AuthenticationError", (Exception,), {})("401 sk-teste-falsa")
    monkeypatch.setattr(service, "build_llm", quebra)
    at = ate_resultado(novo())
    erros = " ".join(e.value for e in at.error)
    assert "chave de acesso" in erros and "sk-teste" not in erros and "401" not in erros
    assert not at.exception and at.session_state["gen_count"] == 0 and ambiente.calls == []
    assert "Não foi possível gerar a mensagem agora" in textos(at)
    monkeypatch.setattr(service, "build_llm", lambda key: ambiente)           # a API voltou
    botao(at, "Tentar novamente").click(); at.run()
    assert len(ambiente.calls) == 1 and MSG.split(". ")[0] in textos(at) and sem_botao(at, "Tentar novamente")


def test_erro_de_conexao_e_de_limite_tem_mensagens_proprias(ambiente, monkeypatch):
    for nome, trecho in (("APIConnectionError", "conectar"), ("RateLimitError", "muitas solicitações")):
        def quebra(key, n=nome):
            raise type(n, (Exception,), {})("falha")
        monkeypatch.setattr(service, "build_llm", quebra)
        at = ate_resultado(novo())
        assert trecho in " ".join(e.value for e in at.error)


def test_seu_mapa_mostra_sol_lua_e_ascendente(ambiente):
    at = ate_resultado(novo())
    assert any("Sol:" in m.value and "Ascendente:" in m.value for m in at.markdown)


def test_acesso_direto_ao_resultado_sem_dados_volta_ao_inicio(ambiente):
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["page"] = "result"
    at.run()
    assert not at.exception and botao(at, "Receber minha mensagem") and ambiente.calls == []


def test_chave_da_api_nunca_aparece_na_tela(ambiente):
    at = ate_resultado(novo())
    tudo = textos(at) + " ".join(str(w.value) for w in at.text_input)
    assert "sk-teste-falsa" not in tudo


# ------------------------------------------------------------------ navegação entre telas
def test_voltar_da_confirmacao_preserva_os_dados_digitados(ambiente):
    at = novo()
    preencher_e_enviar(at, nome="Bia", data=date(2019, 2, 16), hora=time(23, 30), cidade="São Paulo")
    assert at.session_state["page"] == "confirm"
    botao(at, "Voltar").click(); at.run()
    assert at.session_state["page"] == "form" and ambiente.calls == []
    assert at.text_input[0].value == "Bia" and at.text_input[1].value == "São Paulo"
    assert at.date_input[0].value == date(2019, 2, 16) and at.time_input[0].value == time(23, 30)


def test_comecar_de_novo_limpa_tudo_e_volta_ao_formulario(ambiente):
    at = ate_resultado(novo(), nome="Bia")
    botao(at, "Começar de novo").click(); at.run()
    assert at.session_state["page"] == "form" and "chart" not in at.session_state
    assert at.text_input[0].value == "" and at.date_input[0].value is None


def test_recarregar_a_pagina_volta_ao_formulario(ambiente):
    ate_resultado(novo())
    assert botao(novo(), "Receber minha mensagem")                        # nova sessão = formulário vazio


def test_ida_e_volta_completa_sem_excecoes(ambiente):
    at = ate_resultado(novo(), data=date(2019, 2, 16), hora=time(23, 30))
    assert not at.exception and at.session_state["page"] == "result"
    botao(at, "Começar de novo").click(); at.run()
    ate_resultado(at)
    assert not at.exception and at.session_state["page"] == "result"


def test_horario_de_nascimento_no_futuro_e_recusado(ambiente, monkeypatch):
    monkeypatch.setattr(service, "birth_in_future", lambda *a, **k: True)
    at = novo(); preencher_e_enviar(at)
    assert "ainda não aconteceu" in textos(at) and at.session_state["page"] == "form" and ambiente.calls == []


def test_caso_comum_vai_direto_para_a_mensagem_sem_tela_de_confirmacao(ambiente):
    at = novo()
    preencher_e_enviar(at)
    assert at.session_state["page"] == "result" and not [b for b in at.button if b.label == "Ver minha mensagem de hoje"]


def test_mensagem_e_escapada_antes_de_virar_html(ambiente, monkeypatch):
    perigosa = "Olá <script>alert(1)</script> e <img src=x onerror=alert(2)>"
    ambiente.text = perigosa
    at = ate_resultado(novo())
    html = " ".join(m.value for m in at.markdown)
    assert "<script>" not in html and "&lt;script&gt;" in html and "<img" not in html


def test_modo_previa_mostra_o_visual_sem_api_nem_calculo(monkeypatch, tmp_path):
    monkeypatch.setenv("MENSAGEM_ASTRAL_PREVIEW", "result")
    monkeypatch.setenv("MENSAGEM_ASTRAL_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    at = AppTest.from_file(APP, default_timeout=60); at.run()
    assert not at.exception and [x.value for x in at.title] == ["Sua mensagem de hoje"]
    assert "Pré-visualização" in textos(at) and not at.button
