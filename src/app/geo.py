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


def search_places(city: str, country: str, limit: int = 5, timeout: int = 8) -> list[Place]:
    from geopy.exc import GeopyError
    from geopy.geocoders import Nominatim
    from timezonefinder import TimezoneFinder

    query = f"{city.strip()}, {country.strip()}"
    try:
        found = Nominatim(user_agent="mensagem-astral-app").geocode(
            query, exactly_one=False, limit=limit, timeout=timeout, language="pt")
    except GeopyError as e:
        raise GeoError("Não foi possível consultar o serviço de localização agora. "
                       "Tente novamente em instantes.") from e
    if not found:
        raise GeoError(f"Não encontramos '{city.strip()}' em {country.strip()}. "
                       "Confira a grafia e, se quiser, acrescente o estado (ex.: Alfenas, MG).")
    tf, places, seen = TimezoneFinder(), [], set()
    for loc in found:
        tz = tf.timezone_at(lat=loc.latitude, lng=loc.longitude)
        if tz is None or loc.address in seen:
            continue
        seen.add(loc.address)
        places.append(Place(loc.address, round(loc.latitude, 4), round(loc.longitude, 4), tz))
    if not places:
        raise GeoError("Não foi possível determinar o fuso horário desse local.")
    return places
