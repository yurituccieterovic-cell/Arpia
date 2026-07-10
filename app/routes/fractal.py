"""
Fractal 7 — Ecossistema e Síntese Coletiva

GET /api/fractal             — hierarquia fractal completa (todas as 7 camadas)
GET /api/fractal/{layer}     — camada específica
GET /api/fractal/summary     — resumo compacto para widgets
"""
from fastapi import APIRouter, HTTPException
from app.core.fractal import build_fractal, get_layer, LAYER_7_ECOSSISTEMA

router = APIRouter(prefix="/api/fractal", tags=["fractal"])


@router.get("")
async def fractal_completo():
    """Retorna a hierarquia fractal auto-replicante completa."""
    return build_fractal()


@router.get("/summary")
async def fractal_summary():
    """Resumo compacto — para widgets de frontend."""
    f = build_fractal()
    return {
        "nome": f["nome"],
        "versao": f["versao"],
        "total_camadas": f["total_camadas"],
        "total_nos": f["total_nos"],
        "camadas": [
            {
                "layer":      c["layer"],
                "nome":       c["nome"],
                "subsistema": c["subsistema"],
                "n_nos":      len(c["nodes"]),
                "api_routes": c["api_routes"][:2],  # primeiras 2 rotas
            }
            for c in f["camadas"]
        ],
    }


@router.get("/{layer_num}")
async def fractal_layer(layer_num: int):
    """Retorna uma camada específica do fractal (1-7)."""
    if layer_num < 1 or layer_num > 7:
        raise HTTPException(400, "Camada deve ser entre 1 e 7.")
    layer = get_layer(layer_num)
    if not layer:
        raise HTTPException(404, f"Camada {layer_num} não encontrada.")
    return layer
