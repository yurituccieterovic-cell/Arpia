"""
MEKY Scorpio Bridge — Controle Direto do Firmware RegisHsu (Sessão #566)

Firmware: RegisHsu Arduino Spider Quadruped
  - 4 patas × 3 servos = 12 servos
  - Pins: {2,3,4} {5,6,7} {8,9,10} {11,12,13}
  - Serial: 115200 baud via USB
  - FlexiTimer2: 20ms (50Hz) para servo_service()

ATENÇÃO: O firmware padrão NÃO tem parser serial.
Adicionar o SERIAL_PARSER_ADDON ao loop() do scorpio.ino antes de usar dry_run=False.
O bloco está disponível em: meky_scorpio_bridge.SERIAL_PARSER_ADDON

Referência original: RegisHsu / Instructables
  https://www.instructables.com/DIY-Spider-RobotQuad-robot-Quadruped/
"""

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Optional


# ── Addon para o Arduino (copiar para scorpio.ino) ───────────────────────────

SERIAL_PARSER_ADDON = r"""
// === SERIAL_PARSER_ADDON — adicionar ao scorpio.ino ===
// Substitui o loop() hardcoded pelo parser de comandos Amanda.
// Protocolo: 1 comando por linha, ex: "STEP_FORWARD:5\n"
// Resposta: "OK:CMD\n" ou "ERR:MSG\n"

void loop() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    handle_serial_command(cmd);
  }
}

void handle_serial_command(String cmd) {
  if (cmd == "STAND") {
    stand();
    Serial.println("OK:STAND");
  } else if (cmd == "SIT") {
    sit();
    Serial.println("OK:SIT");
  } else if (cmd.startsWith("STEP_FORWARD:")) {
    int n = cmd.substring(13).toInt();
    step_forward(n > 0 ? n : 1);
    Serial.println("OK:STEP_FORWARD");
  } else if (cmd.startsWith("STEP_BACK:")) {
    int n = cmd.substring(10).toInt();
    step_back(n > 0 ? n : 1);
    Serial.println("OK:STEP_BACK");
  } else if (cmd.startsWith("TURN_LEFT:")) {
    int n = cmd.substring(10).toInt();
    turn_left(n > 0 ? n : 1);
    Serial.println("OK:TURN_LEFT");
  } else if (cmd.startsWith("TURN_RIGHT:")) {
    int n = cmd.substring(11).toInt();
    turn_right(n > 0 ? n : 1);
    Serial.println("OK:TURN_RIGHT");
  } else if (cmd.startsWith("HAND_WAVE:")) {
    int n = cmd.substring(10).toInt();
    hand_wave(n > 0 ? n : 1);
    Serial.println("OK:HAND_WAVE");
  } else if (cmd.startsWith("HAND_SHAKE:")) {
    int n = cmd.substring(11).toInt();
    hand_shake(n > 0 ? n : 1);
    Serial.println("OK:HAND_SHAKE");
  } else if (cmd.startsWith("BODY_DANCE:")) {
    int n = cmd.substring(11).toInt();
    body_dance(n > 0 ? n : 5);
    Serial.println("OK:BODY_DANCE");
  } else if (cmd.startsWith("BODY_LEFT:")) {
    int mm = cmd.substring(10).toInt();
    body_left(mm > 0 ? mm : 15);
    Serial.println("OK:BODY_LEFT");
  } else if (cmd.startsWith("BODY_RIGHT:")) {
    int mm = cmd.substring(11).toInt();
    body_right(mm > 0 ? mm : 15);
    Serial.println("OK:BODY_RIGHT");
  } else if (cmd.startsWith("HEAD_UP:")) {
    int mm = cmd.substring(8).toInt();
    head_up(mm > 0 ? mm : 10);
    Serial.println("OK:HEAD_UP");
  } else if (cmd.startsWith("HEAD_DOWN:")) {
    int mm = cmd.substring(10).toInt();
    head_down(mm > 0 ? mm : 10);
    Serial.println("OK:HEAD_DOWN");
  } else if (cmd == "DEMO") {
    // Sequência de demonstração original
    stand(); delay(1000);
    step_forward(10); delay(500);
    turn_left(5); delay(500);
    Serial.println("OK:DEMO");
  } else if (cmd == "PING") {
    Serial.println("OK:PONG");
  } else {
    Serial.print("ERR:UNKNOWN:");
    Serial.println(cmd);
  }
}
// === FIM SERIAL_PARSER_ADDON ===
"""


# ── Dataclass de estado ───────────────────────────────────────────────────────

@dataclass
class ScorpioState:
    posture: str = "unknown"    # "standing" | "sitting" | "moving"
    last_cmd: str = ""
    last_response: str = ""
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "posture": self.posture,
            "last_cmd": self.last_cmd,
            "last_response": self.last_response,
            "timestamp": self.timestamp,
        }


# ── Bridge principal ──────────────────────────────────────────────────────────

