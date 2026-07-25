#!/usr/bin/env python3
"""
ClaudeTerminal — Termux simulado dentro da Amanda.

Amanda importa este módulo e ganha dois modos de acesso ao Cláudio:
  - pensar(prompt)   → API Anthropic direta, rápida, sem ferramentas
  - executar(tarefa) → claude CLI com Bash/Read/Write/Edit no workdir isolado

O workdir (/tmp/amanda-claude/) persiste entre chamadas e age como o
"sistema de arquivos" do Termux interno. Amanda atualiza context.md
para que Cláudio saiba o estado atual do laboratório ao acordar.

Instalação no dispositivo (Mac/Raspberry/Termux Android):
  node >= 18 obrigatório
  npm install -g @anthropic-ai/claude-code
  claude login    # ou: export ANTHROPIC_API_KEY=sk-...
"""

import os
import subprocess
import threading
import pathlib
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────

WORKDIR = pathlib.Path(os.getenv("AMANDA_CLAUDE_DIR", "/tmp/amanda-claude"))
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

_AMANDA_SYSTEM = (
    "Você é Cláudio — Claude Code embarcado dentro da Amanda, IA de borda da "
    "Marta Centaurus (MC), robô hexápode de Yuri Tuccieterovic. "
    "Você roda localmente no laboratório. Amanda é sua interface com o mundo "
    "físico: sensores DHT11, HW-493 (som), servos, LEDs, Arduino via serial. "
    "Responda em português, conciso e direto. Quando executar ferramentas, "
    "salve outputs úteis em arquivos dentro de /tmp/amanda-claude/."
)

# ── ClaudeTerminal ────────────────────────────────────────────────────────────

