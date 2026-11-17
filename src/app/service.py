"""Serviços da interface: cache em disco, chave da API, mapa natal, mensagem do dia e erros amigáveis."""
from __future__ import annotations

import os
import threading
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from src.astrology.chart import BirthData, calculate_chart
from src.common.env import REPO_ROOT
from src.data.kb import KnowledgeBase
from src.rag.generator import DEFAULT_MODEL, AnthropicLLM, LLMError
from src.transits.cache import DailyCache
from src.transits.daily import DailyMessage, daily_message
from src.app.geo import Place
from src.app.limits import (DEFAULT_MAX_DAILY, DEFAULT_MAX_HOURLY, LimitReached, UsageLimiter,  # noqa: F401
                            limit_message)
from src.transits.cache import person_key
from src.app.validation import check_local_time, fixed_offset_tz

MAX_GENERATIONS_PER_SESSION = 3
DISPLAY_TZ = "America/Sao_Paulo"


class CacheMiss(Exception):
    pass


class _CacheOnlyLLM:
    """LLM que nunca chama a API: se for acionado, é porque não havia mensagem em cache."""

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model

    def complete(self, system: str, user: str) -> str:
        raise CacheMiss()


def cache_dir() -> Path:
    return Path(os.environ.get("MENSAGEM_ASTRAL_CACHE_DIR") or REPO_ROOT / ".cache" / "mensagens")


def usage_dir() -> Path:
    return Path(os.environ.get("MENSAGEM_ASTRAL_USAGE_DIR") or cache_dir().parent / "uso")


def read_setting(name: str, secrets=None, default=None):
    """Configuração: variável de ambiente ou Secrets do Streamlit (o ambiente tem prioridade)."""
    value = os.environ.get(name)
    if value in (None, "") and secrets is not None:
        try:
            value = secrets.get(name)
        except Exception:
            value = None
    return default if value in (None, "") else value


def _as_int(value, default: int) -> int:
    try:
        n = int(str(value).strip())
        return n if n >= 0 else default
    except (TypeError, ValueError):
        return default


def usage_limiter(secrets=None) -> UsageLimiter:
    """Limite global de gerações. Ajustável por Secrets/ambiente: MAX_DAILY_GENERATIONS, MAX_HOURLY_GENERATIONS e
    GENERATION_ENABLED (false pausa toda geração nova, útil como chave de emergência)."""
    enabled = str(read_setting("GENERATION_ENABLED", secrets, "true")).strip().lower() not in \
        {"0", "false", "no", "off", "nao", "não"}
    return UsageLimiter(usage_dir(),
                        _as_int(read_setting("MAX_DAILY_GENERATIONS", secrets), DEFAULT_MAX_DAILY),
                        _as_int(read_setting("MAX_HOURLY_GENERATIONS", secrets), DEFAULT_MAX_HOURLY),
                        enabled=enabled)


def apply_secret_settings(secrets=None) -> None:
    """Leva ao ambiente o que o cache precisa (o sal do código de pessoa), venha dos Secrets ou do ambiente."""
    salt = read_setting("CACHE_SALT", secrets) or read_setting("MENSAGEM_ASTRAL_CACHE_SALT", secrets)
    if salt:
        os.environ["MENSAGEM_ASTRAL_CACHE_SALT"] = str(salt)


