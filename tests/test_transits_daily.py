import json
from datetime import date, timedelta

import pytest

pytest.importorskip("kerykeion")
pytest.importorskip("jsonschema")

from src.astrology.chart import BirthData, calculate_chart
from src.common.env import REPO_ROOT
from src.data.kb import KnowledgeBase
from src.rag.generator import LLMError
from src.transits import prompt as prompt_mod
from src.transits.cache import DailyCache, person_key
from src.transits.daily import daily_message
from src.transits.prompt import DAILY_SYSTEM_PROMPT, build_daily_prompt, format_date_pt
from src.transits.retrieval import build_daily_context

kb = KnowledgeBase.load(REPO_ROOT / "kb")
D1 = date(2026, 11, 17)


class FakeLLM:
    """LLM simulado: nenhuma rede, nenhum custo."""
    model = "fake-model"

    def __init__(self, text="Hoje o dia convida a uma pausa curta entre uma tarefa e outra."):
        self.text, self.calls, self.last_usage = text, [], {"input_tokens": 10, "output_tokens": 5}

    def complete(self, system, user):
        self.calls.append((system, user))
        return f"{self.text} [{len(self.calls)}]"


@pytest.fixture(scope="module")
def natal():
    return calculate_chart(BirthData(2000, 1, 1, 12, 0, city="Greenwich", nation="GB",
                                     lat=51.4769, lng=0.0, tz_str="UTC"))


@pytest.fixture(scope="module")
def outro_natal():
    return calculate_chart(BirthData(1985, 6, 15, 8, 30, city="Greenwich", nation="GB",
                                     lat=51.4769, lng=0.0, tz_str="UTC"))


# ---------------- prompt ----------------
def test_data_em_portugues():
    assert format_date_pt(D1) == "terça-feira, 17 de novembro de 2026"
    assert format_date_pt(date(2026, 3, 1)) == "domingo, 1 de março de 2026"


def test_prompt_traz_transitos_natal_e_referencias(natal):
    ctx = build_daily_context(kb, natal, D1)
    system, user = build_daily_prompt(ctx)
    assert system == DAILY_SYSTEM_PROMPT
    assert "terça-feira, 17 de novembro de 2026" in user
    assert f"- Lua do dia: {ctx.moon_today.sign_pt}" in user
    t = ctx.transits[0].aspect
    assert f"em {t.aspect_pt} com o seu" in user and ctx.positions[t.transit].label in user
    for _, d in ctx.docs:
        assert d["texto"] in user
    assert "Mensagens recentes" not in user


def test_prompt_inclui_mensagens_recentes_quando_existem(natal):
    ctx = build_daily_context(kb, natal, D1)
    _, user = build_daily_prompt(ctx, ["Mensagem de ontem."])
    assert "Mensagens recentes" in user and "> Mensagem de ontem." in user


def test_prompt_nao_envia_dados_de_nascimento(natal):
    ctx = build_daily_context(kb, natal, D1)
    _, user = build_daily_prompt(ctx)
    assert "Greenwich" not in user and "2000" not in user and "12:00" not in user


def test_prompt_define_estilo_conversacional_e_evita_repeticao():
    p = DAILY_SYSTEM_PROMPT
    assert "frases simples" in p and "Sem previsões nem afirmações categóricas" in p
    assert "não repita ideias, aberturas, situações nem estrutura" in p


def test_prompt_usa_astrologia_como_fundamento_interno_e_proibe_jargao_no_texto():
    p = DAILY_SYSTEM_PROMPT
    assert "A astrologia orienta a mensagem, mas não é o assunto dela" in p and "raciocínio interno" in p
    assert "NUNCA escreva nomes de planetas" in p and "signos, casas, aspectos" in p and "Nada de jargão astrológico" in p
    assert "no máximo um ou dois elementos do céu" not in p         # a regra anterior (citar planeta) saiu


def test_prompt_prioriza_situacao_cotidiana_e_sugestao_pratica_sem_autoajuda():
    p = DAILY_SYSTEM_PROMPT
    assert "UMA situação concreta" in p and "sugestão pequena e prática" in p
    assert "Não afirme fatos sobre a vida da pessoa" in p
    assert "autoajuda" in p and "terapia" in p and "frases motivacionais genéricas" in p


def test_prompt_abre_com_situacao_concreta_e_sugere_acao_pratica():
    p = DAILY_SYSTEM_PROMPT
    assert "abra o texto já com essa situação" in p and "não com uma reflexão abstrata" in p
    assert "específica daquela situação e possível de fazer hoje" in p


def test_prompt_evita_tom_de_autoajuda_e_perguntas_introspectivas():
    p = DAILY_SYSTEM_PROMPT
    for expressao in ("dar a si mesmo um tempo", "o que realmente importa", "o que está em jogo", "pergunte-se"):
        assert expressao in p                                       # citadas como exemplos do que evitar


