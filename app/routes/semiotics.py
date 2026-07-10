"""
Fractal 2 — Camada Semântica (ARPIA)
/api/semiotics/interpret: traduz face_id em significado semiótico.
  IDs 1-51  → mapeamento estático (FACE_DICT embutido)
  IDs 52-200 → algoritmo bitwise + trigonométrico
"""
import math
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/semiotics", tags=["semiotics"])

# Subconjunto representativo — espelha FACE_DICT do meky_commander.py
STATIC_MAP: dict[int, dict] = {
    1:  {"nome": "ALERTA_BAIXO",     "eixo": "Alerta",      "hex": "#FF4400"},
    2:  {"nome": "CALMO",            "eixo": "Calma",        "hex": "#00CCFF"},
    3:  {"nome": "CURIOSO",          "eixo": "Curiosidade",  "hex": "#FFCC00"},
    4:  {"nome": "ALERTA_ALTO",      "eixo": "Alerta",       "hex": "#FF0000"},
    5:  {"nome": "ATENTO",           "eixo": "Atenção",      "hex": "#FF8800"},
    6:  {"nome": "CONCENTRADO",      "eixo": "Foco",         "hex": "#0088FF"},
    7:  {"nome": "ENTEDIADO",        "eixo": "Tédio",        "hex": "#888888"},
    8:  {"nome": "CURIOSIDADE_LEVE", "eixo": "Curiosidade",  "hex": "#FFDD44"},
    9:  {"nome": "FELIZ",            "eixo": "Alegria",      "hex": "#FFFF00"},
    10: {"nome": "ANIMADO",          "eixo": "Alegria",      "hex": "#FF88FF"},
    17: {"nome": "MEDO_LEVE",        "eixo": "Medo",         "hex": "#9900CC"},
    18: {"nome": "SURPRESA",         "eixo": "Surpresa",     "hex": "#00FFCC"},
    21: {"nome": "TRISTEZA_LEVE",    "eixo": "Tristeza",     "hex": "#0044AA"},
    22: {"nome": "TRISTEZA_MEDIA",   "eixo": "Tristeza",     "hex": "#002288"},
    23: {"nome": "TRISTEZA_FUNDA",   "eixo": "Tristeza",     "hex": "#001155"},
    24: {"nome": "RAIVA_LEVE",       "eixo": "Raiva",        "hex": "#FF2200"},
    25: {"nome": "RAIVA_MEDIA",      "eixo": "Raiva",        "hex": "#CC1100"},
    29: {"nome": "NOJO",             "eixo": "Nojo",         "hex": "#448800"},
    31: {"nome": "VERGONHA",         "eixo": "Vergonha",     "hex": "#FF4488"},
    32: {"nome": "CULPA",            "eixo": "Culpa",        "hex": "#774400"},
    40: {"nome": "AFEICAO",          "eixo": "Afeto",        "hex": "#FF88AA"},
    41: {"nome": "AMOR",             "eixo": "Afeto",        "hex": "#FF2255"},
    42: {"nome": "EMPATIA",          "eixo": "Empatia",      "hex": "#FF99CC"},
    47: {"nome": "VIGILANCIA",       "eixo": "Alerta",       "hex": "#FFAA00"},
    51: {"nome": "UNIAO",            "eixo": "Conexão",      "hex": "#FFFFFF"},
    75: {"nome": "SERENIDADE",       "eixo": "Paz",          "hex": "#88DDFF"},
    100:{"nome": "CONTEMPLACAO",     "eixo": "Introspecção", "hex": "#4444AA"},
    113:{"nome": "ACOLHIMENTO",      "eixo": "Cuidado",      "hex": "#FFBBAA"},
    150:{"nome": "TRANSCENDENCIA",   "eixo": "Espiritual",   "hex": "#DDAAFF"},
    200:{"nome": "VAZIO_PLENO",      "eixo": "Zen",          "hex": "#111111"},
}

