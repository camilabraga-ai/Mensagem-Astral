"""Busca de cidades: candidatos com latitude, longitude e fuso, com timeout e erros em português."""
from __future__ import annotations

from dataclasses import dataclass


class GeoError(RuntimeError):
    """Erro de localização com mensagem pronta para a pessoa usuária."""


@dataclass(frozen=True)
class Place:
    label: str
    lat: float
    lng: float
    tz: str


_SETTLEMENTS = {"city", "town", "village", "municipality", "hamlet", "suburb", "city_district", "borough", "locality"}


def _label(loc) -> str:
    """'Cidade, Estado, País' a partir dos detalhes do endereço (o rótulo padrão do serviço traz regiões confusas)."""
    raw = getattr(loc, "raw", None) or {}
    addr = raw.get("address") or {}
    nome = raw.get("name") or addr.get("city") or addr.get("town") or addr.get("municipality") or addr.get("village")
    partes = [nome, addr.get("state"), addr.get("country")]
    partes = [p for p in partes if p]
    return ", ".join(partes) if len(partes) >= 2 else loc.address


def search_places(city: str, country: str, limit: int = 5, timeout: int = 8) -> list[Place]:
    from geopy.exc import GeopyError
    from geopy.geocoders import Nominatim
    from timezonefinder import TimezoneFinder

    query = f"{city.strip()}, {country.strip()}"
    try:
        found = Nominatim(user_agent="mensagem-astral-app").geocode(
            query, exactly_one=False, limit=limit, timeout=timeout, language="pt", addressdetails=True)
    except GeopyError as e:
        raise GeoError("Não foi possível consultar o serviço de localização agora. "
                       "Tente novamente em instantes.") from e
    if not found:
        raise GeoError(f"Não encontramos '{city.strip()}' em {country.strip()}. "
                       "Confira a grafia e, se quiser, acrescente o estado (ex.: Alfenas, MG).")
    # prefere localidades (cidade, vila...) a estados, condados e regiões; se não houver nenhuma, usa o que veio
    localidades = [x for x in found if (getattr(x, "raw", None) or {}).get("addresstype") in _SETTLEMENTS]
    tf, places, seen = TimezoneFinder(), [], set()
    for loc in (localidades or found):
        tz = tf.timezone_at(lat=loc.latitude, lng=loc.longitude)
        label = _label(loc)
        chave = (label, round(loc.latitude, 2), round(loc.longitude, 2))
        if tz is None or chave in seen:
            continue
        seen.add(chave)
        places.append(Place(label, round(loc.latitude, 4), round(loc.longitude, 4), tz))
    if not places:
        raise GeoError("Não foi possível determinar o fuso horário desse local.")
    return places
