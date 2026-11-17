"""Validação dos dados do formulário e do horário local (horário de verão)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

MIN_DATE = date(1900, 1, 1)


def validate_form(nome: str | None, data: date | None, hora: time | None, cidade: str, pais: str,
                  today: date | None = None) -> list[str]:
    """Lista de mensagens de erro em português (vazia = dados válidos)."""
    today = today or date.today()
    erros = []
    if data is None:
        erros.append("Informe a data de nascimento.")
    elif data > today:
        erros.append("A data de nascimento não pode estar no futuro.")
    elif data < MIN_DATE:
        erros.append("Informe uma data a partir de 1900.")
    if hora is None:
        erros.append("Informe o horário de nascimento (o Ascendente depende dele).")
    if not (cidade or "").strip():
        erros.append("Informe a cidade de nascimento.")
    elif len(cidade.strip()) < 2:
        erros.append("O nome da cidade parece curto demais.")
    if not (pais or "").strip():
        erros.append("Informe o país de nascimento.")
    if nome and len(nome.strip()) > 60:
        erros.append("O nome pode ter no máximo 60 caracteres.")
    return erros


@dataclass(frozen=True)
class LocalTimeCheck:
    status: str                                  # "ok" | "nonexistent" | "ambiguous"
    offsets_hours: tuple[float, ...] = ()        # ambíguo: (verão, padrão), em horas

    def message(self) -> str:
        if self.status == "nonexistent":
            return ("Esse horário não existiu nessa cidade: o relógio foi adiantado na mudança para o horário de "
                    "verão. Confira o horário de nascimento.")
        if self.status == "ambiguous":
            return "Esse horário aconteceu duas vezes nessa cidade (fim do horário de verão). Escolha qual vale."
        return ""


def check_local_time(data: date, hora: time, tz_name: str) -> LocalTimeCheck:
    """Detecta horário inexistente (relógio adiantado) ou ambíguo (relógio atrasado) no fuso informado."""
    tz = ZoneInfo(tz_name)
    naive = datetime.combine(data, hora.replace(second=0, microsecond=0))
    a0, a1 = naive.replace(tzinfo=tz, fold=0), naive.replace(tzinfo=tz, fold=1)
    if a0.utcoffset() == a1.utcoffset():
        return LocalTimeCheck("ok")
    valid0 = a0.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None) == naive
    if not valid0:
        return LocalTimeCheck("nonexistent")
    horas = sorted((a0.utcoffset().total_seconds() / 3600, a1.utcoffset().total_seconds() / 3600), reverse=True)
    return LocalTimeCheck("ambiguous", tuple(horas))


def fixed_offset_tz(hours: float) -> str:
    """Nome IANA de fuso fixo para um deslocamento em horas (ex.: -3 -> 'Etc/GMT+3'; sinal invertido por convenção)."""
    if hours != int(hours):
        raise ValueError("Fuso com deslocamento fracionado não é suportado para horário ambíguo.")
    h = int(hours)
    if h == 0:
        return "Etc/GMT"
    return f"Etc/GMT{'+' if h < 0 else '-'}{abs(h)}"