def test_prompt_nao_dita_situacao_padrao_e_varia_conforme_o_transito_principal():
    p = DAILY_SYSTEM_PROMPT
    assert "trânsito de maior peso" in p and "dois mapas com trânsitos diferentes devem receber mensagens diferentes" in p
    assert "não existe situação padrão" in p and "Não use conversas tensas, discussões" in p
    for area in ("trabalho e organização", "dinheiro do dia a dia", "casa e família", "sono e energia", "estudos"):
        assert area in p
    for exemplo_antigo in ("uma resposta pendente", "responder depois do almoço", "anotar duas linhas"):
        assert exemplo_antigo not in p          # exemplos concretos eram copiados pelo modelo e igualavam as mensagens


def test_prompt_limita_a_100_palavras_com_folga():
    assert "cerca de 85 palavras" in DAILY_SYSTEM_PROMPT and "NUNCA passe de 100" in DAILY_SYSTEM_PROMPT
    assert "2 parágrafos curtos" in DAILY_SYSTEM_PROMPT


def test_prompt_exige_personalizacao_pelos_transitos():
    p = DAILY_SYSTEM_PROMPT
    assert "não pode ser um conselho genérico" in p and "decorrer dos trânsitos do dia" in p
    assert "não invente trânsitos" in p


def test_prompt_pede_linguagem_natural_sem_poesia():
    p = DAILY_SYSTEM_PROMPT
    assert "natural, contemporânea, pessoal e direta" in p and "Evite linguagem poética" in p
    for expressao in ("o universo conspira", "dar forma às ideias", "deixar a sensação assentar"):
        assert expressao in p                       # citadas como exemplos do que evitar


def test_prompt_nao_pede_aviso_de_leitura_simbolica_e_o_proibe():
    p = DAILY_SYSTEM_PROMPT
    assert "NÃO inclua explicações técnicas nem avisos" in p and "apresentada separadamente" in p
    assert "Feche com" not in p and "120 a 180" not in p        # instruções antigas removidas


def test_prompt_mantem_formato_de_70_a_100_palavras_em_ate_2_paragrafos():
    assert "2 parágrafos curtos" in DAILY_SYSTEM_PROMPT and "entre 70 e 100 palavras" in DAILY_SYSTEM_PROMPT


def test_tarefa_do_usuario_reforca_nao_citar_astrologia(natal):
    ctx = build_daily_context(kb, natal, D1)
    _, user = build_daily_prompt(ctx)
    assert "sem citar planetas, signos, casas, aspectos nem astrologia" in user
    assert "## Trânsitos do dia" in user and "## Interpretações de referência" in user   # fundamento interno preservado


def test_versao_do_prompt_mudou_para_nao_reaproveitar_mensagens_antigas():
    assert prompt_mod.PROMPT_VERSION == "daily-6"


def test_alerta_de_jargao_astrologico_na_mensagem_final():
    ok = "Hoje vale responder primeiro as conversas pendentes e deixar para amanhã o que não for urgente."
    assert prompt_mod.check_no_jargon(ok) == []
    ruim = prompt_mod.check_no_jargon("A Lua em Aquário e uma quadratura com Marte pedem calma na casa 7.")
    assert len(ruim) == 1 and all(t in ruim[0] for t in ("Lua", "Aquário", "quadratura", "Marte", "casa 7"))
    assert prompt_mod.check_no_jargon("Em dia de sol, pegue a libra de café e ouça o leão do zoológico.") == []


def test_pipeline_registra_alerta_de_jargao_sem_bloquear(natal):
    out = daily_message(kb, natal, D1, FakeLLM("Hoje Marte em Leão pede paciência."))
    assert out.text.startswith("Hoje Marte") and any("termo astrológico" in w for w in out.warnings)
    limpo = daily_message(kb, natal, D1, FakeLLM("Hoje vale esperar um pouco antes de responder."))
    assert not any("termo astrológico" in w for w in limpo.warnings)


# ---------------- pipeline e fidelidade ----------------
def test_pipeline_gera_mensagem_com_llm_simulado(natal):
    llm = FakeLLM()
    out = daily_message(kb, natal, D1, llm)
    assert out.text.endswith("[1]") and len(llm.calls) == 1 and not out.from_cache
    assert out.usage == {"input_tokens": 10, "output_tokens": 5}
    assert out.user == llm.calls[0][1] and out.context.transits


