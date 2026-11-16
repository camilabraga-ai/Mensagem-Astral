"""Base de conhecimento astrológico: carregamento, validação, consulta e preparo para RAG.

Formato: JSONL (ver src/data/schemas/*.schema.json, schema v1.1). Duas camadas de checagem:
  1. JSON Schema (estrutura, tipos, vocabulário);
  2. regras semânticas (IDs únicos, fontes, hash, contagem, coerência entidade/ID, duplicatas, política de uso).
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA_DIR = Path(__file__).parent / "schemas"
STATUS_RAG = {"revisado", "aprovado"}
REQUIRED_ENTITY = {"signo": {"signo"}, "planeta": {"planeta"}, "casa": {"casa"}, "aspecto": {"aspecto"}}
WORDS_MIN, WORDS_MAX = 80, 300


def _schema(name: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8")))


def read_jsonl(path: str | Path) -> list[dict]:
    rows = []
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise ValueError(f"{path}:{n}: JSON inválido ({e})") from e
    return rows


def normalize_text(text: str) -> str:
    """NFC + espaços colapsados. É a base do hash_texto."""
    return " ".join(unicodedata.normalize("NFC", text).split())


def text_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def slug(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if c.isalnum() and ord(c) < 128)


def _shingles(text: str, n: int = 6) -> set[str]:
    w = normalize_text(text).lower().split()
    return {" ".join(w[i:i + n]) for i in range(max(len(w) - n + 1, 0))}


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_kb(docs: list[dict], fontes: list[dict]) -> Report:
    r = Report()
    dv, fv = _schema("documento"), _schema("fonte")
    for f in fontes:
        for e in fv.iter_errors(f):
            r.errors.append(f"fonte {f.get('id')}: {e.message}")
    fmap = {f["id"]: f for f in fontes if "id" in f}
    if len(fmap) != len(fontes):
        r.errors.append("fontes: IDs duplicados")

    seen: dict[str, dict] = {}
    for d in docs:
        i = d.get("id", "?")
        errs = list(dv.iter_errors(d))
        for e in errs:
            r.errors.append(f"{i}: {'/'.join(map(str, e.path)) or 'raiz'}: {e.message[:120]}")
        if errs:
            continue
        if i in seen:
            r.errors.append(f"{i}: ID duplicado")
        seen[i] = d
        f = fmap.get(d["fonte_id"])
        if f is None:
            r.errors.append(f"{i}: fonte inexistente ({d['fonte_id']})")
        if d["hash_texto"] != text_hash(d["texto"]):
            r.errors.append(f"{i}: hash_texto não confere")
        n = len(d["texto"].split())
        if d["n_palavras"] != n:
            r.errors.append(f"{i}: n_palavras={d['n_palavras']} mas o texto tem {n}")
        if not WORDS_MIN <= n <= WORDS_MAX:
            r.warnings.append(f"{i}: {n} palavras (faixa sugerida {WORDS_MIN}-{WORDS_MAX})")
        need = REQUIRED_ENTITY.get(d["tipo"])
        if need and not need <= d["entidades"].keys():
            r.errors.append(f"{i}: tipo '{d['tipo']}' exige entidades {sorted(need)}")
        if d["tipo"] in ("signo", "planeta"):
            key = "signo" if d["tipo"] == "signo" else "planeta"
            expected = f"{d['tipo']}.{slug(str(d['entidades'].get(key, '')))}"
            if d["id"] != expected:
                r.errors.append(f"{i}: ID deveria ser '{expected}'")
        if d["split_grupo"] != d["id"] and d["tipo"] in ("signo", "planeta", "casa", "aspecto"):
            r.warnings.append(f"{i}: split_grupo difere do id")
        rev = d["revisao"]
        if rev["status"] in STATUS_RAG and not (rev["revisor"] and rev["data"]):
            r.errors.append(f"{i}: status '{rev['status']}' exige revisor e data")
        if f is not None:
            if rev["status"] == "aprovado" and not f["autorizado"]:
                r.errors.append(f"{i}: aprovado, mas a fonte {f['id']} não está autorizada")
            if (d["originalidade"] == "gerado_por_ia") != (f["licenca"] == "gerada_por_ia"):
                r.errors.append(f"{i}: originalidade e licença da fonte inconsistentes")

    sh = {i: _shingles(d["texto"]) for i, d in seen.items()}
    ids = list(sh)
    for a in range(len(ids)):
        for b in range(a + 1, len(ids)):
            inter = len(sh[ids[a]] & sh[ids[b]])
            union = len(sh[ids[a]] | sh[ids[b]]) or 1
            if inter / union > 0.3:
                r.warnings.append(f"{ids[a]} ~ {ids[b]}: textos muito parecidos (Jaccard {inter/union:.2f})")
    return r


def validate_qa(qas: list[dict], docs: list[dict]) -> Report:
    r = Report()
    qv, dids = _schema("qa"), {d["id"] for d in docs}
    groups = {d["id"]: d["split_grupo"] for d in docs}
    seen_ids, group_split = set(), {}
    for q in qas:
        i = q.get("id", "?")
        for e in qv.iter_errors(q):
            r.errors.append(f"{i}: {e.message[:120]}")
        if i in seen_ids:
            r.errors.append(f"{i}: ID duplicado")
        seen_ids.add(i)
        for did in q.get("doc_ids", []):
            if did not in dids:
                r.errors.append(f"{i}: doc_id inexistente ({did})")
        g, s = q.get("split_grupo"), q.get("split")
        if group_split.setdefault(g, s) != s:
            r.errors.append(f"{i}: grupo '{g}' aparece em splits diferentes (vazamento)")
        if g not in set(groups.values()):
            r.warnings.append(f"{i}: split_grupo '{g}' não corresponde a nenhum documento")
    return r


class KnowledgeBase:
    """Consulta determinística por entidades do mapa + preparo de documentos para embeddings."""

    def __init__(self, docs: list[dict], fontes: list[dict]):
        self.docs = docs
        self.fontes = {f["id"]: f for f in fontes}

    @classmethod
    def load(cls, kb_dir: str | Path) -> "KnowledgeBase":
        kb_dir = Path(kb_dir)
        return cls(read_jsonl(kb_dir / "documentos.jsonl"), read_jsonl(kb_dir / "fontes.jsonl"))

    def usable(self, dev_mode: bool = False) -> list[dict]:
        """Política de uso: só indexa revisado/aprovado e fonte autorizada. dev_mode inclui rascunhos."""
        out = []
        for d in self.docs:
            ok_status = dev_mode or d["revisao"]["status"] in STATUS_RAG
            ok_source = dev_mode or self.fontes[d["fonte_id"]]["autorizado"]
            if ok_status and ok_source:
                out.append(d)
        return out

    def lookup(self, dev_mode: bool = False, **entidades) -> list[dict]:
        """Ex.: kb.lookup(signo="Áries"). Casa exatamente as entidades pedidas."""
        return [d for d in self.usable(dev_mode) if all(d["entidades"].get(k) == v for k, v in entidades.items())
                and set(d["entidades"]) == set(entidades)]

    def for_chart(self, chart: dict, dev_mode: bool = False) -> dict[str, list[dict]]:
        """Documentos de signo para Sol, Lua e Ascendente de um mapa gerado por src.astrology.chart."""
        out = {}
        for rotulo, signo in chart["resumo"].items():
            out[rotulo] = self.lookup(dev_mode=dev_mode, signo=signo)
        return out

    def rag_records(self, dev_mode: bool = False) -> list[dict]:
        """Registros prontos para embedding: texto indexável + metadados para filtro/citação."""
        recs = []
        for d in self.usable(dev_mode):
            f = self.fontes[d["fonte_id"]]
            recs.append({
                "id": d["id"],
                "texto_indexavel": f"{d['titulo']}. {normalize_text(d['texto'])}",
                "metadados": {
                    "tipo": d["tipo"], "entidades": d["entidades"], "abordagem": d["abordagem"],
                    "tags": d["tags"], "fonte_id": d["fonte_id"], "fonte_titulo": f["titulo"],
                    "revisao": d["revisao"]["status"], "hash_texto": d["hash_texto"],
                },
            })
        return recs
