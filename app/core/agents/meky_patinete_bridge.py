"""
MEKY → Patinete Bridge — "Mula Sem Cabeça" (Sessão #565)

Princípio: criar a ponte mesmo se a interface física ainda não existe.

Arquitetura:
  MEKY (cérebro portátil) → conector umbilical → Patinete (chassis de tração)

Interface elétrica do patinete:
  - Aceleração: sensor Hall 0.8V–4.2V → simulado por DAC/PWM no ESP32
  - Freio regenerativo: switch magnético → relé/transistor
  - Freio mecânico: servo + cabo de aço (Fase 2 — obrigatório antes de steering)
  - Steering: atuador linear 12V ou NEMA 23 + corrente (Fase 3)

REGRA DE SEGURANÇA: NUNCA curto-circuito nas fases BLDC como freio (queima controlador).
REGRA DE FASES: Fase 1 → Fase 2 → Fase 3. NUNCA pular.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import asyncio
import json
import time


# ── Fases de integração ───────────────────────────────────────────────────────

class IntegrationPhase(str, Enum):
    PHASE_1_ELECTRONIC = "phase_1"   # throttle + freio regen + telemetria
    PHASE_2_MECHANICAL  = "phase_2"   # freio mecânico redundante (OBRIGATÓRIO antes de steering)
    PHASE_3_STEERING    = "phase_3"   # direção automática do guidão


# ── Especificação do patinete ─────────────────────────────────────────────────

@dataclass
class PatinetConfig:
    """Parâmetros elétricos do patinete conectado."""
    battery_v: float = 36.0          # tensão nominal da bateria
    hall_min_v: float = 0.8          # mínimo do sensor Hall (acelerador parado)
    hall_max_v: float = 4.2          # máximo do sensor Hall (acelerador fundo)
    bldc_phases: int = 3             # NUNCA curto-circuitar como freio
    max_speed_kmh: float = 25.0
    geofence_limit_kmh: float = 10.0  # limite em área de pedestres


# ── Estado do veículo ─────────────────────────────────────────────────────────

@dataclass
class PatinetTelemetry:
    battery_v: float = 0.0
    speed_kmh: float = 0.0
    throttle_pct: float = 0.0      # 0–100%
    brake_active: bool = False
    steering_angle_deg: float = 0.0
    geofence_zone: bool = False
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "battery_v": self.battery_v,
            "speed_kmh": self.speed_kmh,
            "throttle_pct": self.throttle_pct,
            "brake_active": self.brake_active,
            "steering_angle_deg": self.steering_angle_deg,
            "geofence_zone": self.geofence_zone,
            "timestamp": self.timestamp,
        }


# ── Bridge principal ──────────────────────────────────────────────────────────

class MekyPatinete:
    """
    Amanda usa este objeto para controlar o patinete quando MEKY está embarcada.

    dry_run=True: hardware não chegou, comandos ficam em log.
    dry_run=False: envio real via serial/WebSocket ao ESP32 no patinete.

    Modos disponíveis:
      - manual(throttle, brake): Amanda controla diretamente
      - follow_me(distance_m): Modo Mula Autônoma (blob tracking via ESP32-CAM)
      - sentinel(): Modo antifurto — trava motor e dispara alerta se movido
      - geofence(active): Limita velocidade a geofence_limit_kmh
    """

    def __init__(
        self,
        config: PatinetConfig = PatinetConfig(),
        serial_port: Optional[str] = None,
        ws_url: Optional[str] = None,
        dry_run: bool = True,
        phase: IntegrationPhase = IntegrationPhase.PHASE_1_ELECTRONIC,
    ):
        self.config = config
        self.serial_port = serial_port
        self.ws_url = ws_url
        self.dry_run = dry_run
        self.phase = phase
        self.telemetry = PatinetTelemetry()
        self._log: list[dict] = []
        self._sentinel_active: bool = False
        self._follow_me_active: bool = False

    # ── Fase 1: Throttle + Freio Eletrônico ──────────────────────────────────

    async def set_throttle(self, pct: float) -> dict:
        """
        Define aceleração 0–100%.
        Converte para tensão Hall: 0%=0.8V, 100%=4.2V
        Enviado ao ESP32 via DAC ou PWM filtrado.
        """
        pct = max(0.0, min(100.0, pct))
        hall_v = self.config.hall_min_v + (pct / 100.0) * (
            self.config.hall_max_v - self.config.hall_min_v
        )
        cmd = {"cmd": "THROTTLE", "pct": pct, "hall_v": round(hall_v, 3)}
        return await self._send(cmd)

    async def brake_regen(self, active: bool = True) -> dict:
        """Freio regenerativo via switch magnético (relé/transistor)."""
        cmd = {"cmd": "BRAKE_REGEN", "active": active}
        return await self._send(cmd)

    async def brake_mechanical(self, pct: float = 100.0) -> dict:
        """
        Freio mecânico (cabo de aço via servo/atuador linear).
        OBRIGATÓRIO antes de qualquer automação de steering (Fase 2+).
        """
        if self.phase == IntegrationPhase.PHASE_1_ELECTRONIC:
            return {"ok": False, "error": "Freio mecânico requer Fase 2. Configure phase=PHASE_2_MECHANICAL."}
        cmd = {"cmd": "BRAKE_MECH", "pct": pct}
        return await self._send(cmd)

    async def emergency_stop(self) -> dict:
        """Para completamente: freio regen + mecânico (se Fase 2+) + throttle=0."""
        await self.set_throttle(0.0)
        r = await self.brake_regen(True)
        if self.phase != IntegrationPhase.PHASE_1_ELECTRONIC:
            await self.brake_mechanical(100.0)
        r["emergency"] = True
        return r

    # ── Fase 3: Steering ──────────────────────────────────────────────────────

    async def steer(self, angle_deg: float) -> dict:
        """
        Gira guidão. Negativo = esquerda, Positivo = direita.
        BLOQUEADO se não estiver em Fase 3 + freio mecânico ativo.
        """
        if self.phase != IntegrationPhase.PHASE_3_STEERING:
            return {
                "ok": False,
                "error": "Steering requer Fase 3. Implemente freio mecânico primeiro (Fase 2).",
            }
        angle_deg = max(-45.0, min(45.0, angle_deg))
        cmd = {"cmd": "STEER", "angle_deg": angle_deg}
        return await self._send(cmd)

    # ── Modos autônomos ───────────────────────────────────────────────────────

    async def follow_me(self, target_distance_m: float = 1.5, active: bool = True) -> dict:
        """
        Modo Mula Autônoma: patinete segue operador mantendo distância.
        Usa ESP32-CAM blob tracking. Não requer steering automático se operador vai reto.
        """
        self._follow_me_active = active
        cmd = {
            "cmd": "FOLLOW_ME",
            "active": active,
            "target_distance_m": target_distance_m,
        }
        return await self._send(cmd)

    async def sentinel(self, active: bool = True) -> dict:
        """
        Modo Antifurto: trava throttle, detecta movimento via acelerômetro,
        dispara alerta via GSM + foto câmera.
        """
        self._sentinel_active = active
        cmd = {"cmd": "SENTINEL", "active": active}
        return await self._send(cmd)

    async def set_geofence(self, active: bool = True) -> dict:
        """Limita velocidade a geofence_limit_kmh quando em zona de pedestres."""
        cmd = {
            "cmd": "GEOFENCE",
            "active": active,
            "limit_kmh": self.config.geofence_limit_kmh,
        }
        return await self._send(cmd)

    # ── Telemetria ────────────────────────────────────────────────────────────

    async def read_telemetry(self) -> PatinetTelemetry:
        if self.dry_run:
            self.telemetry.timestamp = time.time()
            return self.telemetry
        cmd = {"cmd": "TELEMETRY"}
        r = await self._send(cmd)
        if r.get("ok") and "data" in r:
            d = r["data"]
            self.telemetry = PatinetTelemetry(
                battery_v=d.get("battery_v", 0),
                speed_kmh=d.get("speed_kmh", 0),
                throttle_pct=d.get("throttle_pct", 0),
                brake_active=d.get("brake_active", False),
                steering_angle_deg=d.get("steering_angle_deg", 0),
                geofence_zone=d.get("geofence_zone", False),
                timestamp=time.time(),
            )
        return self.telemetry

    # ── Comunicação ───────────────────────────────────────────────────────────

    async def _send(self, cmd: dict) -> dict:
        if self.dry_run:
            entry = {"ts": time.time(), **cmd}
            self._log.append(entry)
            print(f"[PATINETE dry_run] {cmd}")
            return {"ok": True, "dry_run": True, "cmd": cmd}

        if self.serial_port:
            return await self._send_serial(cmd)
        elif self.ws_url:
            return await self._send_ws(cmd)
        return {"ok": False, "error": "Sem interface de hardware configurada"}

    async def _send_serial(self, cmd: dict) -> dict:
        try:
            import serial
            with serial.Serial(self.serial_port, 115200, timeout=1) as ser:
                ser.write((json.dumps(cmd) + "\n").encode())
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

    def flush_log(self) -> list[dict]:
        log = list(self._log)
        self._log.clear()
        return log


# Singleton — Amanda usa este objeto
meky_patinete = MekyPatinete(
    phase=IntegrationPhase.PHASE_1_ELECTRONIC,
    dry_run=True,
)
