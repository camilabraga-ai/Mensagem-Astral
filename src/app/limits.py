"""Limite global de uso da API: vale para TODAS as sessões do mesmo servidor (o limite por sessão é contornável
recarregando a página). Contador em arquivo + memória; sem banco de dados e sem serviço externo.

Limites: mensagens novas por dia (fuso de São Paulo) e por hora corrida. Cache hit não conta. O pior gasto diário é
`max_daily` x custo por mensagem (~US$ 0,003 com o Haiku).

Limitação conhecida: o contador vive no disco do servidor. Se o servidor reiniciar em um ambiente de disco efêmero
(Streamlit Community Cloud), o contador do dia zera. Por isso o limite de gastos no console da Anthropic continua
sendo a proteção final (ver docs/etapa7_progresso.md).
"""
from __future__ import annotations

import json
import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

try:                                    # exclusão entre processos (POSIX); sem isso vale só entre threads
    import fcntl
except ImportError:                     # pragma: no cover
    fcntl = None

DEFAULT_MAX_DAILY = 40
DEFAULT_MAX_HOURLY = 12
HOUR = 3600.0

MESSAGES = {
    "off": "A geração de mensagens está temporariamente pausada. Volte mais tarde.",
    "day": "Hoje já foram geradas muitas mensagens e o limite diário foi atingido. Volte amanhã para receber a sua.",
    "hour": "Muitas pessoas estão pedindo mensagens agora. Tente de novo em alguns minutos.",
}


class LimitReached(Exception):
    """Limite global atingido. `reason`: 'off' (geração pausada), 'day' ou 'hour'."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def limit_message(reason: str) -> str:
    return MESSAGES.get(reason, MESSAGES["day"])


_THREAD_LOCK = threading.Lock()
_MEMORY: dict[tuple[str, str], list[float]] = {}    # (pasta, dia) -> instantes das gerações (reserva se o disco falhar)


class UsageLimiter:
    def __init__(self, root: str | Path, max_daily: int = DEFAULT_MAX_DAILY, max_hourly: int = DEFAULT_MAX_HOURLY,
                 enabled: bool = True, tz: str = "America/Sao_Paulo", clock=time.time):
        self.root, self.max_daily, self.max_hourly = Path(root), int(max_daily), int(max_hourly)
        self.enabled, self.tz, self.clock = enabled, tz, clock

    # -- armazenamento ----------------------------------------------------------------------------------
    def _day(self, now: float) -> str:
        return datetime.fromtimestamp(now, ZoneInfo(self.tz)).date().isoformat()

    def _path(self, day: str) -> Path:
        return self.root / f"uso-{day}.json"

    @contextmanager
    def _exclusive(self):
        with _THREAD_LOCK:
            handle = None
            if fcntl is not None:
                try:
                    self.root.mkdir(parents=True, exist_ok=True)
                    handle = open(self.root / "uso.lock", "w")
                    fcntl.flock(handle, fcntl.LOCK_EX)
                except OSError:
                    handle = None
            try:
                yield
            finally:
                if handle is not None:
                    handle.close()          # fecha e libera o flock

    def _load(self, day: str) -> list[float]:
        """Instantes do dia. Usa o maior entre o arquivo e a memória: nunca subestima o uso."""
        memoria = list(_MEMORY.get((str(self.root), day), []))
        try:
            dados = json.loads(self._path(day).read_text(encoding="utf-8"))
            arquivo = [float(x) for x in dados.get("stamps", [])]
        except (FileNotFoundError, ValueError, TypeError, AttributeError, OSError):
            arquivo = []
        return arquivo if len(arquivo) >= len(memoria) else memoria

    def _save(self, day: str, stamps: list[float]) -> None:
        _MEMORY[(str(self.root), day)] = stamps
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            tmp = self._path(day).with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
            tmp.write_text(json.dumps({"stamps": stamps}), encoding="utf-8")
            os.replace(tmp, self._path(day))
        except OSError:
            pass                            # sem disco: o contador em memória continua valendo

    # -- regras -----------------------------------------------------------------------------------------
    def _reason(self, stamps: list[float], now: float) -> str | None:
        if not self.enabled:
            return "off"
        if len(stamps) >= self.max_daily:
            return "day"
        if sum(1 for s in stamps if s > now - HOUR) >= self.max_hourly:
            return "hour"
        return None

    def check(self) -> str | None:
        """None se ainda há folga; senão 'off', 'day' ou 'hour'. Não reserva nada."""
        now = self.clock()
        with self._exclusive():
            return self._reason(self._load(self._day(now)), now)

    def acquire(self) -> None:
        """Reserva UMA geração (conta mesmo que a chamada falhe depois: é a postura mais segura para o custo)."""
        now = self.clock()
        day = self._day(now)
        with self._exclusive():
            stamps = self._load(day)
            reason = self._reason(stamps, now)
            if reason:
                raise LimitReached(reason)
            self._save(day, stamps + [now])

    def snapshot(self) -> dict:
        now = self.clock()
        with self._exclusive():
            stamps = self._load(self._day(now))
        return {"hoje": len(stamps), "ultima_hora": sum(1 for s in stamps if s > now - HOUR),
                "max_dia": self.max_daily, "max_hora": self.max_hourly, "ativo": self.enabled}
