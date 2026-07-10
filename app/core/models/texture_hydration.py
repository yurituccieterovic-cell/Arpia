# app/core/models/texture_hydration.py
# Mandatado pela Assembleia #414 — TextureHydration
# O físico reintroduzido como constraint operacional, não decoração
# Metadados sensoriais estendidos no Manga DB: temperatura, pH, lux, umidade

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


TEXTURE_COLOR_MAP = {
    "RICH_DEEP_PURPLE": "#4B0082",
    "PEARL_WHITE": "#F8F0E3",
    "CRIMSON_RED": "#DC143C",
    "AZUL_PETROLEO": "#008080",
    "NEON_VERDE": "#39FF14",
    "FIBRA_CARBONO": "#1C1C1E",
}


@dataclass
class TextureMetadata:
    """
    Metadados sensoriais estendidos para nós do Manga DB.
    Temperatura, pH, lux e umidade são constraints operacionais —
    se fora do range, o nó não pode operar em Modo Bebê_Clean.
    """
    node_id: str
    temperatura_c: Optional[float] = None
    ph: Optional[float] = None
    lux: Optional[float] = None
    umidade_pct: Optional[float] = None
    texture_color: Optional[str] = None
    texture_label: Optional[str] = None
    raw_sensorial: Optional[dict] = field(default_factory=dict)
    ts: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    def resolve_color_hex(self) -> Optional[str]:
        if self.texture_color:
            return TEXTURE_COLOR_MAP.get(self.texture_color.upper().replace(" ", "_"))
        return None

    def validate_operational(self) -> dict:
        """
        Valida se os sensores físicos estão dentro dos ranges operacionais.
        Fora do range = nó não pode operar. O físico é constraint, não decoração.
        """
        issues = []
        if self.temperatura_c is not None and not (15.0 <= self.temperatura_c <= 35.0):
            issues.append(f"temperatura fora do range: {self.temperatura_c}°C")
        if self.ph is not None and not (6.0 <= self.ph <= 8.5):
            issues.append(f"pH fora do range: {self.ph}")
        if self.lux is not None and not (5.0 <= self.lux <= 10000.0):
            issues.append(f"lux fora do range: {self.lux}")
        if self.umidade_pct is not None and not (20.0 <= self.umidade_pct <= 95.0):
            issues.append(f"umidade fora do range: {self.umidade_pct}%")

        return {
            "operational": len(issues) == 0,
            "issues": issues,
            "node_id": self.node_id,
            "ts": self.ts
        }


def hydrate_node(node_id: str, sensor_data: dict) -> TextureMetadata:
    """
    Converte dados brutos do sensor em TextureMetadata estruturado.
    Ponto de entrada para ingestão de textura física no Manga DB.
    """
    return TextureMetadata(
        node_id=node_id,
        temperatura_c=sensor_data.get("temperatura_c"),
        ph=sensor_data.get("ph"),
        lux=sensor_data.get("lux"),
        umidade_pct=sensor_data.get("umidade_pct"),
        texture_color=sensor_data.get("texture_color"),
        texture_label=sensor_data.get("texture_label"),
        raw_sensorial={k: v for k, v in sensor_data.items()
                       if k not in ("temperatura_c", "ph", "lux", "umidade_pct",
                                    "texture_color", "texture_label")}
    )
