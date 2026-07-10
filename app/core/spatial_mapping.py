"""
YardTopologyProcessor — Mapeamento Espacial do Quintal (Assembleia #402)
Parser de coordenadas 3D extraídas de metadados de vídeo do quintal da Sociedade Tucci.
Segmenta o ambiente em nós operacionais com eixos de fauna e zonas cronológicas.
"""
from dataclasses import dataclass, field
from typing import Optional
import time

# ── Eixos de Fauna ────────────────────────────────────────────────────────────
EIXO_AVES = {
    "nome": "EIXO_AVES",
    "altura_min_m": 2.0,
    "altura_max_m": 999.0,
    "espécies": ["Jacu", "Sabiá", "Bem-te-vi"],
    "desc": "Fauna de altura — voo e poleiros acima de 2 metros",
}

EIXO_SARUE = {
    "nome": "EIXO_SARUE",
    "altura_min_m": 0.0,
    "altura_max_m": 0.5,
    "fotoperíodo": "noturno",
    "espécies": ["Saruê", "Saruezão", "Saruezinho"],
    "desc": "Fauna terrestre noturna — ativa abaixo de 0.5m após escurecer",
}

NO_MEKY_ESTACIONARIO = {
    "nome": "NÓ_MEKY_ESTACIONÁRIO",
    "coordenadas_seguras": {"x": 0.0, "y": 0.0, "z": 0.0},
    "raio_m": 0.3,
    "desc": "Zona de parada segura do hexápode — ponto zero do sistema de coordenadas",
}

# ── Segmentação Cronológica do Vídeo de 4min20s (260s) ───────────────────────
SEGMENTOS_VIDEO = {
    "NÓ_INTERNO": {
        "t_inicio": 0,
        "t_fim": 45,
        "desc": "Núcleo interno — aquário 1m (lebistes/coridoras), nó de monitoramento estável",
        "limiar_fotoperíodo": True,
    },
    "NÓ_MESA_NASCIMENTO": {
        "t_inicio": 45,
        "t_fim": 135,
        "desc": "Mesa redonda de metal — berço da MC, suporte câmera para calha de penas de jacu",
        "coord_referencia": NO_MEKY_ESTACIONARIO["coordenadas_seguras"],
    },
    "NÓ_QUINTAL_ABERTO": {
        "t_inicio": 135,
        "t_fim": 225,
        "desc": "Piso de laota, frestas de tijolo retêm calor — microclima do Saruezão/Saruezinho",
        "eixo_fauna_ativo": EIXO_SARUE["nome"],
    },
    "NÓ_BARREIRA_COVARDE": {
        "t_inicio": 225,
        "t_fim": 260,
        "desc": "Perímetro como fortaleza lógica — isolamento geográfico @cão_covarde_shield",
        "isolamento": True,
    },
}


@dataclass
class Coordenada3D:
    x: float
    y: float
    z: float
    timestamp_s: float = 0.0
    confidence: float = 1.0

    @property
    def altura_m(self) -> float:
        return self.z

    @property
    def eixo_fauna(self) -> Optional[str]:
        if self.z >= EIXO_AVES["altura_min_m"]:
            return "EIXO_AVES"
        if self.z <= EIXO_SARUE["altura_max_m"]:
            return "EIXO_SARUE"
        return None

    @property
    def segmento_video(self) -> Optional[str]:
        for nome, seg in SEGMENTOS_VIDEO.items():
            if seg["t_inicio"] <= self.timestamp_s < seg["t_fim"]:
                return nome
        return None


@dataclass
class YardTopologyProcessor:
    """
    Processa coordenadas 3D extraídas de metadados de vídeo do quintal.
    Classifica cada ponto nos eixos de fauna e segmentos cronológicos.
    Mantém estado de isolamento: jamais expõe coordenadas absolutas.
    """
    _buffer: list[Coordenada3D] = field(default_factory=list)
    _last_processed: float = field(default_factory=time.time)

    def ingest(self, x: float, y: float, z: float,
               timestamp_s: float = 0.0, confidence: float = 1.0) -> Coordenada3D:
        """Ingere coordenada bruta e classifica."""
        coord = Coordenada3D(x=x, y=y, z=z,
                             timestamp_s=timestamp_s, confidence=confidence)
        self._buffer.append(coord)
        return coord

    def classify(self, coord: Coordenada3D) -> dict:
        """Retorna classificação completa de uma coordenada."""
        return {
            "vetor_relativo": {"x": coord.x, "y": coord.y, "z": coord.z},
            "eixo_fauna": coord.eixo_fauna,
            "segmento_video": coord.segmento_video,
            "confidence": coord.confidence,
            "no_meky_safe": (
                abs(coord.x) <= NO_MEKY_ESTACIONARIO["raio_m"]
                and abs(coord.y) <= NO_MEKY_ESTACIONARIO["raio_m"]
            ),
        }

    def snapshot(self) -> dict:
        """Estado atual: todos os pontos ingeridos, classificados por segmento."""
        result: dict[str, list] = {s: [] for s in SEGMENTOS_VIDEO}
        result["SEM_SEGMENTO"] = []
        for coord in self._buffer:
            seg = coord.segmento_video or "SEM_SEGMENTO"
            result[seg].append(self.classify(coord))
        return {
            "total_pontos": len(self._buffer),
            "segmentos": result,
            "eixos": {
                "EIXO_AVES": EIXO_AVES,
                "EIXO_SARUE": EIXO_SARUE,
                "NÓ_MEKY_ESTACIONÁRIO": NO_MEKY_ESTACIONARIO,
            },
        }

    def clear(self):
        self._buffer.clear()