def test_aviso_para_astrologia_inventada(natal):
    ctx = build_daily_context(kb, natal, D1)
    envolvidos = {p.label for p in ctx.involved_planets()}
    texto_refs = " ".join(d["texto"] for _, d in ctx.docs)
    fora = next(n for n in ("Mercúrio", "Vênus", "Marte", "Júpiter", "Saturno", "Urano", "Netuno", "Plutão")
                if n not in envolvidos and n not in texto_refs)
    out = daily_message(kb, natal, D1, FakeLLM(f"Hoje {fora} traz uma quadratura que pesa na sua casa 9."))
    avisos = " | ".join(out.warnings)
    assert fora in avisos and "casa 9" in avisos


def test_mensagem_fiel_nao_gera_aviso_de_fidelidade(natal):
    ctx = build_daily_context(kb, natal, D1)
    t = ctx.transits[0].aspect
    alvo = {"sun": "Sol", "moon": "Lua", "ascendant": "Ascendente"}[t.natal]
    msg = f"Hoje {ctx.positions[t.transit].label} em {t.aspect_pt} com o seu {alvo} natal convida a uma pausa."
    avisos = daily_message(kb, natal, D1, FakeLLM(msg)).warnings
    assert [w for w in avisos if "termo astrológico" not in w] == []     # fiel ao que foi enviado (o jargão tem alerta próprio)


def test_base_sem_documentos_interrompe_antes_do_llm(natal):
    llm = FakeLLM()
    with pytest.raises(LLMError):
        daily_message(KnowledgeBase([]), natal, D1, llm)
    assert llm.calls == []


# ---------------- cache ----------------
def test_mesmo_dia_usa_cache_e_nao_chama_o_llm_de_novo(natal, tmp_path):
    cache, llm = DailyCache(tmp_path), FakeLLM()
    a = daily_message(kb, natal, D1, llm, cache)
    b = daily_message(kb, natal, D1, llm, cache)
    assert len(llm.calls) == 1 and not a.from_cache and b.from_cache and a.text == b.text


def test_cache_sobrevive_a_um_novo_objeto_de_cache(natal, tmp_path):
    llm = FakeLLM()
    a = daily_message(kb, natal, D1, llm, DailyCache(tmp_path))
    b = daily_message(kb, natal, D1, llm, DailyCache(tmp_path))
    assert b.from_cache and a.text == b.text and len(llm.calls) == 1


def test_dia_seguinte_gera_nova_mensagem(natal, tmp_path):
    cache, llm = DailyCache(tmp_path), FakeLLM()
    daily_message(kb, natal, D1, llm, cache)
    b = daily_message(kb, natal, D1 + timedelta(days=1), llm, cache)
    assert len(llm.calls) == 2 and not b.from_cache


def test_force_regera(natal, tmp_path):
    cache, llm = DailyCache(tmp_path), FakeLLM()
    daily_message(kb, natal, D1, llm, cache)
    b = daily_message(kb, natal, D1, llm, cache, force=True)
    assert len(llm.calls) == 2 and not b.from_cache and b.text.endswith("[2]")
    assert daily_message(kb, natal, D1, llm, cache).text.endswith("[2]")      # cache agora guarda a nova


def test_pessoas_diferentes_nao_compartilham_cache(natal, outro_natal, tmp_path):
    assert person_key(natal) != person_key(outro_natal)
    cache, llm = DailyCache(tmp_path), FakeLLM()
    daily_message(kb, natal, D1, llm, cache)
    b = daily_message(kb, outro_natal, D1, llm, cache)
    assert len(llm.calls) == 2 and not b.from_cache


def test_troca_de_modelo_ou_de_versao_do_prompt_regera(natal, tmp_path, monkeypatch):
    cache = DailyCache(tmp_path)
    daily_message(kb, natal, D1, FakeLLM(), cache)
    outro = FakeLLM(); outro.model = "outro-modelo"
    assert not daily_message(kb, natal, D1, outro, cache).from_cache
    monkeypatch.setattr(prompt_mod, "PROMPT_VERSION", "daily-999")
    llm = FakeLLM()
    assert not daily_message(kb, natal, D1, llm, cache).from_cache and len(llm.calls) == 1


def test_arquivo_de_cache_corrompido_e_ignorado(natal, tmp_path):
    cache, llm = DailyCache(tmp_path), FakeLLM()
    daily_message(kb, natal, D1, llm, cache)
    next(tmp_path.rglob("*.json")).write_text("{quebrado", encoding="utf-8")
    assert not daily_message(kb, natal, D1, llm, cache).from_cache and len(llm.calls) == 2


def test_sem_cache_cada_chamada_gera(natal):
    llm = FakeLLM()
    daily_message(kb, natal, D1, llm); daily_message(kb, natal, D1, llm)
    assert len(llm.calls) == 2


