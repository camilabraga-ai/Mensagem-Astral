import copy

import pytest

pytest.importorskip("jsonschema")

from src.common.env import REPO_ROOT
from src.data.kb import KnowledgeBase, text_hash, validate_kb, validate_qa

KB_DIR = REPO_ROOT / "kb"


@pytest.fixture()
def kb():
    return KnowledgeBase.load(KB_DIR)


def fontes(kb):
    return list(kb.fontes.values())


def test_kb_real_valida(kb):
    r = validate_kb(kb.docs, fontes(kb))
    assert r.ok, r.errors
    assert not r.warnings, r.warnings


def test_cobre_os_12_signos(kb):
    assert len({d["entidades"]["signo"] for d in kb.docs}) == 12


def mutate(kb, **changes):
    docs = copy.deepcopy(kb.docs)
    docs[0].update(changes)
    return validate_kb(docs, fontes(kb))


def test_detecta_hash_adulterado(kb):
    assert any("hash" in e for e in mutate(kb, texto=kb.docs[0]["texto"] + " extra").errors)


def test_detecta_n_palavras_errado(kb):
    assert any("n_palavras" in e for e in mutate(kb, n_palavras=5).errors)


def test_detecta_fonte_inexistente(kb):
    assert any("fonte inexistente" in e for e in mutate(kb, fonte_id="src.nao.existe").errors)


def test_detecta_signo_invalido_e_campo_extra(kb):
    assert not mutate(kb, entidades={"signo": "Ofiúco"}).ok
    assert not mutate(kb, extra="x").ok


def test_id_deve_seguir_entidade(kb):
    assert any("ID deveria ser" in e for e in mutate(kb, id="signo.touro").errors)


def test_revisado_exige_revisor(kb):
    assert any("exige revisor" in e for e in mutate(kb, revisao={"status": "revisado", "revisor": None, "data": None}).errors)


def test_detecta_id_duplicado_e_texto_duplicado(kb):
    docs = copy.deepcopy(kb.docs)
    docs[1].update(id=docs[0]["id"])
    assert any("duplicado" in e for e in validate_kb(docs, fontes(kb)).errors)
    docs = copy.deepcopy(kb.docs)
    docs[1].update(texto=docs[0]["texto"], hash_texto=docs[0]["hash_texto"], n_palavras=docs[0]["n_palavras"])
    assert any("parecidos" in w for w in validate_kb(docs, fontes(kb)).warnings)


def test_politica_rag_exclui_rascunhos(kb):
    assert kb.usable() == []             # tudo é rascunho/não autorizado
    assert len(kb.usable(dev_mode=True)) == 12
    assert kb.rag_records() == []


def test_lookup_por_entidade(kb):
    assert [d["id"] for d in kb.lookup(dev_mode=True, signo="Gêmeos")] == ["signo.gemeos"]
    assert kb.lookup(dev_mode=True, signo="Gêmeos", casa=3) == []


def test_for_chart_usa_resumo_do_mapa(kb):
    chart = {"resumo": {"signo_solar": "Áries", "signo_lunar": "Gêmeos", "ascendente": "Aquário"}}
    got = kb.for_chart(chart, dev_mode=True)
    assert got["signo_lunar"][0]["id"] == "signo.gemeos"


def test_rag_records_formato(kb):
    rec = kb.rag_records(dev_mode=True)[0]
    assert rec["texto_indexavel"].startswith(kb.docs[0]["titulo"]) and rec["metadados"]["fonte_id"]


def test_hash_ignora_espacos():
    assert text_hash("a  b\n c") == text_hash("a b c")


def _qa(i, grupo, split, doc="signo.aries"):
    return {"schema_version": "1.1", "id": f"qa.{i}", "doc_ids": [doc], "mapa_contexto": {"signo": "Áries"},
            "messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "u"},
                         {"role": "assistant", "content": "a"}],
            "tipo_pergunta": "definicao", "origem": "manual", "revisao": {"status": "rascunho"},
            "split_grupo": grupo, "split": split}


def test_qa_valido_e_vazamento(kb):
    assert validate_qa([_qa("1", "signo.aries", "train")], kb.docs).ok
    leak = validate_qa([_qa("1", "signo.aries", "train"), _qa("2", "signo.aries", "test")], kb.docs)
    assert any("vazamento" in e for e in leak.errors)
    assert not validate_qa([_qa("3", "signo.aries", "train", doc="signo.nada")], kb.docs).ok