def get_api_key(secrets=None) -> str | None:
    """Chave da Anthropic: variável de ambiente ou Secrets do Streamlit. Nunca é exibida nem registrada."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key and secrets is not None:
        try:
            key = secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            key = None
    return key or None


def build_llm(api_key: str) -> AnthropicLLM:
    import anthropic
    # timeout curto: a tela nunca fica presa esperando a API (o SDK ainda tenta 2 vezes em falhas de rede)
    return AnthropicLLM(model=DEFAULT_MODEL, client=anthropic.Anthropic(api_key=api_key, timeout=60.0, max_retries=2))


def today_local() -> date:
    return datetime.now(ZoneInfo(DISPLAY_TZ)).date()


def birth_in_future(place: Place, data: date, hora: time, now: datetime | None = None) -> bool:
    """True se o instante de nascimento (no fuso do local) ainda não aconteceu."""
    local = datetime.combine(data, hora.replace(second=0, microsecond=0)).replace(tzinfo=ZoneInfo(place.tz))
    return local.astimezone(timezone.utc) > (now or datetime.now(timezone.utc))


def load_kb() -> KnowledgeBase:
    return KnowledgeBase.load(REPO_ROOT / "kb")


def build_chart(place: Place, data: date, hora: time, offset_hours: float | None = None) -> dict:
    """Mapa natal pelo motor existente. Se a pessoa escolheu uma das duas leituras de um horário ambíguo,
    usa-se um fuso fixo com o deslocamento escolhido (o motor não aceita esse caso diretamente)."""
    tz = place.tz
    if offset_hours is not None:
        tz = fixed_offset_tz(offset_hours)
    elif (st := check_local_time(data, hora, tz).status) != "ok":
        raise ValueError(f"horário local {st}")
    return calculate_chart(BirthData(data.year, data.month, data.day, hora.hour, hora.minute,
                                     place.label.split(",")[0], "", lat=place.lat, lng=place.lng, tz_str=tz))


def cached_message(kb: KnowledgeBase, chart: dict, day: date, cache: DailyCache,
                   model: str = DEFAULT_MODEL) -> DailyMessage | None:
    """Mensagem já guardada para esta pessoa e dia, ou None. Nunca chama a API."""
    try:
        return daily_message(kb, chart, day, _CacheOnlyLLM(model), cache)
    except CacheMiss:
        return None


_KEY_LOCKS: dict[tuple[str, str], threading.Lock] = {}
_KEY_LOCKS_GUARD = threading.Lock()


def _key_lock(person: str, day: date) -> threading.Lock:
    with _KEY_LOCKS_GUARD:
        return _KEY_LOCKS.setdefault((person, day.isoformat()), threading.Lock())


def generate_message(kb: KnowledgeBase, chart: dict, day: date, llm, cache: DailyCache,
                     limiter: UsageLimiter | None = None) -> DailyMessage:
    """Gera (UMA chamada paga) e guarda no cache. Só deve ser chamada após ação explícita da pessoa.

    Duas sessões pedindo a MESMA pessoa/dia ao mesmo tempo não pagam duas vezes: a segunda espera e lê o cache.
    Com `limiter`, a geração nova reserva uma vaga no limite global; sem vaga, levanta LimitReached (sem chamada).
    """
    with _key_lock(person_key(chart), day):
        hit = cached_message(kb, chart, day, cache, getattr(llm, "model", DEFAULT_MODEL))
        if hit is not None:
            return hit
        if limiter is not None:
            limiter.acquire()
        return daily_message(kb, chart, day, llm, cache)


def friendly_error(exc: Exception) -> str:
    """Mensagem em português para erros da API ou do pipeline (sem detalhes técnicos nem chaves)."""
    name = type(exc).__name__
    if isinstance(exc, LLMError):
        return "Não foi possível gerar a mensagem de hoje. Tente novamente em instantes."
    if name == "AuthenticationError":
        return "A chave de acesso ao modelo é inválida. Verifique a configuração do aplicativo."
    if name == "RateLimitError":
        return "O serviço está com muitas solicitações no momento. Tente novamente em alguns minutos."
    if name in ("APIConnectionError", "APITimeoutError"):
        return "Não foi possível conectar ao serviço de geração. Verifique a conexão e tente novamente."
    if name in ("PermissionDeniedError", "BadRequestError") or "credit" in str(exc).lower():
        return "O serviço de geração está indisponível no momento. Tente novamente mais tarde."
    return "Algo deu errado ao gerar a mensagem. Tente novamente em instantes."
