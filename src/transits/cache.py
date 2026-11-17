"""Cache diário em arquivos JSON: a mesma pessoa recebe a mesma mensagem ao consultar o mesmo dia.

Arquivo: <raiz>/<pessoa>/<AAAA-MM-DD>.json. A pessoa é identificada por um hash do instante e do local de
nascimento (sem guardar os dados em claro). A mensagem só é regerada quando muda a data, o modelo, a versão do
prompt (PROMPT_VERSION), ou quando se pede `force=True`. Em produção a raiz fica no Drive, fora do GitHub.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path


def person_key(chart: dict) -> str:
    n = chart["nascimento"]
    raw = json.dumps([n["horario_utc"], n["latitude"], n["longitude"]])
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class DailyCache:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _path(self, person: str, day: date) -> Path:
        return self.root / person / f"{day.isoformat()}.json"

    def _read(self, path: Path) -> dict | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None

    def get(self, person: str, day: date, model: str, prompt_version: str) -> dict | None:
        rec = self._read(self._path(person, day))
        if rec and rec.get("model") == model and rec.get("prompt_version") == prompt_version and rec.get("message"):
            return rec
        return None

    def set(self, person: str, day: date, record: dict) -> Path:
        path = self._path(person, day)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        return path

    def recent(self, person: str, before: date, n: int = 2) -> list[dict]:
        """Registros dos dias anteriores a `before` (mais recente primeiro), para evitar repetição."""
        folder = self.root / person
        if not folder.is_dir():
            return []
        found = []
        for f in folder.glob("*.json"):
            try:
                d = date.fromisoformat(f.stem)
            except ValueError:
                continue
            rec = self._read(f)
            if d < before and rec and rec.get("message"):
                found.append((d, rec))
        return [r for _, r in sorted(found, key=lambda x: x[0], reverse=True)[:n]]