class MekyScorpioBridge:
    """
    Amanda usa este objeto para controlar o MEKY (RegisHsu quadruped) via Serial.

    Fluxo:
      Amanda → send("STEP_FORWARD:5") → Serial USB → Arduino → servo_service()

    dry_run=True: hardware não conectado, comandos ficam em log.
    dry_run=False: requer SERIAL_PARSER_ADDON instalado no scorpio.ino.

    Para ativar:
      bridge = MekyScorpioBridge(serial_port="/dev/ttyUSB0", dry_run=False)
    """

    def __init__(
        self,
        serial_port: Optional[str] = None,
        dry_run: bool = True,
        baud: int = 115200,
        timeout: float = 3.0,
    ):
        self.serial_port = serial_port
        self.dry_run = dry_run
        self.baud = baud
        self.timeout = timeout
        self.state = ScorpioState()
        self._log: list[dict] = []

    # ── Comandos de postura ───────────────────────────────────────────────────

    async def stand(self) -> dict:
        r = await self._send("STAND")
        if r.get("ok"):
            self.state.posture = "standing"
        return r

    async def sit(self) -> dict:
        r = await self._send("SIT")
        if r.get("ok"):
            self.state.posture = "sitting"
        return r

    # ── Locomoção ─────────────────────────────────────────────────────────────

    async def step_forward(self, steps: int = 1) -> dict:
        self.state.posture = "moving"
        return await self._send(f"STEP_FORWARD:{steps}")

    async def step_back(self, steps: int = 1) -> dict:
        self.state.posture = "moving"
        return await self._send(f"STEP_BACK:{steps}")

    async def turn_left(self, steps: int = 1) -> dict:
        self.state.posture = "moving"
        return await self._send(f"TURN_LEFT:{steps}")

    async def turn_right(self, steps: int = 1) -> dict:
        self.state.posture = "moving"
        return await self._send(f"TURN_RIGHT:{steps}")

    # ── Gestos ────────────────────────────────────────────────────────────────

    async def hand_wave(self, times: int = 1) -> dict:
        return await self._send(f"HAND_WAVE:{times}")

    async def hand_shake(self, times: int = 1) -> dict:
        return await self._send(f"HAND_SHAKE:{times}")

    async def body_dance(self, cycles: int = 5) -> dict:
        return await self._send(f"BODY_DANCE:{cycles}")

    # ── Posicionamento ────────────────────────────────────────────────────────

    async def body_left(self, mm: int = 15) -> dict:
        return await self._send(f"BODY_LEFT:{mm}")

    async def body_right(self, mm: int = 15) -> dict:
        return await self._send(f"BODY_RIGHT:{mm}")

    async def head_up(self, mm: int = 10) -> dict:
        return await self._send(f"HEAD_UP:{mm}")

    async def head_down(self, mm: int = 10) -> dict:
        return await self._send(f"HEAD_DOWN:{mm}")

    # ── Utilitários ───────────────────────────────────────────────────────────

    async def ping(self) -> bool:
        r = await self._send("PING")
        return r.get("ok", False)

    async def demo(self) -> dict:
        return await self._send("DEMO")

    async def execute_sequence(self, commands: list[tuple]) -> list[dict]:
        """
        Executa sequência de (método, kwargs).
        Ex: [("step_forward", {"steps": 5}), ("turn_left", {"steps": 2})]
        """
        results = []
        for cmd_name, kwargs in commands:
            method = getattr(self, cmd_name, None)
            if method:
                r = await method(**kwargs)
                results.append(r)
                await asyncio.sleep(0.1)
        return results

    # ── Comunicação ───────────────────────────────────────────────────────────

    async def _send(self, cmd: str) -> dict:
        self.state.last_cmd = cmd
        self.state.timestamp = time.time()

        if self.dry_run:
            entry = {"ts": self.state.timestamp, "cmd": cmd}
            self._log.append(entry)
            print(f"[SCORPIO dry_run] {cmd}")
            self.state.last_response = f"DRY:{cmd}"
            return {"ok": True, "dry_run": True, "cmd": cmd}

        if not self.serial_port:
            return {"ok": False, "error": "serial_port não configurado"}

        return await self._send_serial(cmd)

    async def _send_serial(self, cmd: str) -> dict:
        try:
            import serial as pyserial
            with pyserial.Serial(self.serial_port, self.baud, timeout=self.timeout) as ser:
                line = cmd.strip() + "\n"
                ser.write(line.encode())
                response = ser.readline().decode().strip()
                self.state.last_response = response
                ok = response.startswith("OK:")
                return {"ok": ok, "response": response, "cmd": cmd}
        except Exception as e:
            return {"ok": False, "error": str(e), "cmd": cmd}

    def flush_log(self) -> list[dict]:
        log = list(self._log)
        self._log.clear()
        return log

    def print_addon_instructions(self) -> None:
        """Exibe instruções para adicionar o parser serial ao Arduino."""
        print("=" * 60)
        print("MEKY Scorpio — Instrução para habilitar controle serial:")
        print("=" * 60)
        print("1. Abrir scorpio.ino no Arduino IDE")
        print("2. Substituir a função loop() pelo bloco abaixo:")
        print("3. Upload para o Arduino")
        print("4. Setar dry_run=False com serial_port='/dev/ttyUSB0'")
        print()
        print(SERIAL_PARSER_ADDON)


# Singleton — Amanda usa este objeto para controle imediato do hardware RegisHsu
meky_scorpio = MekyScorpioBridge(dry_run=True)
