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

        # Detecção de som
        if detectar_som():
            print("[AMANDA som] Barulho detectado!")
            pensamento = pensar(
                "Detectei um som no laboratório. Reaja brevemente, no estilo Amanda PX."
            )
            falar(pensamento)

        time.sleep(0.5)


def ciclo_dream():
    """Amanda sonha periodicamente — síntese do dia e registro na memória ISA."""
    while True:
        time.sleep(3600 * 3)  # a cada 3h
        contexto = (
            "É hora do sonho de Amanda. Sintetize o que aconteceu no laboratório hoje "
            "em uma frase poética no estilo Amanda PX. Registre como memória."
        )
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
