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


def test_base_tem_224_documentos(kb):
    from collections import Counter
    assert len(kb.docs) == 224
    assert Counter(d["tipo"] for d in kb.docs) == {
        "signo": 12, "planeta": 10, "casa": 12, "aspecto": 5, "elemento": 5,
        "planeta_signo": 120, "elemento_signo": 60}


def test_cobertura_completa_sem_buracos(kb):
    from src.data.kb import SIGN_PT_TO_EN
    signos = set(SIGN_PT_TO_EN.values())
    ids = {d["id"] for d in kb.docs}
    planetas = {d["entidades"]["planeta"] for d in kb.docs if d["tipo"] == "planeta"}
    elementos = {d["entidades"]["elemento"] for d in kb.docs if d["tipo"] == "elemento"}
    assert {f"signo.{s}" for s in signos} <= ids
    assert {f"planeta_signo.{p}.{s}" for p in planetas for s in signos} <= ids       # 10 x 12
    assert {f"elemento_signo.{e}.{s}" for e in elementos for s in signos} <= ids     # 5 x 12
    assert {f"casa.{n}" for n in range(1, 13)} <= ids


def test_planetas_cobrem_os_ids_do_motor_astrologico(kb):
    from src.astrology.chart import PLANETS
    assert {d["entidades"]["planeta"] for d in kb.docs if d["tipo"] == "planeta"} == set(PLANETS)


def test_integracao_com_mapa_do_motor_astrologico(kb):
    """Cada ponto de um mapa real do motor encontra exatamente um documento correspondente."""
    from src.astrology.chart import BirthData, calculate_chart
    c = calculate_chart(BirthData(2000, 1, 1, 12, 0, city="Greenwich", nation="GB",
                                  lat=51.4769, lng=0.0, tz_str="UTC"))
    for p in c["planetas"]:
        assert len(kb.lookup(planeta=p["id"])) == 1, p["id"]
        assert len(kb.lookup(planeta=p["id"], signo=p["signo"])) == 1, p["nome"]   # signo em português
        assert len(kb.lookup(casa=p["casa"])) == 1
    asc, mc = c["angulos"]
    assert len(kb.lookup(elemento=asc["id"], signo=asc["signo"])) == 1
    assert len(kb.lookup(elemento=mc["id"], signo=mc["signo"])) == 1                # medium_coeli -> midheaven
    for a in c["aspectos"]:
        assert len(kb.lookup(aspecto=a["aspecto"])) == 1, a["aspecto"]              # aspecto em português


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
    assert any("ID deveria ser" in e for e in mutate(kb, id="signo.taurus").errors)


def test_vocabulario_em_ingles_e_portugues_rejeitado(kb):
    assert not mutate(kb, entidades={"signo": "Áries"}).ok          # a base usa inglês
    assert not mutate(kb, entidades={"signo": "aries", "elemento": "sun"}).ok


def test_alerta_de_similaridade_continua_ativo(kb):
    docs = copy.deepcopy(kb.docs)
    docs[1]["texto"] = docs[0]["texto"]
    docs[1]["hash_texto"], docs[1]["n_palavras"] = docs[0]["hash_texto"], docs[0]["n_palavras"]
    r = validate_kb(docs)
    assert any("muito parecidos" in w for w in r.warnings)
    assert r.ok                                                       # é alerta, não erro


def test_detecta_id_duplicado_e_texto_duplicado(kb):
    docs = copy.deepcopy(kb.docs)
    docs[1].update(id=docs[0]["id"])
    assert any("duplicado" in e for e in validate_kb(docs).errors)
    docs = copy.deepcopy(kb.docs)
    docs[1].update(texto=docs[0]["texto"], hash_texto=docs[0]["hash_texto"], n_palavras=docs[0]["n_palavras"])
    assert any("parecidos" in w for w in validate_kb(docs).warnings)


def test_indexacao_direta_dos_224(kb):
    recs = kb.rag_records()
    assert len(recs) == 224
    assert len({r["id"] for r in recs}) == 224
    assert recs[0]["texto_indexavel"].startswith(kb.docs[0]["titulo"])
    assert set(recs[0]["metadados"]) == {"tipo", "entidades", "abordagem", "tags", "hash_texto"}


def test_lookup_planeta(kb):
    assert [d["id"] for d in kb.lookup(planeta="moon")] == ["planeta.moon"]
    assert [d["id"] for d in kb.lookup(planeta="moon", signo="Gêmeos")] == ["planeta_signo.moon.gemini"]
    assert [d["id"] for d in kb.lookup(planeta="moon", signo="gemini")] == ["planeta_signo.moon.gemini"]


def test_lookup_por_entidade(kb):
    assert [d["id"] for d in kb.lookup(signo="Gêmeos")] == ["signo.gemini"]
    assert kb.lookup(signo="Gêmeos", casa=3) == []


def test_for_chart_usa_resumo_do_mapa(kb):
    chart = {"resumo": {"signo_solar": "Áries", "signo_lunar": "Gêmeos", "ascendente": "Aquário"}}
    assert kb.for_chart(chart)["signo_lunar"][0]["id"] == "signo.gemini"


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
