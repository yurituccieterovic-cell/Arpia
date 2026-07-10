"""
Socoboy — Bot Telegram da Arpia
Roda como worker separado no Railway (Procfile worker process).

Config necessária (Railway Variables):
  TELEGRAM_TOKEN    — obtido via @BotFather
  TELEGRAM_ADMIN_ID — ID numérico do Yuri (use @userinfobot para descobrir)
  DATABASE_URL      — mesma variável do processo web
  ANTHROPIC_API_KEY — para respostas inteligentes

Comandos disponíveis:
  /start         — apresentação e boas-vindas
  /chat <msg>    — envia mensagem para a IA e recebe resposta
  /meky <fac_id> — envia comando para a MEKY via vision socket
  /status        — saúde do sistema (DB + MEKY + eco-log)
  /admin         — painel de administração (só TELEGRAM_ADMIN_ID)
"""
import asyncio, logging, os, sys
sys.path.insert(0, "/root/Arpia")

from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from app.core.config import get_settings

log = logging.getLogger("socoboy")


# ─── Helpers ─────────────────────────────────────────────────────────────────
def is_admin(update: Update, cfg) -> bool:
    return update.effective_user.id == cfg.telegram_admin_id


async def _ai_reply(text: str, cfg) -> str:
    """Chama Claude ou Gemini sem persistência (modo bot)."""
    if cfg.anthropic_api_key:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=cfg.anthropic_api_key)
        resp = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": text}],
        )
        return resp.content[0].text
    if cfg.gemini_api_key:
        import google.generativeai as genai
        genai.configure(api_key=cfg.gemini_api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        resp = await model.generate_content_async(text)
        return resp.text
    return "Nenhuma API de IA configurada. Defina ANTHROPIC_API_KEY ou GEMINI_API_KEY."


def _meky_cmd(linha: str, cfg) -> bool:
    """Envia comando direto para MEKY via Unix socket da Amanda."""
    import socket as sock
    try:
        with sock.socket(sock.AF_UNIX, sock.SOCK_STREAM) as s:
            s.connect(cfg.meky_vision_socket)
            s.sendall(linha.encode() + b"\n")
        return True
    except Exception as e:
        log.warning("MEKY socket error: %s", e)
        return False


# ─── Handlers ─────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cfg = get_settings()
    nome = update.effective_user.first_name
    await update.message.reply_text(
        f"Oi {nome}! Sou o Socoboy, assistente do ecossistema Tucci.\n\n"
        f"Comandos:\n"
        f"  /chat <mensagem> — falar com a IA\n"
        f"  /meky <ID 1-200> — controlar rosto da MEKY\n"
        f"  /status — saúde do sistema\n"
        f"{'  /admin — painel admin' if is_admin(update, cfg) else ''}"
    )


async def cmd_chat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cfg = get_settings()
    texto = " ".join(ctx.args)
    if not texto:
        await update.message.reply_text("Uso: /chat <mensagem>")
        return
    await update.message.reply_chat_action("typing")
    try:
        resposta = await _ai_reply(texto, cfg)
        await update.message.reply_text(resposta[:4096])  # Telegram limit
    except Exception as e:
        await update.message.reply_text(f"Erro: {e}")


async def cmd_meky(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cfg = get_settings()
    if not ctx.args:
        await update.message.reply_text("Uso: /meky <ID 1-200>")
        return
    arg = ctx.args[0].upper()
    linha = f"#FAC:{arg}"
    ok = _meky_cmd(linha, cfg)
    if ok:
        await update.message.reply_text(f"✓ MEKY: {linha}")
    else:
        await update.message.reply_text("MEKY offline ou socket indisponível.")


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cfg = get_settings()
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text as sql_text
    db_ok = False
    try:
        eng = create_async_engine(cfg.database_url, pool_pre_ping=True)
        async with eng.connect() as conn:
            await conn.execute(sql_text("SELECT 1"))
        db_ok = True
        await eng.dispose()
    except Exception:
        pass

    import socket as sock, os
    meky_ok = os.path.exists(cfg.meky_vision_socket)

    await update.message.reply_text(
        f"🟢 Arpia: online\n"
        f"{'🟢' if db_ok else '🔴'} Manga (DB): {'ok' if db_ok else 'offline'}\n"
        f"{'🟢' if meky_ok else '🟡'} MEKY socket: {'disponível' if meky_ok else 'sem socket'}"
    )


async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cfg = get_settings()
    if not is_admin(update, cfg):
        await update.message.reply_text("Acesso restrito.")
        return
    await update.message.reply_text(
        "Painel Admin:\n"
        "/meky TEST — autoteste de expressões\n"
        "/meky 1-200 — expressão específica\n"
        "Mais comandos em desenvolvimento."
    )


async def fallback_mensagem(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Mensagem sem comando → responde com IA diretamente."""
    cfg = get_settings()
    texto = update.message.text
    await update.message.reply_chat_action("typing")
    try:
        resposta = await _ai_reply(texto, cfg)
        await update.message.reply_text(resposta[:4096])
    except Exception as e:
        await update.message.reply_text(f"Erro: {e}")


# ─── Entrypoint ───────────────────────────────────────────────────────────────
def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s"
    )
    cfg = get_settings()
    if not cfg.telegram_token:
        log.error("TELEGRAM_TOKEN não configurado. Socoboy não pode iniciar.")
        sys.exit(1)

    app = Application.builder().token(cfg.telegram_token).build()

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("chat",   cmd_chat))
    app.add_handler(CommandHandler("meky",   cmd_meky))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("admin",  cmd_admin))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_mensagem))

    log.info("Socoboy iniciando polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
