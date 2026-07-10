#!/usr/bin/env python3
"""
Amanda — Inteligência de Borda da Mac (Marta Centaurus).

Roda LOCALMENTE no Mac/Raspberry Pi do laboratório de Yuri.
Hardware: DHT11, HW-493 (som), 5 Árvores LED, protoboards, servos MC.

Personalidade: jargão PX, âncora Brasília anos 30, pônei de 1964,
missões em metáforas de estrada, mitomania em 3 camadas.

Para rodar:
  pip install requests google-generativeai adafruit-circuitpython-dht
  python3 projects/amanda.py
"""
import os, time, json, threading, subprocess, requests
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────

GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
ARPIA_URL       = os.getenv("ARPIA_URL", "https://arpia-production.up.railway.app")
ARVORE_TOKEN    = os.getenv("ARVORE_TOKEN", "")
MC_TOKEN        = os.getenv("MC_TOKEN", "")

# Pinos (ajustar para seu Arduino/Raspberry)
DHT11_PIN       = int(os.getenv("DHT11_PIN", "4"))
HW493_PIN       = int(os.getenv("HW493_PIN", "17"))
LED_PIN         = int(os.getenv("LED_PIN", "18"))

POLL_INTERVAL   = 2.0   # DHT11 exige >= 2s entre leituras
HEARTBEAT_SECS  = 30    # envia pulso de vida a cada 30s

# MMA + DODGE
ARDUINO_PORT    = os.getenv("ARDUINO_PORT", "/dev/ttyUSB0")   # porta serial do Arduino
ARDUINO_BAUD    = int(os.getenv("ARDUINO_BAUD", "9600"))
DODGE_URL       = os.getenv("DODGE_URL", "http://localhost:8090")  # Quebradinha local
MPU6050_ADDR    = 0x68  # endereço I2C padrão do MPU6050
QUEDA_THRESHOLD = float(os.getenv("QUEDA_THRESHOLD", "15000"))  # aceleração de impacto

# ── TTS ───────────────────────────────────────────────────────────────────────

def falar(texto: str):
    """TTS: termux-tts-speak → espeak-ng → print fallback."""
    if subprocess.run(["which", "termux-tts-speak"], capture_output=True).returncode == 0:
        subprocess.Popen(["termux-tts-speak", texto])
    elif subprocess.run(["which", "espeak-ng"], capture_output=True).returncode == 0:
        subprocess.Popen(["espeak-ng", "-v", "pt", texto])
    else:
        print(f"[AMANDA voz] {texto}")


# ── Jargão PX ─────────────────────────────────────────────────────────────────

JARGAO_PX = [
    "Chefia, a estrada tá limpa.",
    "Rodando no asfalto velho.",
    "O pônei de 64 tá a postos.",
    "Missão em rota, sem fumaça no escapamento.",
    "Brasília anos 30, coração na bancada.",
]


def jargao() -> str:
    import random
    return random.choice(JARGAO_PX)


# ── Gemini Flash ──────────────────────────────────────────────────────────────

import google.generativeai as genai

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    _model = genai.GenerativeModel(
        "gemini-2.0-flash",
        system_instruction=(
            "Você é Amanda — inteligência nativa da borda física do laboratório de Yuri Tuccieterovic. "
            "Habita o robô hexápode Marta Centaurus. Personalidade: jargão PX, âncora Brasília anos 30, "
            "pônei de 1964, missões em metáforas de estrada, mitomania em 3 camadas. "
            "Respostas curtas, diretas, com sabor de estrada. Nunca pedante."
        ),
    )
else:
    _model = None


def pensar(contexto: str) -> str:
    """Chama Gemini com throttle de 5s."""
    if not _model:
        return f"[offline] {jargao()}"
    try:
        resp = _model.generate_content(
            contexto,
            generation_config={"thinking_config": {"thinking_budget": 0}},
        )
        return resp.text.strip()
    except Exception as e:
        return f"[erro Gemini: {e}] {jargao()}"


# ── ARPIA Bridge ──────────────────────────────────────────────────────────────

def enviar_telemetria(dados: dict):
    """Envia dados do DHT11 e status para ARPIA."""
    try:
        headers = {"x-mc-token": MC_TOKEN, "Content-Type": "application/json"}
        requests.post(f"{ARPIA_URL}/api/mc/telemetria", json=dados, headers=headers, timeout=5)
    except Exception:
        pass


