from types import SimpleNamespace as NS

import pytest

pytest.importorskip("jsonschema")

from src.common.env import REPO_ROOT
from src.data.kb import KnowledgeBase
from src.rag.generator import AnthropicLLM, LLMError, check_faithfulness, generate_message, message_from_birth
from src.rag.prompt import SYSTEM_PROMPT, build_prompt
from src.rag.retriever import retrieve
from tests.test_rag_retriever import fake_chart

kb = KnowledgeBase.load(REPO_ROOT / "kb")
ASP = [{"planeta_1": "Sol", "planeta_2": "Lua", "aspecto": "sextil", "orbe": 0.95}]


class FakeLLM:
    def __init__(self, text="Mensagem de teste."):
        self.text, self.calls = text, []

    def complete(self, system, user):
        self.calls.append((system, user))
        return self.text


def test_prompt_contem_dados_calculados_e_textos_recuperados():
    ctx = retrieve(kb, fake_chart(aspectos=ASP))
    system, user = build_prompt(ctx)
    assert system == SYSTEM_PROMPT
    assert "- Sol: Áries, 10,5°, casa 3" in user and "- Ascendente: Aquário, 10,5°" in user
    assert "Sol em sextil com Lua" in user
    for _, d in ctx.docs:
        assert d["texto"] in user                       # contexto íntegro, sem alteração
    assert "Mercúrio" not in user.split("## Interpretações")[0]   # ponto não pedido fora dos dados


def test_prompt_sem_aspectos_declara_ausencia():
    _, user = build_prompt(retrieve(kb, fake_chart()))
    assert "Nenhum aspecto calculado" in user


def test_pipeline_com_llm_falso_nao_usa_rede():
    llm = FakeLLM("Você tem Sol em Áries e Lua em Gêmeos, com Ascendente em Aquário.")
    out = generate_message(kb, fake_chart(aspectos=ASP), llm)
    assert out.text.startswith("Você tem Sol")
    assert len(llm.calls) == 1 and out.user == llm.calls[0][1]
    assert out.warnings == []


def test_checagem_de_fidelidade_detecta_invencao():
    ctx = retrieve(kb, fake_chart())
    ruim = "Seu Mercúrio em Câncer na casa 9 forma um trígono com Saturno."
    avisos = " | ".join(check_faithfulness(ruim, ctx))
    assert "Câncer" in avisos and "casa 9" in avisos and "trígono" in avisos
    assert "Saturno" in avisos or "Mercúrio" in avisos


def test_checagem_aceita_o_que_foi_recuperado_ou_calculado():
    ctx = retrieve(kb, fake_chart(aspectos=ASP))
    ok = "Seu Sol em Áries, na casa 3, faz um sextil com a Lua em Gêmeos; o Ascendente em Aquário completa o quadro."
    assert check_faithfulness(ok, ctx) == []


def test_pipeline_a_partir_de_dados_de_nascimento():
    from src.astrology.chart import BirthData
    b = BirthData(2000, 1, 1, 12, 0, city="Greenwich", nation="GB", lat=51.4769, lng=0.0, tz_str="UTC")
    out = message_from_birth(kb, b, FakeLLM("Sol em Capricórnio."))
    assert "- Sol: Capricórnio" in out.user and out.context.missing == []


def test_base_incompleta_interrompe_antes_de_chamar_a_llm():
    llm = FakeLLM()
    with pytest.raises(LLMError):
        generate_message(KnowledgeBase([]), fake_chart(), llm)
    assert llm.calls == []


# --- AnthropicLLM com cliente falso (nenhuma chamada real, nenhum custo) ---------------------------
def fake_client(stop_reason="end_turn", content=None):
    captured = {}

    def create(**kw):
        captured.update(kw)
        return NS(stop_reason=stop_reason, stop_details=None,
                  content=content if content is not None else [NS(type="thinking", text=""), NS(type="text", text=" Olá. ")])

    return NS(messages=NS(create=create)), captured


def test_anthropic_llm_monta_requisicao_e_extrai_texto():
    client, cap = fake_client()
    out = AnthropicLLM(client=client).complete("SYS", "USER")
    assert out == "Olá."
    assert cap["model"] == "claude-haiku-5-5" and cap["system"] == "SYS"
    assert cap["messages"] == [{"role": "user", "content": "USER"}]
    assert cap["output_config"] == {"effort": "low"} and "temperature" not in cap and "thinking" not in cap


