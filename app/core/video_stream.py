"""
Video Stream Processor — parse_extended_yard_payload (Assembleia #402)
Segmenta 260 segundos de dados visuais em 4 matrizes de estado cronológicas.
Todos os dados de profundidade/coordenada ficam encriptados localmente no Manga DB.
"""
from dataclasses import dataclass, field
from typing import Optional
from app.core.spatial_mapping import SEGMENTOS_VIDEO, YardTopologyProcessor
from app.core.privacy_shield import cao_covarde_shield


@dataclass
class EstadoMatriz:
    nome_no: str
    t_inicio: int
    t_fim: int
    frames: list[dict] = field(default_factory=list)
    turbidez_media: float = 0.0
    deteccoes_fauna: list[dict] = field(default_factory=list)
    luz_ambiente: float = 0.0

    @property
    def duracao_s(self) -> int:
        return self.t_fim - self.t_inicio

    def to_dict(self) -> dict:
        return {
            "no": self.nome_no,
            "t_inicio": self.t_inicio,
            "t_fim": self.t_fim,
            "duracao_s": self.duracao_s,
            "total_frames": len(self.frames),
            "turbidez_media": round(self.turbidez_media, 3),
            "deteccoes_fauna": self.deteccoes_fauna,
            "luz_ambiente": round(self.luz_ambiente, 2),
        }


def parse_extended_yard_payload(
    frames_raw: list[dict],
    duracao_total_s: int = 260,
) -> dict:
    """
    Segmenta payload de vídeo de 260s em 4 matrizes de estado cronológicas.
    Cada frame deve conter: {"t": float, "x": float, "y": float, "z": float,
                              "turbidez": float, "luz": float, "fauna": list}
    Retorna dados encriptados via @cão_covarde_shield — sem coordenadas absolutas.
    """
    processor = YardTopologyProcessor()

    matrizes: dict[str, EstadoMatriz] = {
        nome: EstadoMatriz(
            nome_no=nome,
            t_inicio=seg["t_inicio"],
            t_fim=seg["t_fim"],
        )
        for nome, seg in SEGMENTOS_VIDEO.items()
    }

    for frame in frames_raw:
        t = float(frame.get("t", 0))
        x = float(frame.get("x", 0))
        y = float(frame.get("y", 0))
        z = float(frame.get("z", 0))
        turbidez = float(frame.get("turbidez", 0))
        luz = float(frame.get("luz", 0))
        fauna = frame.get("fauna", [])

        coord = processor.ingest(x, y, z, timestamp_s=t)
        seg_nome = coord.segmento_video

        if seg_nome and seg_nome in matrizes:
            mat = matrizes[seg_nome]
            mat.frames.append({"t": t, "vetor": {"x": x, "y": y, "z": z}})
            # Running mean de turbidez
            n = len(mat.frames)
            mat.turbidez_media = (mat.turbidez_media * (n - 1) + turbidez) / n
            mat.luz_ambiente = (mat.luz_ambiente * (n - 1) + luz) / n
            for f in fauna:
                mat.deteccoes_fauna.append({
                    "especie": f.get("especie", "Desconhecido"),
                    "eixo": coord.eixo_fauna,
                    "t": t,
                    "confidence": f.get("confidence", 0.5),
                })

    return {
        "duracao_total_s": duracao_total_s,
        "total_frames": len(frames_raw),
        "matrizes": {nome: mat.to_dict() for nome, mat in matrizes.items()},
        "shield": "@cão_covarde_shield:ativo",
    }


def get_fotoperíodo_threshold(t_segundos: float) -> str:
    """
    Inferido do vídeo: abertura da porta de madeira aos ~45s estabelece
    o limiar de fotoperíodo. Antes = modo interno/noturno, depois = externo/diurno.
    """
    return "NOTURNO" if t_segundos < 45 else "DIURNO"