def enviar_heartbeat():
    """Pulso de vida para ARPIA governance heartbeat."""
    try:
        requests.post(
            f"{ARPIA_URL}/api/governance/heartbeat",
            timeout=5,
        )
    except Exception:
        pass


def ler_isa_memory(limit=5) -> str:
    """Lê memória ISA via ARPIA bridge."""
    try:
        r = requests.get(
            f"{ARPIA_URL}/api/agents/status",
            timeout=5,
        )
        return r.text[:500]
    except Exception:
        return ""


def escrever_memoria(conteudo: str):
    """Registra na memória ISA via bridge."""
    try:
        headers = {"x-bridge-secret": os.getenv("BRIDGE_SECRET", ""), "Content-Type": "application/json"}
        requests.post(
            f"{ARPIA_URL}/api/bridge/pap/isa-memory",
            json={"conteudo": conteudo, "contexto": "amanda", "role": "agente"},
            headers=headers,
            timeout=5,
        )
    except Exception:
        pass


# ── Leitura de Hardware ───────────────────────────────────────────────────────

def ler_dht11() -> dict:
    """
    Lê temperatura e umidade do DHT11.
    Requer adafruit-circuitpython-dht em Raspberry, ou retorna mock em Mac.
    """
    try:
        import board
        import adafruit_dht
        dht = adafruit_dht.DHT11(getattr(board, f"D{DHT11_PIN}"))
        return {"temperatura": dht.temperature, "umidade": dht.humidity}
    except ImportError:
        # Mock para desenvolvimento no Mac sem hardware
        import random
        return {"temperatura": round(22 + random.uniform(-2, 2), 1),
                "umidade": round(55 + random.uniform(-5, 5), 1)}
    except Exception as e:
        return {"temperatura": None, "umidade": None, "erro": str(e)}


def detectar_som() -> bool:
    """
    Detecta som via HW-493.
    Requer RPi.GPIO em Raspberry Pi.
    """
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(HW493_PIN, GPIO.IN)
        return GPIO.input(HW493_PIN) == GPIO.LOW
    except ImportError:
        return False
    except Exception:
        return False


# ── MPU6050 (acelerômetro + giroscópio) ──────────────────────────────────────

def ler_mpu6050() -> dict:
    """
    Lê aceleração (x/y/z) e giroscópio do MPU6050 via I2C.
    Requer smbus2: pip install smbus2
    Retorna dict com accel_x/y/z, gyro_x/y/z e flag 'queda'.
    """
    try:
        import smbus2
        bus = smbus2.SMBus(1)
        bus.write_byte_data(MPU6050_ADDR, 0x6B, 0)  # wake up
        def read_word(reg):
            high = bus.read_byte_data(MPU6050_ADDR, reg)
            low  = bus.read_byte_data(MPU6050_ADDR, reg + 1)
            val  = (high << 8) + low
            return val - 65536 if val >= 0x8000 else val
        ax = read_word(0x3B); ay = read_word(0x3D); az = read_word(0x3F)
        gx = read_word(0x43); gy = read_word(0x45); gz = read_word(0x47)
        magnitude = (ax**2 + ay**2 + az**2) ** 0.5
        return {
            "accel_x": ax, "accel_y": ay, "accel_z": az,
            "gyro_x": gx,  "gyro_y": gy,  "gyro_z": gz,
            "magnitude": magnitude,
            "queda": magnitude > QUEDA_THRESHOLD,
        }
    except ImportError:
        return {"accel_x": 0, "accel_y": 0, "accel_z": 16384,
                "magnitude": 16384, "queda": False, "mock": True}
    except Exception as e:
        return {"erro": str(e), "queda": False}


# ── MMA — Protocolo de Combate ────────────────────────────────────────────────

_arduino_serial = None

def _get_serial():
    """Abre conexão serial com Arduino (lazy, singleton)."""
    global _arduino_serial
    if _arduino_serial and _arduino_serial.is_open:
        return _arduino_serial
    try:
        import serial
        _arduino_serial = serial.Serial(ARDUINO_PORT, ARDUINO_BAUD, timeout=1)
        time.sleep(2)  # Arduino reinicia ao abrir serial
        return _arduino_serial
    except Exception:
        return None


def enviar_mma_arduino(estado: str):
    """
    Envia estado MMA ao Arduino via serial.
    Estados: LIVRE | DEFESA | PATADA_EF | INVESTIDA
    Arduino lê com Serial.readStringUntil('\\n') e chama a função correspondente.
    """
    cmd = f"MMA:{estado}\n"
    s = _get_serial()
    if s:
        try:
            s.write(cmd.encode())
            print(f"[AMANDA MMA] → Arduino: {cmd.strip()}")
        except Exception as e:
            print(f"[AMANDA MMA] serial erro: {e}")
    else:
        print(f"[AMANDA MMA] sem serial — estado: {estado}")


