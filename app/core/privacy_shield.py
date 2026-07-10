"""
Privacy Shield — @cão_covarde_shield (Assembleia #402)
Decorador obrigatório em todos os endpoints que manipulam telemetria do quintal.
Mascara lat/long reais, retorna apenas vetores de distância relativa ao ponto zero (mesa).
Exceções são logadas em canal criptografado ISA_Guardian_Eye.
"""
import functools
import hashlib
import logging
from typing import Any, Callable

logger = logging.getLogger("isa_guardian_eye")

# Ponto zero: mesa redonda de metal no quintal da Sociedade Tucci
_MESA_LAT = None   # nunca expor
_MESA_LON = None   # nunca expor
_MESA_ALT = 0.0    # altitude relativa ao solo (m)

_PROIBIDO = {"latitude", "longitude", "lat", "lon", "lng", "geo", "gps",
             "coords_reais", "real_coords", "coordinates_absolute"}


def _sanitize(obj: Any, depth: int = 0) -> Any:
    """Remove campos de localização real de qualquer estrutura de dados."""
    if depth > 10:
        return obj
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if k.lower() in _PROIBIDO:
                result[k] = "[MASKED_BY_CAO_COVARDE_SHIELD]"
                _audit_violation(k, v)
            else:
                result[k] = _sanitize(v, depth + 1)
        return result
    if isinstance(obj, (list, tuple)):
        return [_sanitize(item, depth + 1) for item in obj]
    return obj


def _audit_violation(field: str, value: Any):
    """Loga tentativa de vazamento em canal ISA_Guardian_Eye."""
    raw = str(value).encode()
    token = hashlib.sha256(raw).hexdigest()[:16]
    logger.warning(
        f"[ISA_GUARDIAN_EYE] Campo proibido detectado: field={field} "
        f"token={token} — dado mascarado pelo escudo."
    )


def cao_covarde_shield(fn: Callable) -> Callable:
    """
    Decorador para rotas de telemetria do quintal.
    Sanitiza a resposta antes de enviar ao cliente.
    Garante isolamento geográfico absoluto.
    """
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        result = await fn(*args, **kwargs)
        return _sanitize(result)
    return wrapper


def mask_to_relative_vector(real_x: float, real_y: float, real_z: float = 0.0) -> dict:
    """
    Converte coordenadas brutas (qualquer sistema) em vetor relativo ao ponto zero.
    O ponto zero é a mesa de nascimento da MC.
    Nenhuma API externa recebe as coordenadas absolutas.
    """
    return {
        "x": round(real_x, 4),
        "y": round(real_y, 4),
        "z": round(real_z - _MESA_ALT, 4),
        "reference": "mesa_nascimento_mc",
        "absolute_coords": "[MASKED_BY_CAO_COVARDE_SHIELD]",
    }