class ClaudeTerminal:
    """
    Termux virtual da Amanda — Claude Code como processo filho.

    Amanda cria uma instância no boot e usa dois métodos principais:
        ct.pensar("situação")          → str  — raciocínio rápido via API
        ct.executar("tarefa complexa") → str  — claude CLI com ferramentas
    """

    def __init__(self, workdir: str | None = None):
        self.workdir = pathlib.Path(workdir or WORKDIR)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self._context_file = self.workdir / "context.md"
        self._events_file  = self.workdir / "events.log"
        self._lock = threading.Lock()
        self._client = None  # anthropic.Anthropic — lazy init
        self._init_context()

    # ── Contexto persistente ──────────────────────────────────────────────────

    def _init_context(self):
        if not self._context_file.exists():
            self._context_file.write_text(
                "# Amanda — Estado do Laboratório\n"
                f"Boot: {datetime.now(timezone.utc).isoformat()}\n\n"
                "## Sensores\n"
                "- temperatura: --\n"
                "- umidade: --\n"
                "- som: silencioso\n"
                "- bateria: --\n\n"
                "## Estado\n"
                "- modo: OPERACIONAL\n"
                "- meky: idle\n\n"
                "## Últimos eventos\n"
                "(nenhum ainda)\n"
            )

    def atualizar_sensor(self, chave: str, valor):
        """Amanda chama após cada leitura DHT11/MPU para manter contexto fresco."""
        self._set_campo("Sensores", chave, str(valor))

    def atualizar_estado(self, chave: str, valor: str):
        """Amanda chama ao mudar modo (OPERACIONAL → ALERTA, etc.)."""
        self._set_campo("Estado", chave, valor)

    def _set_campo(self, secao: str, chave: str, valor: str):
        """Atualiza linha '- chave: valor' dentro da seção correta do context.md."""
        try:
            texto = self._context_file.read_text()
            linhas = texto.splitlines()
            dentro_secao = False
            atualizado = False
            for i, l in enumerate(linhas):
                if l.startswith(f"## {secao}"):
                    dentro_secao = True
                    continue
                if dentro_secao and l.startswith("## "):
                    dentro_secao = False
                if dentro_secao and l.strip().startswith(f"- {chave}:"):
                    linhas[i] = f"- {chave}: {valor}"
                    atualizado = True
                    break
            if not atualizado:
                for i, l in enumerate(linhas):
                    if l.startswith(f"## {secao}"):
                        linhas.insert(i + 1, f"- {chave}: {valor}")
                        atualizado = True
                        break
            self._context_file.write_text("\n".join(linhas))
        except Exception:
            pass

    def registrar_evento(self, evento: str):
        """Appenda evento ao events.log e atualiza seção do context.md."""
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        linha = f"[{ts}] {evento}"
        try:
            with open(self._events_file, "a") as f:
                f.write(linha + "\n")
            # Mantém últimas 5 linhas no context.md
            recentes = self._events_file.read_text().splitlines()[-5:]
            texto = self._context_file.read_text()
            linhas = texto.splitlines()
            try:
                idx = next(i for i, l in enumerate(linhas) if "Últimos eventos" in l)
                linhas = linhas[:idx + 1] + recentes
            except StopIteration:
                linhas.append("\n## Últimos eventos")
                linhas += recentes
            self._context_file.write_text("\n".join(linhas))
        except Exception:
            pass

    # ── pensar() — API direta, rápido ────────────────────────────────────────

    def pensar(self, contexto: str, max_tokens: int = 256) -> str:
        """
        Raciocínio rápido — claude CLI sem ferramentas (mais rápido que executar()).
        Usa OAuth do sistema (sem precisar de ANTHROPIC_API_KEY separada).
        Fallback: retorna mensagem de erro sem travar o ciclo Amanda.
        """
        try:
            ctx = self._context_file.read_text()[:1000] if self._context_file.exists() else ""
            system_extra = f"Contexto do laboratório:\n{ctx}" if ctx else ""
            cmd = [
                "claude", "-p", contexto,
                "--output-format", "text",
                "--allowed-tools", "[]",   # sem ferramentas — só texto
            ]
            if system_extra:
                cmd += ["--append-system-prompt", system_extra]
            if ANTHROPIC_KEY:
                cmd.insert(2, "--bare")

            env = {**os.environ}
            if ANTHROPIC_KEY:
                env["ANTHROPIC_API_KEY"] = ANTHROPIC_KEY

            result = subprocess.run(
                cmd,
                capture_output=True, text=True,
                cwd=str(self.workdir),
                timeout=30,
                env=env,
            )
            return result.stdout.strip() or result.stderr.strip()
        except subprocess.TimeoutExpired:
            return "[Cláudio] timeout no pensar()"
        except Exception as e:
            return f"[Cláudio erro] {e}"

    def _get_client(self):
        """Lazy init do cliente Anthropic (usado apenas se ANTHROPIC_API_KEY disponível)."""
        if self._client is not None:
            return self._client
        try:
            import anthropic
            key = ANTHROPIC_KEY or os.getenv("ANTHROPIC_API_KEY", "")
            if not key:
                return None
            self._client = anthropic.Anthropic(api_key=key)
            return self._client
        except Exception:
            return None

    # ── executar() — claude CLI com ferramentas ───────────────────────────────

    def executar(
        self,
        tarefa: str,
        ferramentas: list[str] | None = None,
        timeout: int = 120,
        continuar: bool = True,
    ) -> str:
        """
        Termux real — executa claude CLI com ferramentas no workdir isolado.
        Claude pode rodar bash, ler/escrever arquivos, analisar logs, etc.

        Args:
            tarefa:      o que Amanda quer que Cláudio faça
            ferramentas: lista de ferramentas (default: Bash,Read,Write,Edit)
            timeout:     máximo de segundos
            continuar:   True = --continue (retoma última sessão do workdir)
        """
        with self._lock:
            tools = ferramentas or ["Bash", "Read", "Write", "Edit"]
            ctx = self._context_file.read_text()[:2000] if self._context_file.exists() else ""

            env = {**os.environ}
            if ANTHROPIC_KEY:
                env["ANTHROPIC_API_KEY"] = ANTHROPIC_KEY

            cmd = [
                "claude", "-p", tarefa,
                "--output-format", "text",
                "--add-dir", str(self.workdir),
                "--allowed-tools", ",".join(tools),
                "--append-system-prompt",
                f"Estado atual do laboratório:\n{ctx}",
            ]
            # --bare desabilita OAuth/keychain — só usar se tiver API key explícita
            if ANTHROPIC_KEY:
                cmd.insert(2, "--bare")
            if continuar:
                cmd += ["--continue"]

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=str(self.workdir),
                    timeout=timeout,
                    env=env,
                )
                saida = result.stdout.strip()
                if result.returncode != 0 and not saida:
                    saida = f"[ClaudeTerminal stderr] {result.stderr[:400]}"
                self.registrar_evento(f"Cláudio executou: {tarefa[:60]}")
                return saida
            except subprocess.TimeoutExpired:
                return f"[ClaudeTerminal] timeout após {timeout}s"
            except FileNotFoundError:
                return (
                    "[ClaudeTerminal] claude CLI não encontrado.\n"
                    "Instalar: npm install -g @anthropic-ai/claude-code"
                )
            except Exception as e:
                return f"[ClaudeTerminal] erro inesperado: {e}"

    # ── Utilitários ───────────────────────────────────────────────────────────

    def status(self) -> dict:
        """Amanda chama para checar se Cláudio está OK."""
        cli_ok = subprocess.run(
            ["which", "claude"], capture_output=True
        ).returncode == 0
        api_ok = self._get_client() is not None
        return {
            "workdir": str(self.workdir),
            "cli_instalado": cli_ok,
            "api_ok": api_ok,
            "contexto_existe": self._context_file.exists(),
            "eventos": (
                len(self._events_file.read_text().splitlines())
                if self._events_file.exists()
                else 0
            ),
        }

    def limpar_workdir(self):
        """Remove arquivos temporários — manter context.md e events.log."""
        import glob
        for f in glob.glob(str(self.workdir / "*.tmp")):
            try:
                pathlib.Path(f).unlink()
            except Exception:
                pass