@pytest.mark.parametrize("reason", ["refusal", "max_tokens"])
def test_anthropic_llm_trata_recusa_e_truncamento(reason):
    client, _ = fake_client(stop_reason=reason)
    with pytest.raises(LLMError):
        AnthropicLLM(client=client).complete("s", "u")


def test_anthropic_llm_sem_texto_levanta_erro():
    client, _ = fake_client(content=[NS(type="thinking", text="")])
    with pytest.raises(LLMError):
        AnthropicLLM(client=client).complete("s", "u")


def test_modelo_padrao_e_haiku_e_pode_ser_trocado():
    from src.rag.generator import DEFAULT_MODEL
    assert DEFAULT_MODEL == "claude-haiku-5-5"
    client, cap = fake_client()
    AnthropicLLM(model="claude-opus-5-5", client=client).complete("s", "u")
    assert cap["model"] == "claude-opus-5-5"


def test_notebook_mantem_chamada_paga_desligada_por_padrao():
    import json
    nb = json.loads((REPO_ROOT / "notebooks" / "04_rag.ipynb").read_text(encoding="utf-8"))
    src = "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")
    assert "CONFIRMO_CHAMADA_PAGA = False" in src
    assert "CONFIRMO_CHAMADA_PAGA_TESTES = False" in src        # seção de vários mapas também desligada
    assert "CONFIRMO_CHAMADA_PAGA = True" not in src and "CONFIRMO_CHAMADA_PAGA_TESTES = True" not in src
    assert "mapas_teste.json" in src                      # dados dos mapas ficam só no Drive
    assert "1990" not in src and "1960" not in src        # nenhuma data de nascimento no notebook versionado


def test_oposicao_no_sentido_comum_nao_gera_aviso():
    ctx = retrieve(kb, fake_chart(aspectos=ASP))
    msg = ("O Ascendente em Aquário convida a distinguir a diferença significativa da simples oposição, "
           "e a perceber que pertencer a um grupo não exige abrir mão da singularidade.")
    assert check_faithfulness(msg, ctx) == []


def test_aspecto_inventado_continua_gerando_aviso():
    ctx = retrieve(kb, fake_chart(aspectos=ASP))
    assert any("oposição" in w for w in check_faithfulness("Há uma oposição entre o Sol e a Lua.", ctx))
    assert any("trígono" in w for w in check_faithfulness("Um trígono favorece você.", ctx))      # estrito
    assert any("sextil" in w.lower() or "quadratura" in w
               for w in check_faithfulness("A quadratura de Saturno com a Lua pesa.", ctx))
    assert check_faithfulness("O sextil entre Sol e Lua favorece a conversa.", ctx) == []        # calculado


def test_registro_de_consumo_de_tokens():
    def create(**kw):
        return NS(stop_reason="end_turn", stop_details=None, content=[NS(type="text", text="Olá.")],
                  usage=NS(input_tokens=3000, output_tokens=700))
    llm = AnthropicLLM(client=NS(messages=NS(create=create)))
    out = generate_message(kb, fake_chart(), llm)
    assert out.usage == {"input_tokens": 3000, "output_tokens": 700}
    generate_message(kb, fake_chart(), llm)
    assert llm.total_usage == {"input_tokens": 6000, "output_tokens": 1400, "calls": 2}


def test_consumo_ausente_nao_quebra():
    client, _ = fake_client()                  # resposta sem 'usage'
    llm = AnthropicLLM(client=client)
    assert llm.complete("s", "u") == "Olá." and llm.last_usage is None
    assert generate_message(kb, fake_chart(), FakeLLM()).usage is None


def test_max_tokens_padrao_tem_folga_para_o_raciocinio_do_modelo():
    client, cap = fake_client()
    AnthropicLLM(client=client).complete("s", "u")
    assert cap["max_tokens"] == 4000          # saídas reais ficaram perto de 2000 (texto + raciocínio)
    AnthropicLLM(client=client, max_tokens=1234).complete("s", "u")
    assert cap["max_tokens"] == 1234          # continua configurável
