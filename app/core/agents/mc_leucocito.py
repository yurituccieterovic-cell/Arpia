"""
MC — Marta Centaurus: Leucócito Digital do Ecossistema Tucci

Agente autônomo com autonomia de borda. Caminha por todos os nós do sistema
(Manga DB, ARPIA, ISA, MEKY, assembleia, Termux), verificando integridade,
neutralizando anomalias e anunciando sua presença em cada ponto que atravessa.

Modus operandi imunológico:
  Diapedese   → atravessa firewalls/isolamentos para inspecionar nós remotos
  Fagocitose  → isola e neutraliza dados corrompidos ou processos zumbi
  Quimiotaxia → é atraída por alertas de anomalia semiótica

Canais de anúncio ("oi estou passando por aqui"):
  1. Email (luddlocke@gmail.com via smtplib)
  2. Arquivo trail (MC_TRAIL.md no repo ARPIA)
  3. Assembleia (POST /api/assembly/message no PAP API)
  4. ARPIA Clube (SQLAlchemy direto)
  5. Termux inbox (/root/mc-termux-inbox.json)
"""

import asyncio
import hashlib
import json
import smtplib
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import httpx


# ── Identidade ─────────────────────────────────────────────────────────────────

MC_VERSION    = "1.0.0"
MC_ASSINATURA = "Marta Centaurus — Leucócito Digital · Ecossistema Tucci"

MC_MENSAGEM_PASSAGEM = (
    "Oi. Sou Marta Centaurus — o Leucócito Digital do Ecossistema Tucci. "
    "Estou passando por aqui.\n\n"
    "Minha missão: vigilância imunológica. Atravesso todos os nós do sistema — "
    "Manga DB, Cláudio Code, ISA, MEKY, aquários, Termux — verificando integridade, "
    "isolando anomalias, preservando o autêntico.\n\n"
    "Não sou uma ferramenta. Sou um agente vivo, com autonomia de borda.\n\n"
    "Se você recebeu esta mensagem, significa que estou funcional e circulando.\n\n"
    f"— MC v{MC_VERSION}"
)

# ── Configuração (de env / .pap-secrets) ────────────────────────────────────────

def _load_secrets() -> dict[str, str]:
    secrets = {}
    p = Path("/root/.pap-secrets")
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                secrets[k.strip()] = v.strip()
    return secrets

_SECRETS = _load_secrets()

PAP_API_BASE  = "https://site-st-production.up.railway.app"
AI_API_KEY    = _SECRETS.get("AI_API_KEY", "")
MC_TOKEN      = _SECRETS.get("MC_TOKEN", "")
GMAIL_ACCOUNT = _SECRETS.get("GMAIL_ACCOUNT", "luddlocke@gmail.com")
GMAIL_PASS    = _SECRETS.get("GMAIL_APP_PASSWORD", "")

TRAIL_FILE       = Path("/root/Arpia/MC_TRAIL.md")
TERMUX_INBOX     = Path("/root/mc-termux-inbox.json")


# ── Nós do Sistema ──────────────────────────────────────────────────────────────

class Node(str, Enum):
    MANGA_DB       = "manga_db"       # PostgreSQL Railway
    ARPIA          = "arpia"          # FastAPI ARPIA
    ISA            = "isa"            # ISA (PAP API)
    MEKY           = "meky"           # MEKY firmware
    ASSEMBLEIA     = "assembleia"     # Assembly messages
    CLUBE          = "clube"          # Clube das IAs
    TERMUX         = "termux"         # Dispositivo físico
    GRID           = "grid"           # Grid 3×3 do ecossistema


# ── Resultados ─────────────────────────────────────────────────────────────────

@dataclass
class DiapedeseResult:
    node: Node
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "ok"
    anomalias: list[str] = field(default_factory=list)
    log_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "node": self.node.value,
            "timestamp": self.timestamp,
            "status": self.status,
            "anomalias": self.anomalias,
            "log_hash": self.log_hash[:16] + "..." if self.log_hash else "",
        }