def test_cache_nao_guarda_dados_de_nascimento_em_claro(natal, tmp_path):
    daily_message(kb, natal, D1, FakeLLM(), DailyCache(tmp_path))
    arquivo = next(tmp_path.rglob("*.json"))
    conteudo = arquivo.read_text(encoding="utf-8") + str(arquivo)
    assert "Greenwich" not in conteudo and "2000-01-01" not in conteudo


# ---------------- variedade entre dias ----------------
def test_dia_seguinte_recebe_mensagem_anterior_e_penaliza_transito_repetido(natal, tmp_path):
    cache, llm = DailyCache(tmp_path), FakeLLM("Mensagem do primeiro dia.")
    d1 = daily_message(kb, natal, D1, llm, cache)
    d2 = daily_message(kb, natal, D1 + timedelta(days=1), llm, cache)
    assert "Mensagens recentes" in d2.user and "Mensagem do primeiro dia." in d2.user
    registro = json.loads(next(tmp_path.rglob(f"{D1.isoformat()}.*.json")).read_text(encoding="utf-8"))
    assert registro["transits"] and registro["prompt_version"] == prompt_mod.PROMPT_VERSION
    from src.transits.select import RECENT_PENALTY, score
    k1 = {(t.aspect.transit, t.aspect.natal, t.aspect.aspect) for t in d1.context.transits}
    repetidos = [t for t in d2.context.transits if (t.aspect.transit, t.aspect.natal, t.aspect.aspect) in k1]
    assert repetidos                                        # neste mapa os mesmos trânsitos lentos persistem
    assert all(t.score == pytest.approx(score(t.aspect) * RECENT_PENALTY, abs=1e-3) for t in repetidos)


def test_chamadas_pagas_exigem_llm_explicito():
    import inspect
    assert inspect.signature(daily_message).parameters["llm"].default is inspect.Parameter.empty


def test_notebook_05_mantem_chamada_paga_desligada_e_sem_dados_pessoais():
    nb = json.loads((REPO_ROOT / "notebooks" / "05_transitos.ipynb").read_text(encoding="utf-8"))
    src = "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")
    assert "CONFIRMO_CHAMADA_PAGA_DIARIA = False" in src and "CONFIRMO_CHAMADA_PAGA_DIARIA = True" not in src
    assert "DEFAULT_MODEL" in src and "mensagens_diarias" in src        # modelo padrão e cache no Drive
    assert "1990" not in src and "1960" not in src and "1991" not in src


# ---------------- cache por versão do prompt ----------------
def test_nova_versao_do_prompt_nao_sobrescreve_a_mensagem_guardada(natal, tmp_path, monkeypatch):
    cache = DailyCache(tmp_path)
    monkeypatch.setattr(prompt_mod, "PROMPT_VERSION", "daily-A")
    a = daily_message(kb, natal, D1, FakeLLM("Mensagem da versão A."), cache)
    monkeypatch.setattr(prompt_mod, "PROMPT_VERSION", "daily-B")
    llm_b = FakeLLM("Mensagem da versão B.")
    b = daily_message(kb, natal, D1, llm_b, cache)
    assert not b.from_cache and len(llm_b.calls) == 1
    assert len(list(tmp_path.rglob("*.json"))) == 2                     # os dois arquivos coexistem
    monkeypatch.setattr(prompt_mod, "PROMPT_VERSION", "daily-A")
    llm = FakeLLM()
    voltou = daily_message(kb, natal, D1, llm, cache)
    assert voltou.from_cache and voltou.text == a.text and llm.calls == []   # a antiga segue disponível, sem chamada


def test_arquivo_de_cache_no_formato_antigo_ainda_e_lido(natal, tmp_path):
    cache, llm = DailyCache(tmp_path), FakeLLM()
    daily_message(kb, natal, D1, llm, cache)
    novo = next(tmp_path.rglob("*.json"))
    antigo = novo.with_name(f"{D1.isoformat()}.json")
    novo.rename(antigo)                                                  # simula o arquivo gravado antes da mudança
    b = daily_message(kb, natal, D1, llm, cache)
    assert b.from_cache and len(llm.calls) == 1 and antigo.exists()


def test_recentes_preferem_a_versao_atual_e_usam_um_registro_por_dia(natal, tmp_path, monkeypatch):
    cache = DailyCache(tmp_path)
    monkeypatch.setattr(prompt_mod, "PROMPT_VERSION", "daily-A")
    daily_message(kb, natal, D1, FakeLLM("Antiga."), cache)
    monkeypatch.setattr(prompt_mod, "PROMPT_VERSION", "daily-B")
    daily_message(kb, natal, D1, FakeLLM("Nova."), cache)
    rec = cache.recent(person_key(natal), D1 + timedelta(days=1), n=5, prompt_version="daily-B")
    assert [r["message"] for r in rec] == ["Nova. [1]"]
