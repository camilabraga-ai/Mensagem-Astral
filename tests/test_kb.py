import copy

import pytest

pytest.importorskip("jsonschema")

from src.common.env import REPO_ROOT
from src.data.kb import KnowledgeBase, text_hash, validate_kb, validate_qa

KB_DIR = REPO_ROOT / "kb"


@pytest.fixture()
def kb():
    return KnowledgeBase.load(KB_DIR)


def mutate(kb, **changes):
    docs = copy.deepcopy(kb.docs)
    docs[0].update(changes)
    return validate_kb(docs)


def test_kb_real_valida(kb):
    r = validate_kb(kb.docs)
    assert r.ok, r.errors
    assert not r.warnings, r.warnings


def test_sem_fontes_jsonl_e_sem_campos_removidos(kb):
    assert not (KB_DIR / "fontes.jsonl").exists()
    removidos = {"revisao", "originalidade", "fonte_id", "localizacao_fonte"}
    assert all(not (removidos & d.keys()) for d in kb.docs)
    assert all(d["schema_version"] == "2.0" for d in kb.docs)


def test_campos_antigos_sao_rejeitados(kb):
    assert not mutate(kb, revisao={"status": "aprovado"}).ok
    assert not mutate(kb, fonte_id="x.y").ok


def test_base_tem_22_documentos(kb):
    assert len(kb.docs) == 22
    assert len({d["entidades"]["signo"] for d in kb.docs if d["tipo"] == "signo"}) == 12
    assert len({d["entidades"]["planeta"] for d in kb.docs if d["tipo"] == "planeta"}) == 10


def test_planetas_cobrem_os_ids_do_motor_astrologico(kb):
    from src.astrology.chart import PLANETS
    assert {d["entidades"]["planeta"] for d in kb.docs if d["tipo"] == "planeta"} == set(PLANETS)


def test_textos_preservados(kb):
    # hash conferido contra o texto: nenhum dos 12 textos aprovados foi alterado
    assert all(d["hash_texto"] == text_hash(d["texto"]) for d in kb.docs)
    assert kb.lookup(signo="Áries")[0]["hash_texto"] == (
        "sha256:324a397a3e44776d0b177e37f9f2eabb25573cd88b0110d049071fb8247040cd")


def test_detecta_hash_adulterado(kb):
    assert any("hash" in e for e in mutate(kb, texto=kb.docs[0]["texto"] + " extra").errors)


def test_detecta_n_palavras_errado(kb):
    assert any("n_palavras" in e for e in mutate(kb, n_palavras=5).errors)


def test_detecta_signo_invalido_e_campo_extra(kb):
    assert not mutate(kb, entidades={"signo": "Ofiúco"}).ok
    assert not mutate(kb, extra="x").ok


def test_id_deve_seguir_entidade(kb):
    assert any("ID deveria ser" in e for e in mutate(kb, id="signo.touro").errors)


def test_detecta_id_duplicado_e_texto_duplicado(kb):
    docs = copy.deepcopy(kb.docs)
    docs[1].update(id=docs[0]["id"])
    assert any("duplicado" in e for e in validate_kb(docs).errors)
    docs = copy.deepcopy(kb.docs)
    docs[1].update(texto=docs[0]["texto"], hash_texto=docs[0]["hash_texto"], n_palavras=docs[0]["n_palavras"])
    assert any("parecidos" in w for w in validate_kb(docs).warnings)


def test_indexacao_direta_dos_22(kb):
    recs = kb.rag_records()
    assert len(recs) == 22
    assert recs[0]["texto_indexavel"].startswith(kb.docs[0]["titulo"])
    assert set(recs[0]["metadados"]) == {"tipo", "entidades", "abordagem", "tags", "hash_texto"}


def test_lookup_planeta(kb):
    assert [d["id"] for d in kb.lookup(planeta="moon")] == ["planeta.moon"]
    assert kb.lookup(planeta="moon", signo="Gêmeos") == []   # combinação ainda não existe


def test_lookup_por_entidade(kb):
    assert [d["id"] for d in kb.lookup(signo="Gêmeos")] == ["signo.gemeos"]
    assert kb.lookup(signo="Gêmeos", casa=3) == []


def test_for_chart_usa_resumo_do_mapa(kb):
    chart = {"resumo": {"signo_solar": "Áries", "signo_lunar": "Gêmeos", "ascendente": "Aquário"}}
    assert kb.for_chart(chart)["signo_lunar"][0]["id"] == "signo.gemeos"


def test_hash_ignora_espacos():
    assert text_hash("a  b\n c") == text_hash("a b c")


def _qa(i, grupo, split, doc="signo.aries"):
    return {"schema_version": "2.0", "id": f"qa.{i}", "doc_ids": [doc], "mapa_contexto": {"signo": "Áries"},
            "messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "u"},
                         {"role": "assistant", "content": "a"}],
            "tipo_pergunta": "definicao", "split_grupo": grupo, "split": split}


def test_qa_valido_e_vazamento(kb):
    assert validate_qa([_qa("1", "signo.aries", "train")], kb.docs).ok
    leak = validate_qa([_qa("1", "signo.aries", "train"), _qa("2", "signo.aries", "test")], kb.docs)
    assert any("vazamento" in e for e in leak.errors)
    assert not validate_qa([_qa("3", "signo.aries", "train", doc="signo.nada")], kb.docs).ok
