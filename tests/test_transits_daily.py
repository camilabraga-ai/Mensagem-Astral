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


def test_prompt_define_estilo_conversacional_curto():
    p = DAILY_SYSTEM_PROMPT
    assert "no máximo 2 parágrafos curtos" in p and "entre 70 e 100 palavras" in p
    assert "natural, contemporâneo, inteligente e conversacional" in p
    assert "Frases simples, fluidas e objetivas" in p
    assert "Nada de previsões" in p
    assert "não recontar quem a pessoa é" in p and "não repita ideias, aberturas" in p


def test_prompt_proibe_poesia_metaforas_e_construcoes_artificiais():
    p = DAILY_SYSTEM_PROMPT
    assert "Sem metáforas, frases de efeito ou linguagem poética" in p
    for expressao in ("o céu convida", "dar forma às ideias", "deixar a sensação assentar"):
        assert expressao in p                       # citadas como exemplos do que evitar
    assert "levemente poético" not in p             # a instrução da versão anterior saiu


def test_prompt_mantem_astrologia_como_base_sem_virar_explicacao_tecnica():
    p = DAILY_SYSTEM_PROMPT
    assert "A astrologia é o fundamento" in p and "não é uma explicação técnica" in p
    assert "no máximo um ou dois elementos do céu" in p and "Sem jargão" in p


def test_prompt_pede_observacao_e_sugestao_pratica_sem_autoajuda():
    p = DAILY_SYSTEM_PROMPT
    assert "observação relevante" in p and "sugestão prática pequena e concreta" in p
    assert "autoajuda" in p and "aconselhamento terapêutico" in p


def test_prompt_nao_pede_aviso_de_leitura_simbolica_e_o_proibe():
    p = DAILY_SYSTEM_PROMPT
    assert "NÃO inclua avisos" in p and "apresentada separadamente" in p
    assert "Feche com" not in p and "120 a 180" not in p        # instruções antigas removidas


def test_versao_do_prompt_mudou_para_invalidar_mensagens_em_cache():
    assert prompt_mod.PROMPT_VERSION not in ("daily-1", "daily-2")


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


def test_mensagem_fiel_nao_gera_aviso(natal):
    ctx = build_daily_context(kb, natal, D1)
    t = ctx.transits[0].aspect
    alvo = {"sun": "Sol", "moon": "Lua", "ascendant": "Ascendente"}[t.natal]
    msg = f"Hoje {ctx.positions[t.transit].label} em {t.aspect_pt} com o seu {alvo} natal convida a uma pausa."
    assert daily_message(kb, natal, D1, FakeLLM(msg)).warnings == []


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
    registro = json.loads(next(tmp_path.rglob(f"{D1.isoformat()}.json")).read_text(encoding="utf-8"))
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