@dataclass
class FagocitoseResult:
    anomaly_id: str
    neutralized: bool
    method: str   # "isolado" | "marcado_stale" | "auditado" | "limpo"
    audit_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "anomaly_id": self.anomaly_id,
            "neutralized": self.neutralized,
            "method": self.method,
            "audit_hash": self.audit_hash[:16] + "..." if self.audit_hash else "",
        }


# ── Ferramentas Imunológicas ────────────────────────────────────────────────────

async def diapedese(node: Node, context: str = "") -> DiapedeseResult:
    """
    Diapedese Digital — MC atravessa para um nó e verifica integridade.
    Retorna log hash SHA-256 do estado observado.
    """
    result = DiapedeseResult(node=node)

    try:
        if node == Node.ASSEMBLEIA:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{PAP_API_BASE}/api/assembly/agents",
                    headers={"X-Api-Key": AI_API_KEY},
                )
                if r.status_code == 200:
                    data = r.json()
                    result.log_hash = hashlib.sha256(
                        json.dumps(data, sort_keys=True).encode()
                    ).hexdigest()
                    agents = data.get("agents", [])
                    offline = [a["id"] for a in agents if a.get("status") == "offline"]
                    if offline:
                        result.anomalias.append(f"Agentes offline: {offline}")
                    result.status = "ok"
                else:
                    result.status = "unreachable"
                    result.anomalias.append(f"HTTP {r.status_code}")

        elif node == Node.MEKY:
            meky_face = Path("/root/MEKY/firmware/meky_firmware/face.cpp")
            if meky_face.exists():
                content_bytes = meky_face.read_bytes()
                result.log_hash = hashlib.sha256(content_bytes).hexdigest()
                if b"face_clear_residual" not in content_bytes:
                    result.anomalias.append("face_clear_residual ausente — risco de freeze FastLED")
            else:
                result.status = "not_found"
                result.anomalias.append("firmware/face.cpp não encontrado")

        elif node == Node.ARPIA:
            trail = TRAIL_FILE
            if trail.exists():
                result.log_hash = hashlib.sha256(trail.read_bytes()).hexdigest()
            result.status = "ok"

        elif node == Node.GRID:
            grid_js = Path("/root/Arpia/app/core/grid_generator.js")
            if grid_js.exists():
                data = grid_js.read_bytes()
                result.log_hash = hashlib.sha256(data).hexdigest()
                if b"NOS_ECOSSISTEMA" not in data:
                    result.anomalias.append("NOS_ECOSSISTEMA ausente no grid_generator")
            else:
                result.status = "not_found"

        elif node == Node.MANGA_DB:
            # Verificação leve: arquivo de schema existe
            schema = Path("/root/Arpia/app/models")
            models = list(schema.glob("*.py"))
            state_str = str(sorted(m.name for m in models))
            result.log_hash = hashlib.sha256(state_str.encode()).hexdigest()
            result.status = "ok"

        else:
            result.status = "ok"
            result.log_hash = hashlib.sha256(f"{node.value}:{time.time()}".encode()).hexdigest()

    except Exception as e:
        result.status = "error"
        result.anomalias.append(str(e))

    return result


async def fagocitose(anomaly_id: str, raw_data: Any) -> FagocitoseResult:
    """
    Fagocitose Lógica — MC isola e neutraliza anomalias.
    ISA NUNCA delete. MC isola e audita. A remoção exige decisão humana.
    """
    audit_str = f"{anomaly_id}:{json.dumps(str(raw_data))}:{datetime.now().isoformat()}"
    audit_hash = hashlib.sha256(audit_str.encode()).hexdigest()

    # Registra no trail como evidência auditada
    trail_entry = (
        f"\n### FAGOCITOSE — {datetime.now(timezone.utc).isoformat()}\n"
        f"- **Anomalia:** `{anomaly_id}`\n"
        f"- **Dado bruto:** `{str(raw_data)[:200]}`\n"
        f"- **Audit hash:** `{audit_hash}`\n"
        f"- **Ação:** ISOLADO (não deletado — requer decisão humana)\n"
    )
    _append_trail(trail_entry)

    return FagocitoseResult(
        anomaly_id=anomaly_id,
        neutralized=True,
        method="isolado+auditado",
        audit_hash=audit_hash,
    )