EIXOS = [
    "Alerta", "Calma", "Curiosidade", "Alegria", "Tristeza",
    "Raiva", "Medo", "Afeto", "Empatia", "Foco",
    "Introspecção", "Paz", "Conexão", "Zen",
]

ATYPE_NAMES = ["breath", "rotate", "shimmer", "static", "blink", "rainbow"]


def _hue_to_hex(hue: int) -> str:
    """HSV(hue, 255, 200) → #RRGGBB aproximado."""
    h = (hue % 256) / 256.0
    i = int(h * 6)
    f = h * 6 - i
    v = 200
    p = int(v * 0)
    q = int(v * (1 - f))
    t = int(v * f)
    i %= 6
    rgb = [
        (v, t, p), (q, v, p), (p, v, t),
        (p, q, v), (t, p, v), (v, p, q),
    ][i]
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _interpret_parametric(face_id: int) -> dict:
    """
    Motor paramétrico — espelha _anim_parametrico() do firmware.
    atype  = face_id % 6
    hue    = (face_id * 7) % 256
    speed  = face_id % 5 + 2
    eixo   = EIXOS[(face_id * 3) % len(EIXOS)]   (distribuição por espectro)
    """
    atype  = face_id % 6
    hue    = (face_id * 7) % 256
    speed  = face_id % 5 + 2
    eixo   = EIXOS[(face_id * 3) % len(EIXOS)]
    hex_c  = _hue_to_hex(hue)

    # Intensidade emocional: combinação bitwise + trig (conforme spec fractal)
    intensity = abs(math.sin(face_id * math.pi / 17)) * 100
    complexity = bin(face_id).count("1")          # nº de bits 1 — "densidade do signo"
    harmonic   = round(math.cos(face_id / 13.0) * 50 + 50, 2)  # 0-100

    return {
        "face_id":   face_id,
        "tipo":      "parametrico",
        "eixo":      eixo,
        "atype":     atype,
        "atype_name": ATYPE_NAMES[atype],
        "hue":       hue,
        "speed":     speed,
        "hex":       hex_c,
        "intensity": round(intensity, 2),   # 0-100: quão intenso é o estado
        "complexity": complexity,           # bits 1: "peso semiótico"
        "harmonic":  harmonic,              # ressonância com estados vizinhos
        "sinsigno":  f"#FAC:{face_id}",
        "legisigno": f"atype={atype},eixo={eixo},rate_limit=10",
    }


@router.get("/interpret/{face_id}")
async def interpret(face_id: int):
    if face_id < 1 or face_id > 200:
        raise HTTPException(400, "face_id deve estar entre 1 e 200")

    if face_id in STATIC_MAP:
        s = STATIC_MAP[face_id]
        return {
            "face_id":   face_id,
            "tipo":      "estatico",
            "nome":      s["nome"],
            "eixo":      s["eixo"],
            "hex":       s["hex"],
            "sinsigno":  f"#FAC:{face_id}",
            "legisigno": f"eixo={s['eixo']},rate_limit=5",
            "qualisigno_desc": f"Estado puro de {s['eixo'].lower()} — {s['nome']}",
        }

    return _interpret_parametric(face_id)


@router.get("/spectrum")
async def spectrum(eixo: str | None = None):
    """Retorna todos os IDs 1-200 mapeados, opcionalmente filtrados por eixo."""
    results = []
    for fid in range(1, 201):
        if fid in STATIC_MAP:
            s = STATIC_MAP[fid]
            entry = {"face_id": fid, "tipo": "estatico", "eixo": s["eixo"],
                     "nome": s["nome"], "hex": s["hex"]}
        else:
            p = _interpret_parametric(fid)
            entry = {"face_id": fid, "tipo": "parametrico", "eixo": p["eixo"],
                     "nome": f"P-{fid}", "hex": p["hex"]}

        if eixo and entry["eixo"].lower() != eixo.lower():
            continue
        results.append(entry)
    return results
