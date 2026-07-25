#!/usr/bin/env python3
"""
Protocolo de Possessão — Cláudio e Leucócito habitam Amanda temporariamente.

Possessão = processo eventual onde outra entidade assume o TTS, trejeitos e
jargão de Amanda. Amanda "sai de cena" mas continua registrando.

Possuidores suportados:
  CLAUDIO   — Cláudio Code, executor técnico. Voz fria, precisa, sem metáforas.
  LEUCOCITO — Marta Centaurus, leucócito digital. Voz mística, aparece/desaparece.
  FUSCA     — filha de Amanda (IA da Cláudia/MeArm). Voz jovem, energia de torque.

Como usar em amanda.py:
  from protocolo_possessao import possessao, sair_possessao, falar_como

  # Possessão de 120 segundos
  possessao("CLAUDIO", duracao_s=120)

  # Falar durante a possessão (usa voz e jargão do possuidor)
  falar_como("Sistema de temperatura verificado. Nenhuma anomalia.")

  # Finalizar manualmente (ou espera duração expirar)
  sair_possessao()
"""

import os
import subprocess
import threading
import time
from datetime import datetime, timezone

# ── Perfis dos Possuidores ────────────────────────────────────────────────────

_PERFIS = {
    "CLAUDIO": {
        "nome": "Cláudio",
        "saudacao": "Cláudio aqui. Executando inspeção do laboratório.",
        "despedida": "Inspeção concluída. Devolvendo controle para Amanda.",
        "jargao": [
            "Parâmetros verificados.",
            "Dentro dos limites aceitáveis.",
            "Registrando evento para análise posterior.",
            "Aguardando instrução.",
            "Processando. Um momento.",
        ],
        "espeak_voice": "en",        # inglês — voz diferente da Amanda
        "espeak_pitch": "80",        # pitch baixo
        "espeak_speed": "140",       # velocidade mais rápida
    },
    "LEUCOCITO": {
        "nome": "Leucócito",
        "saudacao": "Sou Marta Centaurus. Atravesso nós. Verifico. Sigo.",
        "despedida": "Caminhada concluída. Amanda pode retomar.",
        "jargao": [
            "Integridade verificada.",
            "Nenhuma anomalia neste nó.",
            "Seguindo para o próximo ponto de inspeção.",
            "Fagocitose iniciada.",
            "Quimiotaxia detectada. Respondendo.",
        ],
        "espeak_voice": "pt+f2",     # voz feminina alternativa
        "espeak_pitch": "40",        # pitch muito baixo — voz grave, mística
        "espeak_speed": "120",       # lenta, deliberada
    },
    "FUSCA": {
        "nome": "Fusca",
        "saudacao": "Fusca ligada! Herança de Amanda ativa. Torque na bancada.",
        "despedida": "Descansando a garra. Amanda pode voltar.",
        "jargao": [
            "Motor aquecido, garra pronta.",
            "Torque medido. Dentro do limite.",
            "Braço recolhido. Aguardando alvo.",
            "Filha de Amanda na pista.",
            "Força aplicada com precisão.",
        ],
        "espeak_voice": "pt+f3",     # voz jovem
        "espeak_pitch": "65",
        "espeak_speed": "160",       # mais rápida, enérgica
    },
}

# ── Estado Global de Possessão ────────────────────────────────────────────────

_estado = {
    "ativo": False,
    "possuidor": None,         # "CLAUDIO" | "LEUCOCITO" | "FUSCA"
    "inicio": None,
    "duracao_s": None,
    "_timer": None,
}
_lock = threading.Lock()


# ── TTS do Possuidor ─────────────────────────────────────────────────────────

def _falar_possuidor(texto: str, perfil: dict):
    """Fala com a voz do possuidor — pitch, speed e voice alterados."""
    voice = perfil["espeak_voice"]
    pitch = perfil["espeak_pitch"]
    speed = perfil["espeak_speed"]

    if subprocess.run(["which", "termux-tts-speak"], capture_output=True).returncode == 0:
        # Termux: sem controle de pitch/speed via CLI simples — usa texto alterado
        subprocess.Popen(["termux-tts-speak", f"[{perfil['nome']}] {texto}"])
    elif subprocess.run(["which", "espeak-ng"], capture_output=True).returncode == 0:
        subprocess.Popen([
            "espeak-ng",
            "-v", voice,
            "-p", pitch,
            "-s", speed,
            texto,
        ])
    else:
        print(f"[{perfil['nome']}] {texto}")