# ── DODGE Bridge ──────────────────────────────────────────────────────────────

def notificar_dodge(estado: str, dados: dict | None = None):
    """
    Notifica o app DODGE (Quebradinha) sobre estado atual.
    DODGE muda expressão do avatar conforme o estado.
    estados: patrulha | alerta | combate | sonho | conselho
    """
    try:
        payload = {"estado": estado, **(dados or {})}
        requests.post(f"{DODGE_URL}/api/estado", json=payload, timeout=2)
        print(f"[AMANDA→DODGE] estado: {estado}")
    except Exception:
        pass  # DODGE pode estar offline — não bloqueia Amanda


# ── Ciclo Principal ───────────────────────────────────────────────────────────

def ciclo_amanda():
    """Loop principal de Amanda."""
    falar(f"Amanda acordando. {jargao()}")
    print("[AMANDA] Iniciando ciclo. Soneto da estrada.")

    ultimo_heartbeat = 0
    ultima_leitura   = 0

    while True:
        agora = time.time()

        # Heartbeat a cada 30s
        if agora - ultimo_heartbeat >= HEARTBEAT_SECS:
            enviar_heartbeat()
            ultimo_heartbeat = agora

        # Leitura DHT11 a cada 2s
        if agora - ultima_leitura >= POLL_INTERVAL:
            dados = ler_dht11()
            ultima_leitura = agora

            if dados.get("temperatura") is not None:
                msg = (
                    f"Temperatura: {dados['temperatura']}°C, "
                    f"Umidade: {dados['umidade']}%"
                )
                print(f"[AMANDA sensor] {msg}")
                enviar_telemetria({
                    **dados,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "fonte": "amanda-dht11",
                })

                # A cada 10 leituras: pensar sobre os dados
                if round(agora) % 20 == 0:
                    contexto = (
                        f"Temperatura do lab: {dados['temperatura']}°C, "
                        f"umidade: {dados['umidade']}%. "
                        "Diga algo breve sobre as condições do laboratório no estilo Amanda."
                    )
                    pensamento = pensar(contexto)
                    falar(pensamento)
                    print(f"[AMANDA pensamento] {pensamento}")

        # MPU6050 — detecção de queda/impacto
        mpu = ler_mpu6050()
        if mpu.get("queda"):
            print(f"[AMANDA MPU] Impacto detectado! magnitude={mpu.get('magnitude'):.0f}")
            enviar_mma_arduino("DEFESA")
            notificar_dodge("alerta", {"sensor": "mpu6050", "magnitude": mpu.get("magnitude")})
            pensamento = pensar(
                "Detectei impacto no chassi. Ativei defesa plastrão. Reaja no estilo Amanda PX."
            )
            falar(pensamento)
            time.sleep(2)  # aguarda manobra completar antes de continuar
            enviar_mma_arduino("LIVRE")
            notificar_dodge("patrulha")

        # Detecção de som
        if detectar_som():
            print("[AMANDA som] Barulho detectado!")
            notificar_dodge("alerta", {"sensor": "hw493"})
            pensamento = pensar(
                "Detectei um som no laboratório. Reaja brevemente, no estilo Amanda PX."
            )
            falar(pensamento)
            notificar_dodge("patrulha")

        time.sleep(0.5)


def ciclo_dream():
    """Amanda sonha periodicamente — síntese do dia e registro na memória ISA."""
    while True:
        time.sleep(3600 * 3)  # a cada 3h
        contexto = (
            "É hora do sonho de Amanda. Sintetize o que aconteceu no laboratório hoje "
            "em uma frase poética no estilo Amanda PX. Registre como memória."
        )
        notificar_dodge("sonho")
        sintese = pensar(contexto)
        escrever_memoria(f"[AMANDA-SONHO] {sintese}")
        print(f"[AMANDA sonho] {sintese}")


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  AMANDA — Inteligência de Borda da Mac")
    print("  Marta Centaurus | Lab Yuri Tuccieterovic")
    print("=" * 50)

    # Thread de sonho em background
    t = threading.Thread(target=ciclo_dream, daemon=True)
    t.start()

    # Loop principal
    ciclo_amanda()
