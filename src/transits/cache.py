"""Cache diário em arquivos JSON: a mesma pessoa recebe a mesma mensagem ao consultar o mesmo dia.

Arquivo: <raiz>/<pessoa>/<AAAA-MM-DD>.<PROMPT_VERSION>.json (uma versão de prompt nunca sobrescreve a mensagem
guardada por outra; arquivos antigos <AAAA-MM-DD>.json continuam sendo lidos). A pessoa é identificada por um hash do instante e do local de
nascimento (sem guardar os dados em claro). A mensagem só é regerada quando muda a data, o modelo, a versão do
prompt (PROMPT_VERSION), ou quando se pede `force=True`. Em produção a raiz fica no Drive, fora do GitHub.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
from datetime import date
from pathlib import Path


def person_key(chart: dict) -> str:
    n = chart["nascimento"]
    # coordenadas com 2 casas (~1 km): o serviço de cidades pode variar nas últimas casas e isso não deve gerar nova chamada
    raw = json.dumps([n["horario_utc"], round(n["latitude"], 2), round(n["longitude"], 2)])
    # Com um sal secreto (MENSAGEM_ASTRAL_CACHE_SALT) o código não pode ser refeito por quem só tem os arquivos do cache:
    # data/hora/local de nascimento têm pouca entropia e um hash simples poderia ser adivinhado por força bruta.
    salt = os.environ.get("MENSAGEM_ASTRAL_CACHE_SALT")
    if salt:
        return hmac.new(salt.encode(), raw.encode(), hashlib.sha256).hexdigest()[:16]
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class DailyCache:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _path(self, person: str, day: date, prompt_version: str) -> Path:
        return self.root / person / f"{day.isoformat()}.{prompt_version}.json"

    def _legacy_path(self, person: str, day: date) -> Path:
        return self.root / person / f"{day.isoformat()}.json"       # formato anterior (sem a versão no nome)

    def _read(self, path: Path) -> dict | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

    def get(self, person: str, day: date, model: str, prompt_version: str) -> dict | None:
        for path in (self._path(person, day, prompt_version), self._legacy_path(person, day)):
            rec = self._read(path)
            if rec and rec.get("model") == model and rec.get("prompt_version") == prompt_version and rec.get("message"):
                return rec
        return None

    def set(self, person: str, day: date, record: dict) -> Path:
        path = self._path(person, day, record["prompt_version"])
        path.parent.mkdir(parents=True, exist_ok=True)
        # gravação atômica: outra sessão nunca lê um arquivo pela metade (vários usuários no mesmo servidor)
        tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, path)
        return path

    def recent(self, person: str, before: date, n: int = 2, prompt_version: str | None = None) -> list[dict]:
        """Registros dos dias anteriores a `before` (mais recente primeiro), para evitar repetição.

        Um registro por dia; havendo mais de uma versão de prompt no mesmo dia, prefere a de `prompt_version`.
        """
        folder = self.root / person
        if not folder.is_dir():
            return []
        por_dia: dict[date, dict] = {}
        for f in sorted(folder.glob("*.json")):
            try:
                d = date.fromisoformat(f.name.split(".")[0])
            except ValueError:
                continue
            rec = self._read(f)
            if d < before and rec and rec.get("message"):
                if d not in por_dia or rec.get("prompt_version") == prompt_version:
                    por_dia[d] = rec
        return [por_dia[d] for d in sorted(por_dia, reverse=True)[:n]]