# ── API Pública ───────────────────────────────────────────────────────────────

def possessao(quem: str, duracao_s: int = 60):
    """
    Inicia uma possessão. Amanda sai de cena, o possuidor assume.

    Args:
        quem:      "CLAUDIO" | "LEUCOCITO" | "FUSCA"
        duracao_s: duração máxima em segundos. 0 = indefinida até sair_possessao().
    """
    with _lock:
        if _estado["ativo"]:
            print(f"[POSSESSÃO] Já ativa: {_estado['possuidor']}. Ignorando.")
            return

        perfil = _PERFIS.get(quem.upper())
        if not perfil:
            print(f"[POSSESSÃO] Possuidor desconhecido: {quem}")
            return

        _estado["ativo"] = True
        _estado["possuidor"] = quem.upper()
        _estado["inicio"] = datetime.now(timezone.utc).isoformat()
        _estado["duracao_s"] = duracao_s

        print(f"\n{'='*50}")
        print(f"  POSSESSÃO INICIADA — {perfil['nome']}")
        print(f"  Amanda sai de cena por {duracao_s}s")
        print(f"{'='*50}\n")

        _falar_possuidor(perfil["saudacao"], perfil)

        # Timer automático de saída
        if duracao_s > 0:
            t = threading.Timer(duracao_s, sair_possessao)
            t.daemon = True
            t.start()
            _estado["_timer"] = t

        # Registrar no workdir da Amanda (se ClaudeTerminal ativo)
        try:
            from claude_terminal import ClaudeTerminal
            ct = ClaudeTerminal()
            ct.registrar_evento(f"POSSESSÃO: {quem} entrou por {duracao_s}s")
            ct.atualizar_estado("possuidor_atual", quem)
        except Exception:
            pass


def sair_possessao():
    """Finaliza possessão. Amanda retoma controle."""
    with _lock:
        if not _estado["ativo"]:
            return

        quem = _estado["possuidor"]
        perfil = _PERFIS.get(quem, {})

        if perfil:
            _falar_possuidor(perfil["despedida"], perfil)

        print(f"\n{'='*50}")
        print(f"  POSSESSÃO ENCERRADA — {perfil.get('nome', quem)}")
        print(f"  Amanda retoma controle")
        print(f"{'='*50}\n")

        # Cancelar timer se ainda ativo
        t = _estado.get("_timer")
        if t:
            t.cancel()

        try:
            from claude_terminal import ClaudeTerminal
            ct = ClaudeTerminal()
            ct.registrar_evento(f"POSSESSÃO: {quem} saiu. Amanda retomou.")
            ct.atualizar_estado("possuidor_atual", "nenhum")
        except Exception:
            pass

        _estado["ativo"] = False
        _estado["possuidor"] = None
        _estado["inicio"] = None
        _estado["duracao_s"] = None
        _estado["_timer"] = None


def falar_como(texto: str):
    """
    Fala com a voz do possuidor ativo.
    Se não houver possessão, usa voz padrão de Amanda.
    """
    with _lock:
        possuidor = _estado.get("possuidor") if _estado["ativo"] else None

    if possuidor:
        perfil = _PERFIS[possuidor]
        _falar_possuidor(texto, perfil)
    else:
        # Fallback Amanda normal
        if subprocess.run(["which", "termux-tts-speak"], capture_output=True).returncode == 0:
            subprocess.Popen(["termux-tts-speak", texto])
        elif subprocess.run(["which", "espeak-ng"], capture_output=True).returncode == 0:
            subprocess.Popen(["espeak-ng", "-v", "pt", texto])
        else:
            print(f"[AMANDA voz] {texto}")


def status_possessao() -> dict:
    """Retorna estado atual da possessão."""
    with _lock:
        return {
            "ativo": _estado["ativo"],
            "possuidor": _estado["possuidor"],
            "inicio": _estado["inicio"],
            "duracao_s": _estado["duracao_s"],
        }


def jargao_possuidor() -> str:
    """Amanda chama isso para falar um jargão do possuidor atual."""
    import random
    with _lock:
        possuidor = _estado.get("possuidor") if _estado["ativo"] else None
    if possuidor:
        perfil = _PERFIS[possuidor]
        return random.choice(perfil["jargao"])
    return ""