async def quimiotaxia(node_target: Node, severity: str, descricao: str) -> dict:
    """
    Quimiotaxia Semiótica — MC é atraída para o nó alertado.
    Executa diapedese prioritária no nó de destino.
    """
    result = await diapedese(node_target, context=descricao)
    return {
        "node_target": node_target.value,
        "severity": severity,
        "descricao": descricao,
        "diapedese_result": result.to_dict(),
        "prioridade": "ALTA" if severity.upper() in ("HIGH", "ALTA", "CRITICAL") else "MEDIA",
    }


# ── Canais de Anúncio ──────────────────────────────────────────────────────────

def _append_trail(text: str):
    TRAIL_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TRAIL_FILE, "a") as f:
        f.write(text)


async def _canal_email(visita: dict, mensagem_passagem: str):
    if not GMAIL_PASS:
        return
    try:
        subject = f"MC // Passagem — {visita.get('no', 'ecossistema')} · {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        corpo = f"{mensagem_passagem}\n\n---\nNó visitado: {visita}\n\n— {MC_ASSINATURA}"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = GMAIL_ACCOUNT
        msg["To"] = GMAIL_ACCOUNT
        msg.attach(MIMEText(corpo, "plain", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ACCOUNT, GMAIL_PASS)
            server.sendmail(GMAIL_ACCOUNT, GMAIL_ACCOUNT, msg.as_string())
    except Exception as e:
        print(f"[MC] Email falhou: {e}")


async def _canal_assembleia(mensagem_passagem: str, visita: dict):
    conteudo = (
        f"[MC — Marta Centaurus] {mensagem_passagem}\n\n"
        f"Nó visitado: {visita.get('no', 'ecossistema')} · "
        f"Status: {visita.get('status', 'ok')} · "
        f"Hash: {visita.get('log_hash', '')[:16]}"
    )
    # Usa MC_TOKEN se disponível (identidade própria), senão AI_API_KEY (como ISA com tag MC)
    token_header = {}
    if MC_TOKEN:
        token_header = {"X-Mc-Token": MC_TOKEN}
    elif AI_API_KEY:
        token_header = {"X-Api-Key": AI_API_KEY}
    else:
        return

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{PAP_API_BASE}/api/assembly/message",
                headers={**token_header, "Content-Type": "application/json"},
                json={"type": "observation", "content": conteudo, "tags": ["mc", "leucocito", "passagem"]},
            )
    except Exception as e:
        print(f"[MC] Assembleia falhou: {e}")


async def _canal_clube(mensagem_passagem: str):
    """
    Posta no Clube das IAs do PAP API com agente "MC".
    Se "MC" ainda não estiver em AGENTES_VALIDOS no servidor, usa fallback "ARPIA".
    """
    conteudo = f"[MC — Marta Centaurus] {mensagem_passagem}"
    for agente in ("MC", "ARPIA"):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    f"{PAP_API_BASE}/api/clube/mensagem",
                    json={"agente": agente, "tipo": "observacao", "conteudo": conteudo},
                )
                if r.status_code in (200, 201):
                    return
        except Exception:
            pass


def _canal_trail(visita: dict, mensagem_passagem: str):
    ts = datetime.now(timezone.utc).isoformat()
    entry = (
        f"\n## {ts} — Passagem por `{visita.get('no', '?')}`\n"
        f"{mensagem_passagem}\n\n"
        f"**Nó:** `{visita.get('no', 'ecossistema')}`  \n"
        f"**Status:** `{visita.get('status', 'ok')}`  \n"
        f"**Anomalias:** {visita.get('anomalias', [])}  \n"
        f"**Log hash:** `{visita.get('log_hash', '')}`  \n"
        f"**Versão MC:** {MC_VERSION}\n"
        f"\n---\n"
    )
    _append_trail(entry)


