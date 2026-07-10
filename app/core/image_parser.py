"""
Image Parser — validate_tile_resolution (Assembleia #403)
Valida e processa tiles de mapa 300×300px para o sistema eco do MC.
Cada tile processado recebe flag processed:true e é salvo em /assets/map_tiles/.
"""
import io
import os
import hashlib
from pathlib import Path
from typing import Optional

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

TILE_SIZE = (300, 300)
ASSETS_DIR = Path("assets/map_tiles")
ASSETS_DIR.mkdir(parents=True, exist_ok=True)


class TileValidationError(Exception):
    pass


def validate_tile_resolution(
    image_data: bytes,
    filename: str,
    force_resize: bool = True,
) -> dict:
    """
    Valida que o tile tem resolução 300×300px.
    Se force_resize=True, redimensiona via Pillow e salva.
    Retorna metadados do tile com flag processed:true.
    """
    if not PIL_AVAILABLE:
        raise TileValidationError("Pillow não instalado — pip install Pillow")

    img = Image.open(io.BytesIO(image_data))
    original_size = img.size
    needs_resize = img.size != TILE_SIZE

    if needs_resize:
        if not force_resize:
            raise TileValidationError(
                f"Tile {filename} tem {img.size} — esperado {TILE_SIZE}"
            )
        img = img.resize(TILE_SIZE, Image.LANCZOS)

    stem = Path(filename).stem
    suffix = Path(filename).suffix or ".png"
    out_path = ASSETS_DIR / f"{stem}_300x300{suffix}"

    buf = io.BytesIO()
    fmt = "PNG" if suffix.lower() in (".png", "") else "JPEG"
    img.save(buf, format=fmt, optimize=True)
    processed_bytes = buf.getvalue()

    out_path.write_bytes(processed_bytes)
    content_hash = hashlib.sha256(processed_bytes).hexdigest()

    return {
        "filename": out_path.name,
        "path": str(out_path),
        "original_size": original_size,
        "final_size": TILE_SIZE,
        "resized": needs_resize,
        "processed": True,
        "format": fmt,
        "size_bytes": len(processed_bytes),
        "sha256": content_hash,
    }


def process_tile_batch(tiles: list[dict]) -> list[dict]:
    """
    Processa uma lista de tiles {filename, data_bytes}.
    Retorna lista de metadados. Tiles inválidos ficam com processed:false.
    """
    results = []
    for tile in tiles:
        try:
            meta = validate_tile_resolution(
                tile["data_bytes"], tile["filename"]
            )
            results.append(meta)
        except (TileValidationError, Exception) as e:
            results.append({
                "filename": tile.get("filename", "unknown"),
                "processed": False,
                "error": str(e),
            })
    return results
