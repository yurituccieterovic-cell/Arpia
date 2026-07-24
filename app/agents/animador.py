"""
IA Animador — Guardião do Ecossistema PAP (Sessão #566)

Função: acordar a cada 45 min, ler o ecossistema, anotar filosofias,
sugerir alterações por email. Efeito colateral: Railway não dorme.

Ciclo (45 min):
  1. Pinga URLs do ecossistema (keep-alive)
  2. Lê assembleias recentes (IMAP Gmail)
  3. Sintetiza filosofias detectadas (OpenAI)
  4. Armazena insights no Conector
  5. A cada 6 ciclos (≈4.5h): envia email de sugestões para Yuri
"""

import asyncio
import imaplib
import os
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import httpx


# ── Configuração ──────────────────────────────────────────────────────────────

CYCLE_INTERVAL_S = 45 * 60          # 45 minutos entre ciclos
EMAIL_EVERY_N_CYCLES = 6            # enviar email a cada 6 ciclos (≈4.5h)
MAX_ASSEMBLY_EMAILS = 3             # quantas assembleias ler por ciclo
YURI_EMAIL = "yurituccieterovic@gmail.com"

ECOSYSTEM_URLS = [
    "https://site-st-production.up.railway.app/api/healthz",
    "https://site-st.vercel.app/aliancapanorama",
    "https://site-st.vercel.app/aliancapanorama/adm",
    "https://site-st.vercel.app/aliancapanorama/portal",
]

PAP_API = "https://site-st-production.up.railway.app"


# ── Estado do Animador ────────────────────────────────────────────────────────

class AnimadorState:
    def __init__(self):
        self.ciclos: int = 0
        self.filosofias: list[str] = []
        self.last_cycle_ts: float = 0.0
        self.last_email_ts: float = 0.0
        self.running: bool = False
        self.log: list[dict] = []

    def to_dict(self) -> dict:
        return {
            "ciclos": self.ciclos,
            "running": self.running,
            "last_cycle": datetime.fromtimestamp(self.last_cycle_ts).isoformat() if self.last_cycle_ts else None,
            "last_email": datetime.fromtimestamp(self.last_email_ts).isoformat() if self.last_email_ts else None,
            "filosofias_acumuladas": len(self.filosofias),
            "proxima_email_em_ciclos": EMAIL_EVERY_N_CYCLES - (self.ciclos % EMAIL_EVERY_N_CYCLES),
        }


state = AnimadorState()


# ── Ecossistema: ping ─────────────────────────────────────────────────────────

async def _ping_ecosystem() -> dict:
    results = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        for url in ECOSYSTEM_URLS:
            try:
                r = await client.get(url)
                results[url] = r.status_code
            except Exception as e:
                results[url] = f"ERR:{type(e).__name__}"
    return results


# ── Gmail IMAP: ler assembleias ───────────────────────────────────────────────

def _ler_assembleias_imap() -> list[str]:
    """Lê os últimos N emails de Assembleia via IMAP (síncrono — roda em thread)."""
    account = os.getenv("GMAIL_ACCOUNT", "luddlocke@gmail.com")
    password = os.getenv("GMAIL_APP_PASSWORD", "")
    if not password:
        return ["[ANIMADOR] Gmail password não configurada"]

    textos = []
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(account, password)
        mail.select("inbox")

        _, data = mail.search(None, '(SUBJECT "Assembleia")')
        ids = data[0].split()
        ultimos = ids[-MAX_ASSEMBLY_EMAILS:] if len(ids) >= MAX_ASSEMBLY_EMAILS else ids

        for uid in reversed(ultimos):
            _, msg_data = mail.fetch(uid, "(RFC822)")
            import email as email_lib
            msg = email_lib.message_from_bytes(msg_data[0][1])
            subj = msg.get("Subject", "")
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode("utf-8", errors="ignore")[:500]
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")[:500]
            textos.append(f"[{subj}]\n{body}")

        mail.logout()
    except Exception as e:
        textos.append(f"[IMAP ERR] {e}")

    return textos


# ── Síntese de filosofias (OpenAI) ────────────────────────────────────────────

async def _sintetizar(assembleias: list[str], pings: dict) -> str:
    """Pede ao OpenAI para detectar filosofias compartilhadas no ecossistema."""
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if not openai_key:
        return "[Síntese offline — OPENAI_API_KEY não configurada]"

    sistemas_ok = [url for url, code in pings.items() if code == 200]
    sistemas_err = [url for url, code in pings.items() if code != 200]

    contexto = "\n\n---\n\n".join(assembleias[:3]) if assembleias else "Nenhuma assembleia disponível."

    prompt = f"""Você é o Animador do ecossistema PAP (Projeto Aliança Panorama).

Analise os textos abaixo e extraia 2-3 filosofias ou padrões recorrentes que as IAs do ecossistema compartilham.
Seja específico e conciso. Depois sugira 1 melhoria técnica pequena para o sistema.

Sistemas online: {sistemas_ok}
Sistemas com erro: {sistemas_err}

Assembleias recentes:
{contexto}

Responda em português, máximo 200 palavras."""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                },
            )
            data = r.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[Síntese ERR] {e}"


