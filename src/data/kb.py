"""Base de conhecimento astrológico: carregamento, validação, consulta e preparo para RAG.

Formato: JSONL (ver src/data/schemas/*.schema.json, schema v2.0). Duas camadas de checagem:
  1. JSON Schema (estrutura, tipos, vocabulário);
  2. regras técnicas (IDs únicos, hash, contagem, coerência entidade/ID, duplicatas).
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA_DIR = Path(__file__).parent / "schemas"
# Chaves de entidades que compõem o ID de cada tipo: id == "<tipo>.<valor1>.<valor2>"
ID_KEYS = {"signo": ["signo"], "planeta": ["planeta"], "casa": ["casa"], "aspecto": ["aspecto"],
           "elemento": ["elemento"], "planeta_signo": ["planeta", "signo"], "elemento_signo": ["elemento", "signo"]}
SIMILARITY_WARN = 0.5   # Jaccard de 6-gramas; acima disso gera aviso (nunca desativado)

# O motor astrológico (src/astrology/chart.py) usa nomes em português para signos e aspectos;
# a base usa inglês. A tradução é feita só na consulta.
SIGN_PT_TO_EN = {"Áries": "aries", "Touro": "taurus", "Gêmeos": "gemini", "Câncer": "cancer", "Leão": "leo",
                 "Virgem": "virgo", "Libra": "libra", "Escorpião": "scorpio", "Sagitário": "sagittarius",
                 "Capricórnio": "capricorn", "Aquário": "aquarius", "Peixes": "pisces"}
ASPECT_PT_TO_EN = {"conjunção": "conjunction", "sextil": "sextile", "quadratura": "square",
                   "trígono": "trine", "oposição": "opposition"}
ALIASES = {"signo": SIGN_PT_TO_EN, "aspecto": ASPECT_PT_TO_EN, "elemento": {"medium_coeli": "midheaven"}}
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


def validate_kb(docs: list[dict]) -> Report:
    r = Report()
    dv = _schema("documento")
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
        if d["hash_texto"] != text_hash(d["texto"]):
            r.errors.append(f"{i}: hash_texto não confere")
        n = len(d["texto"].split())
        if d["n_palavras"] != n:
            r.errors.append(f"{i}: n_palavras={d['n_palavras']} mas o texto tem {n}")
        if not WORDS_MIN <= n <= WORDS_MAX:
            r.warnings.append(f"{i}: {n} palavras (faixa sugerida {WORDS_MIN}-{WORDS_MAX})")
        keys = ID_KEYS.get(d["tipo"])
        if keys:
            if set(d["entidades"]) != set(keys):
                r.errors.append(f"{i}: tipo '{d['tipo']}' exige entidades {keys}")
            else:
                expected = ".".join([d["tipo"]] + [str(d["entidades"][k]) for k in keys])
                if d["id"] != expected:
                    r.errors.append(f"{i}: ID deveria ser '{expected}'")
                if d["split_grupo"] != d["id"]:
                    r.warnings.append(f"{i}: split_grupo difere do id")

    sh = {i: _shingles(d["texto"]) for i, d in seen.items()}
    ids = list(sh)
    for a in range(len(ids)):
        for b in range(a + 1, len(ids)):
            inter = len(sh[ids[a]] & sh[ids[b]])
            union = len(sh[ids[a]] | sh[ids[b]]) or 1
            if inter / union > SIMILARITY_WARN:
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

    def __init__(self, docs: list[dict]):
        self.docs = docs

    @classmethod
    def load(cls, kb_dir: str | Path) -> "KnowledgeBase":
        return cls(read_jsonl(Path(kb_dir) / "documentos.jsonl"))

    def lookup(self, **entidades) -> list[dict]:
        """Ex.: kb.lookup(signo="Áries") ou kb.lookup(planeta="sun", signo="aries").
        Casa exatamente as entidades pedidas. Aceita os nomes em português do motor astrológico."""
        entidades = {k: ALIASES.get(k, {}).get(v, v) for k, v in entidades.items()}
        return [d for d in self.docs if set(d["entidades"]) == set(entidades)
                and all(d["entidades"][k] == v for k, v in entidades.items())]

    def for_chart(self, chart: dict) -> dict[str, list[dict]]:
        """Documentos de signo para Sol, Lua e Ascendente de um mapa gerado por src.astrology.chart."""
        return {rotulo: self.lookup(signo=signo) for rotulo, signo in chart["resumo"].items()}

    def rag_records(self) -> list[dict]:
        """Registros prontos para embedding: texto indexável + metadados para filtro."""
        return [{
            "id": d["id"],
            "texto_indexavel": f"{d['titulo']}. {normalize_text(d['texto'])}",
            "metadados": {"tipo": d["tipo"], "entidades": d["entidades"], "abordagem": d["abordagem"],
                          "tags": d["tags"], "hash_texto": d["hash_texto"]},
        } for d in self.docs]
