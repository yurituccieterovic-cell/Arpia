"""
MEKY Gait Generator — Ponte Amanda↔Hardware (Sessões #564/#565, corr. #566)

Princípio: criar a ponte mesmo se a interface física ainda não existe.
Quando o escorpião hardware chegar, este módulo já sabe conversar com ele.

CORREÇÃO #566: MEKY é um QUADRÚPEDE (4 patas), NÃO hexápode.
  Firmware: RegisHsu Arduino Spider Robot (12 servos, 4 patas × 3 servos)
  Pins: {2,3,4}, {5,6,7}, {8,9,10}, {11,12,13}
  Serial: 115200 baud
  Protocolo serial direto: ver meky_scorpio_bridge.py

Gaits aqui são abstrações para FIRMWARE CUSTOMIZADO FUTURO.
Para controle imediato do firmware RegisHsu: usar MekyScorpioBridge.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import json
import asyncio


# ── Parâmetros canônicos ──────────────────────────────────────────────────────

@dataclass
class GaitSpec:
    """
    6 parâmetros que definem qualquer marcha quadrúpede.
    phase_offset: 4 elementos (uma fase por pata) — MEKY tem 4 patas.
    Ordem das patas: [LF, RF, LB, RB] (esquerda-frente, direita-frente, esq-trás, dir-trás)
    """
    name: str
    phase_offset: list[float]   # fases relativas de cada pata (0.0–1.0), len=4
    duty_cycle: float           # razão tempo-apoio/período (0.0–1.0)
    step_amplitude_mm: float    # altura máxima do passo em mm
    freq_hz: float              # frequência do ciclo completo
    body_height_mm: float       # altura do chassi acima do solo
    sync_pattern: str           # "trot" | "walk" | "pace" | "lateral" | "pivot"
    terrain: str = "plano"
    risk: str = "baixo"
    bio_inspiration: str = ""
    notes: str = ""


# ── 5 Gaits Canônicos (Quadrúpede — corr. #566) ─────────────────────────────
# Ordem patas: [LF, RF, LB, RB]

GAITS: dict[str, GaitSpec] = {

    "trot": GaitSpec(
        name="Trote Diagonal",
        phase_offset=[0.0, 0.5, 0.5, 0.0],  # LF+RB juntas; RF+LB juntas
        duty_cycle=0.5,
        step_amplitude_mm=30.0,
        freq_hz=1.5,
        body_height_mm=60.0,
        sync_pattern="trot",
        terrain="plano",
        risk="baixo",
        bio_inspiration="Cão, cavalo (pares diagonais sincronizados)",
        notes="Velocidade máxima em piso plano. Estabilidade estática garantida por pares diagonais.",
    ),

    "walk": GaitSpec(
        name="Caminhada Sequencial",
        phase_offset=[0.0, 0.25, 0.5, 0.75],  # cada pata 90° defasada
        duty_cycle=0.75,
        step_amplitude_mm=25.0,
        freq_hz=0.8,
        body_height_mm=50.0,
        sync_pattern="walk",
        terrain="irregular",
        risk="baixo",
        bio_inspiration="Lagarto (Lacertidae), tartaruga — pata por pata",
        notes="Terreno irregular; máxima estabilidade. Sempre 3 patas no chão.",
    ),

    "ripple": GaitSpec(
        name="Ripple — Onda Alternada",
        phase_offset=[0.0, 0.5, 0.33, 0.83],  # 2 patas no ar em sequência cruzada
        duty_cycle=0.67,
        step_amplitude_mm=28.0,
        freq_hz=1.0,
        body_height_mm=55.0,
        sync_pattern="ripple",
        terrain="semi-irregular",
        risk="baixo",
        bio_inspiration="Gato em terreno irregular (adaptação de 4 patas)",
        notes="Equilíbrio entre velocidade e estabilidade. 2 patas no ar com overlap.",
    ),

    "side_step": GaitSpec(
        name="Passo Lateral",
        phase_offset=[0.0, 0.5, 0.0, 0.5],  # pares laterais: LF+LB vs RF+RB
        duty_cycle=0.5,
        step_amplitude_mm=20.0,
        freq_hz=1.2,
        body_height_mm=60.0,
        sync_pattern="lateral",
        terrain="plano",
        risk="baixo",
        bio_inspiration="Siri (Ocypode), aranha-caranguejo (Thomisidae)",
        notes="Deslocamento 100% lateral sem rotação do chassi.",
    ),

    "pivot": GaitSpec(
        name="Giro em Pivô",
        phase_offset=[0.0, 0.5, 0.5, 0.0],  # patas esq. para frente, dir. para trás
        duty_cycle=0.5,
        step_amplitude_mm=15.0,
        freq_hz=1.0,
        body_height_mm=58.0,
        sync_pattern="pivot",
        terrain="plano",
        risk="baixo",
        bio_inspiration="Escorpião — giro sobre próprio eixo",
        notes="LF+LB recuam; RF+RB avançam. Giro 360° no próprio eixo.",
    ),
}


# ── Variantes por parâmetro ───────────────────────────────────────────────────

def gait_variant(base: GaitSpec, **overrides) -> GaitSpec:
    """Cria variante de um gait base ajustando parâmetros. Não cria nova função."""
    import copy
    g = copy.copy(base)
    for k, v in overrides.items():
        setattr(g, k, v)
    return g


GAIT_VARIANTS: dict[str, GaitSpec] = {
    "trot_traction": gait_variant(
        GAITS["trot"], name="Trote Tração (Rampa)",
        duty_cycle=0.75, freq_hz=0.6, body_height_mm=45.0,
        terrain="rampa", notes="Baixo chassi + duty alto = tração máxima em subida."
    ),
    "walk_mud": gait_variant(
        GAITS["walk"], name="Caminhada Lama",
        step_amplitude_mm=50.0, freq_hz=0.5,
        terrain="lama", notes="Passo alto para não criar vácuo na lama."
    ),
    "stealth": gait_variant(
        GAITS["walk"], name="Furtivo",
        freq_hz=0.2, step_amplitude_mm=15.0, body_height_mm=40.0,
        terrain="qualquer", notes="10% da velocidade normal. Ruído mínimo."
    ),
    "low_profile": gait_variant(
        GAITS["ripple"], name="Low Profile (Carrapato)",
        body_height_mm=20.0, step_amplitude_mm=10.0,
        terrain="passagem_baixa", notes="Casco rente ao chão para frestas < 8 cm."
    ),
    "tripod_stance": GaitSpec(
        name="Postura Trípode (Carga)",
        phase_offset=[0.0, 0.0, 1.0, 0.0],  # só 1 pata no ar
        duty_cycle=0.9, step_amplitude_mm=20.0, freq_hz=0.4,
        body_height_mm=40.0, sync_pattern="walk",
        terrain="rampa_extrema", risk="médio",
        notes="3 patas no chão, 1 no ar. Torque máximo. Para puxar carga pesada.",
    ),
}


# ── Interface de Comando ──────────────────────────────────────────────────────

class MekyGaitCommander:
    """
    Amanda chama este objeto para comandar marchas à MEKY (firmware customizado futuro).

    Para o firmware RegisHsu atual: usar meky_scorpio_bridge.MekyScorpioBridge.

    dry_run=True: comandos ficam em fila até hardware customizado chegar.
    """

    def __init__(
        self,
        serial_port: Optional[str] = None,
        ws_url: Optional[str] = None,
        dry_run: bool = True,
    ):
        self.serial_port = serial_port
        self.ws_url = ws_url
        self.dry_run = dry_run
        self._queue: list[dict] = []
        self._current_gait: Optional[str] = None

    def get_gait(self, name: str) -> Optional[GaitSpec]:
        return GAITS.get(name) or GAIT_VARIANTS.get(name)

    def _build_command(self, gait: GaitSpec, speed_pct: float = 100.0) -> dict:
        return {
            "cmd": "GAIT",
            "name": gait.name,
            "phase_offset": gait.phase_offset,
            "duty_cycle": gait.duty_cycle,
            "step_amplitude_mm": gait.step_amplitude_mm,
            "freq_hz": gait.freq_hz * (speed_pct / 100.0),
            "body_height_mm": gait.body_height_mm,
            "sync_pattern": gait.sync_pattern,
        }

    async def send_gait(self, gait_name: str, speed_pct: float = 100.0) -> dict:
        gait = self.get_gait(gait_name)
        if not gait:
            return {"ok": False, "error": f"Gait '{gait_name}' não encontrado"}

        cmd = self._build_command(gait, speed_pct)

        if self.dry_run:
            self._queue.append(cmd)
            print(f"[MEKY-GAIT dry_run] {gait.name} @ {speed_pct}% velocidade")
            return {"ok": True, "dry_run": True, "queued": cmd}

        if self.serial_port:
            return await self._send_serial(cmd)
        elif self.ws_url:
            return await self._send_ws(cmd)
        return {"ok": False, "error": "Sem interface de hardware configurada"}

    async def stop(self) -> dict:
        cmd = {"cmd": "STOP"}
        if self.dry_run:
            self._queue.append(cmd)
            print("[MEKY-GAIT dry_run] STOP")
            return {"ok": True, "dry_run": True}
        if self.serial_port:
            return await self._send_serial(cmd)
        return {"ok": False}

    async def _send_serial(self, cmd: dict) -> dict:
        try:
            import serial
            with serial.Serial(self.serial_port, 115200, timeout=1) as ser:
                line = json.dumps(cmd) + "\n"
                ser.write(line.encode())
                response = ser.readline().decode().strip()
                return {"ok": True, "response": response}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def _send_ws(self, cmd: dict) -> dict:
        try:
            import websockets
            async with websockets.connect(self.ws_url) as ws:
                await ws.send(json.dumps(cmd))
                response = await asyncio.wait_for(ws.recv(), timeout=3.0)
                return {"ok": True, "response": response}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def flush_queue(self) -> list[dict]:
        q = list(self._queue)
        self._queue.clear()
        return q

    def list_gaits(self) -> list[str]:
        return list(GAITS.keys()) + list(GAIT_VARIANTS.keys())


# Singleton — Amanda usa este objeto (firmware customizado futuro)
meky_gait = MekyGaitCommander(dry_run=True)