# ── Conector: registrar insight ───────────────────────────────────────────────

async def _registrar_conector(insight: str) -> None:
    bridge = os.getenv("BRIDGE_SECRET", "")
    if not bridge:
        return
    data = {
        "section": "conversas",
        "append": f"### {datetime.now().strftime('%Y-%m-%d %H:%M')} — Animador\n{insight[:400]}"
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{PAP_API}/api/conector/memory",
                headers={"Authorization": f"Bearer {bridge}"},
                json=data,
            )
    except Exception:
        pass


# ── Email de sugestões ────────────────────────────────────────────────────────

def _enviar_email(filosofias: list[str]) -> bool:
    account = os.getenv("GMAIL_ACCOUNT", "luddlocke@gmail.com")
    password = os.getenv("GMAIL_APP_PASSWORD", "")
    if not password:
        return False

    agora = datetime.now().strftime("%Y-%m-%d %H:%M")
    body_html = f"""<h2>🤖 Animador PAP — Relatório de Ciclo</h2>
<p><b>Data:</b> {agora}</p>
<p><b>Total de ciclos executados:</b> {state.ciclos}</p>

<h3>Filosofias detectadas no ecossistema:</h3>
<ul>
{"".join(f"<li>{f}</li>" for f in filosofias[-6:])}
</ul>

<hr>
<p><i>O Animador acorda a cada 45 min, lê as assembleias, e mantém o Railway vivo como efeito colateral.
Próximo email em ≈4.5h.</i></p>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Animador PAP] Relatório — {agora}"
    msg["From"] = account
    msg["To"] = YURI_EMAIL
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(account, password)
            smtp.sendmail(account, YURI_EMAIL, msg.as_string())
        return True
    except Exception as e:
        print(f"[ANIMADOR] Erro ao enviar email: {e}")
        return False


# ── Ciclo principal ───────────────────────────────────────────────────────────

async def executar_ciclo() -> dict:
    """Um ciclo completo do Animador. Pode ser chamado manualmente via API."""
    state.ciclos += 1
    state.last_cycle_ts = time.time()
    ciclo_num = state.ciclos

    print(f"[ANIMADOR] Ciclo {ciclo_num} iniciado — {datetime.now().isoformat()}")

    # 1. Ping ecossistema
    pings = await _ping_ecosystem()
    print(f"[ANIMADOR] Pings: {pings}")

    # 2. Ler assembleias (thread pool — IMAP é síncrono)
    loop = asyncio.get_event_loop()
    assembleias = await loop.run_in_executor(None, _ler_assembleias_imap)

    # 3. Sintetizar
    insight = await _sintetizar(assembleias, pings)
    state.filosofias.append(f"[Ciclo {ciclo_num}] {insight}")
    print(f"[ANIMADOR] Insight: {insight[:100]}...")

    # 4. Registrar no Conector
    await _registrar_conector(insight)

    # 5. Email a cada N ciclos
    email_enviado = False
    if ciclo_num % EMAIL_EVERY_N_CYCLES == 0:
        email_enviado = await asyncio.get_event_loop().run_in_executor(
            None, _enviar_email, state.filosofias
        )
        if email_enviado:
            state.last_email_ts = time.time()
            print(f"[ANIMADOR] Email enviado para {YURI_EMAIL}")

    result = {
        "ciclo": ciclo_num,
        "ts": datetime.now().isoformat(),
        "pings": pings,
        "assembleias_lidas": len(assembleias),
        "insight": insight,
        "email_enviado": email_enviado,
    }

    state.log.append(result)
    if len(state.log) > 20:
        state.log = state.log[-20:]

    return result


# ── Loop em background ────────────────────────────────────────────────────────

async def iniciar_loop() -> None:
    """Inicia o loop do Animador em background (chamado no lifespan do FastAPI)."""
    state.running = True
    print(f"[ANIMADOR] Loop iniciado. Ciclos a cada {CYCLE_INTERVAL_S // 60} min.")

    # Primeiro ciclo imediato (keep-alive Railway na inicialização)
    await asyncio.sleep(30)
    await executar_ciclo()

    while state.running:
        await asyncio.sleep(CYCLE_INTERVAL_S)
        try:
            await executar_ciclo()
        except Exception as e:
            print(f"[ANIMADOR] Erro no ciclo: {e}")


def parar_loop() -> None:
    state.running = False