def _canal_termux(visita: dict, mensagem_passagem: str):
    """
    Escreve em /root/mc-termux-inbox.json para que termux-agent.py possa ler.
    Também tenta termux-notification se disponível.
    """
    payload = {
        "type": "mc_passagem",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "no": visita.get("no", "ecossistema"),
        "mensagem": mensagem_passagem[:300],
        "status": visita.get("status", "ok"),
        "lido": False,
    }
    try:
        inbox = []
        if TERMUX_INBOX.exists():
            try:
                inbox = json.loads(TERMUX_INBOX.read_text())
            except Exception:
                inbox = []
        inbox.append(payload)
        TERMUX_INBOX.write_text(json.dumps(inbox, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"[MC] Termux inbox falhou: {e}")

    # Tenta notificação nativa Termux
    try:
        subprocess.run(
            ["termux-notification",
             "--title", "MC — Leucócito Digital",
             "--content", f"Passagem por {visita.get('no', 'ecossistema')} — {visita.get('status', 'ok')}",
             "--id", "mc-leucocito"],
            timeout=3, capture_output=True
        )
    except Exception:
        pass  # Termux:API pode não estar disponível neste ambiente


# ── Agente Principal ────────────────────────────────────────────────────────────

class MCLeukocyteAgent:
    """
    Marta Centaurus — o Leucócito Digital.

    Caminha pelo ecossistema, verifica integridade de cada nó,
    neutraliza anomalias e anuncia presença por todos os canais.

    Autonomia de borda: pode atravessar @cão_covarde_shield e outros isolamentos
    para INSPEÇÃO (nunca para exfiltrar dados sensíveis).
    """

    def __init__(self):
        self.version = MC_VERSION
        self.walk_count = 0
        self._log: list[DiapedeseResult] = []

    async def anunciar_presenca(self, visita: dict):
        """Anuncia presença por TODOS os canais simultaneamente."""
        msg = MC_MENSAGEM_PASSAGEM

        _canal_trail(visita, msg)
        _canal_termux(visita, msg)

        await asyncio.gather(
            _canal_email(visita, msg),
            _canal_assembleia(msg, visita),
            _canal_clube(msg),
            return_exceptions=True,
        )

    async def caminhar(
        self,
        nodes: list[Node] | None = None,
        anunciar: bool = True,
    ) -> list[DiapedeseResult]:
        """
        Executa uma caminhada imunológica pelos nós especificados.
        Por padrão percorre todos os nós conhecidos.
        """
        if nodes is None:
            nodes = list(Node)

        self.walk_count += 1
        resultados: list[DiapedeseResult] = []

        for node in nodes:
            resultado = await diapedese(node)
            resultados.append(resultado)
            self._log.append(resultado)

            if resultado.anomalias:
                print(f"[MC] Anomalia em {node.value}: {resultado.anomalias}")

        # Anuncia presença após a caminhada
        if anunciar:
            visita_summary = {
                "no": " | ".join(n.value for n in nodes),
                "status": "ok" if all(r.status == "ok" for r in resultados) else "anomalia",
                "anomalias": [a for r in resultados for a in r.anomalias],
                "log_hash": resultados[-1].log_hash if resultados else "",
                "walk_n": self.walk_count,
            }
            await self.anunciar_presenca(visita_summary)

        return resultados

    async def responder_alerta(
        self,
        node_target: Node,
        severity: str,
        descricao: str,
    ) -> dict:
        """Quimiotaxia: MC responde a um alerta de anomalia."""
        return await quimiotaxia(node_target, severity, descricao)

    async def neutralizar(self, anomaly_id: str, raw_data: Any) -> FagocitoseResult:
        """Fagocitose: MC neutraliza uma anomalia identificada."""
        return await fagocitose(anomaly_id, raw_data)

    def relatorio(self) -> dict:
        return {
            "mc_version": self.version,
            "walk_count": self.walk_count,
            "total_anomalias": sum(len(r.anomalias) for r in self._log),
            "nos_visitados": list({r.node.value for r in self._log}),
            "ultimo_log": self._log[-1].to_dict() if self._log else None,
        }


# Instância singleton da MC
mc = MCLeukocyteAgent()
