#!/usr/bin/env python3
"""
video_pipeline.py — Módulo de geração de vídeos para o Ecossistema Tucci

Especificação (Motion Graphics v2 — Sessão 50):
  - Formato: 1080×1080 quadrado (Instagram / YouTube Shorts)
  - Narração: edge-tts pt-BR-AntonioNeural, fala por cena
  - Imagens: Pollinations.ai Flux, 1080×1080, prompt temático por cena
  - Overlay: Pillow — gradiente base+topo, texto centralizado, linha decorativa
  - Animação: zoompan Ken Burns + fade in/out por segmento
  - Transição: xfade + acrossfade encadeado entre todos os cortes
  - Envio: Gmail SMTP luddlocke@gmail.com → destinatário

Uso básico:
    from lib.video_pipeline import VideoScene, gerar_video

    cenas = [
        VideoScene(
            fala="Olá, sou a ISA.",
            prompt="cute owl robot glowing blue, dark background, cinematic, no text",
            texto_overlay="ISA · PAP",
            cor="#00BFFF",
        ),
        ...
    ]
    gerar_video(cenas, titulo="ISA — Relatório do Dia", remetente_nome="ISA")

Compatível com: Amanda, MC, ISA (via bridge), qualquer IA Python do ecossistema.
CLI: python3 -m lib.video_pipeline --json cenas.json --titulo "Título" --nome "Amanda"
"""

from __future__ import annotations

import os, json, time, subprocess, urllib.parse, urllib.request, smtplib, tempfile, argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL = True
except ImportError:
    _PIL = False

# ── Configuração ──────────────────────────────────────────────────────────────

VENV            = Path(os.environ.get("TTS_VENV", "/tmp/venv-video"))
GMAIL_FROM      = os.environ.get("GMAIL_FROM", "luddlocke@gmail.com")
GMAIL_PASS      = os.environ.get("GMAIL_PASS", "ajqp wexr qege ouaq")
GMAIL_TO        = os.environ.get("GMAIL_TO",   "yurituccieterovic@gmail.com")
FADE_DUR        = 0.20   # segundos de crossfade entre cenas
ZOOM_STEP       = 0.0003 # velocidade do zoompan (Ken Burns)
ZOOM_MAX        = 1.05   # zoom máximo (1.05 = 5%)
FPS             = 25

FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]

# ── Modelo de cena ────────────────────────────────────────────────────────────

@dataclass
class VideoScene:
    fala: str          # Texto narrado pela voz sintetizada
    prompt: str        # Prompt de imagem para Pollinations.ai
    texto_overlay: str = ""       # Texto exibido na tela (base da imagem)
    cor: str = "#FFD700"          # Cor do overlay (hex)
    seed: Optional[int] = None    # Seed Pollinations (None = derivado do conteúdo)

# ── Utilitários internos ──────────────────────────────────────────────────────

def _ffprobe_dur(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(r.stdout)["format"]["duration"])

def _hex2rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

def _fonte(size: int) -> "ImageFont":
    for fp in FONTS:
        if Path(fp).exists():
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()

# ── Etapas do pipeline ────────────────────────────────────────────────────────

def _gerar_fala(scene: VideoScene, work: Path, idx: int) -> Path:
    mp3 = work / f"s{idx:02d}_fala.mp3"
    if mp3.exists() and mp3.stat().st_size > 500:
        return mp3
    mp3.unlink(missing_ok=True)
    exe = VENV / "bin/edge-tts"
    if not exe.exists():
        raise RuntimeError(f"edge-tts não encontrado em {exe}. Rode: python3 -m venv {VENV} && {VENV}/bin/pip install edge-tts")
    for _ in range(3):
        try:
            subprocess.run(
                [str(exe), "--voice", "pt-BR-AntonioNeural",
                 "--text", scene.fala, "--write-media", str(mp3)],
                check=True, capture_output=True, timeout=30,
            )
            if mp3.stat().st_size > 500:
                return mp3
            mp3.unlink(missing_ok=True)
        except Exception:
            time.sleep(5)
    raise RuntimeError(f"edge-tts falhou na cena {idx}: {scene.fala!r}")

def _baixar_imagem(scene: VideoScene, work: Path, idx: int) -> Path:
    raw = work / f"s{idx:02d}_raw.jpg"
    if raw.exists() and raw.stat().st_size > 2000:
        return raw
    seed = scene.seed if scene.seed is not None else (abs(hash(scene.fala + scene.prompt[:30])) % 99999)
    enc = urllib.parse.quote(scene.prompt + " no text no letters")
    url = (f"https://image.pollinations.ai/prompt/{enc}"
           f"?width=1080&height=1080&nologo=true&seed={seed}")
    hdrs = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
    for n in range(3):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = resp.read()
            raw.write_bytes(data)
            return raw
        except Exception as e:
            print(f"    [img {idx}] tentativa {n+1}: {e}")
            time.sleep(25 if n > 0 else 8)
    # fallback: fundo escuro sólido
    if _PIL:
        Image.new("RGB", (1080, 1080), (8, 12, 24)).save(raw, "JPEG")
    else:
        raw.write_bytes(b"")  # vazio (ffmpeg vai falhar, mas não travar)
    return raw

def _aplicar_overlay(scene: VideoScene, raw: Path, work: Path, idx: int) -> Path:
    out = work / f"s{idx:02d}_comp.jpg"
    if out.exists():
        return out
    if not _PIL:
        return raw
    img = Image.open(raw).convert("RGB").resize((1080, 1080), Image.LANCZOS)
    # gradientes
    ov = Image.new("RGBA", (1080, 1080), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for y in range(760, 1080):
        od.rectangle([0, y, 1080, y+1], fill=(0, 0, 0, int(230 * (y-760) / 320)))
    for y in range(0, 180):
        od.rectangle([0, y, 1080, y+1], fill=(0, 0, 0, int(130 * (180-y) / 180)))
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    draw = ImageDraw.Draw(img)
    cor = _hex2rgb(scene.cor)
    fn = _fonte(52)
    # linha decorativa topo
    draw.rectangle([60, 56, 260, 61], fill=cor)
    # texto base
    if scene.texto_overlay:
        txt = scene.texto_overlay
        bb = draw.textbbox((0, 0), txt, font=fn)
        x = (1080 - (bb[2] - bb[0])) // 2
        for dx, dy in [(2,2), (-1,1), (1,-1), (0,2)]:
            draw.text((x+dx, 990+dy), txt, font=fn, fill=(0, 0, 0))
        draw.text((x, 990), txt, font=fn, fill=cor)
    img.save(out, "JPEG", quality=93)
    return out

def _criar_segmento(comp: Path, audio: Path, dur: float, work: Path, idx: int) -> Path:
    seg = work / f"seg_{idx:02d}.mp4"
    if seg.exists():
        return seg
    frames   = max(int(dur * FPS), 5)
    fade_d   = min(FADE_DUR, dur * 0.12)
    fade_out = max(dur - fade_d, 0)
    vf = (
        f"scale=1080:1080,"
        f"zoompan=z='min(zoom+{ZOOM_STEP},{ZOOM_MAX})':d={frames}:s=1080x1080,"
        f"fade=t=in:st=0:d={fade_d:.3f},"
        f"fade=t=out:st={fade_out:.3f}:d={fade_d:.3f}"
    )
    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(comp),
        "-i", str(audio),
        "-t", str(dur),
        "-vf", vf,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", str(seg),
    ], check=True, capture_output=True)
    return seg

def _montar_xfade(segs: list[Path], durs: list[float], out: Path) -> Path:
    """Concatena N segmentos com transição xfade+acrossfade."""
    import shutil
    N = len(segs)
    if N == 1:
        shutil.copy(segs[0], out)
        return out

    inputs = []
    for s in segs:
        inputs += ["-i", str(s)]

    fc_v, fc_a = [], []
    off0 = durs[0] - FADE_DUR
    fc_v.append(f"[0:v][1:v]xfade=transition=fade:duration={FADE_DUR}:offset={off0:.3f}[xv01]")
    fc_a.append(f"[0:a][1:a]acrossfade=d={FADE_DUR}[xa01]")
    for i in range(2, N):
        pv = f"xv{i-1:02d}"; pa = f"xa{i-1:02d}"
        cv = f"xv{i:02d}";   ca = f"xa{i:02d}"
        off = sum(durs[:i]) - i * FADE_DUR
        fc_v.append(f"[{pv}][{i}:v]xfade=transition=fade:duration={FADE_DUR}:offset={off:.3f}[{cv}]")
        fc_a.append(f"[{pa}][{i}:a]acrossfade=d={FADE_DUR}[{ca}]")

    last_v = f"xv{N-1:02d}"; last_a = f"xa{N-1:02d}"
    subprocess.run(
        ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", ";".join(fc_v + fc_a),
            "-map", f"[{last_v}]", "-map", f"[{last_a}]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k",
            str(out),
        ],
        check=True, capture_output=True,
    )
    return out

def _enviar_email(video: Path, assunto: str, dest: str, corpo: str) -> None:
    msg = MIMEMultipart()
    msg["From"] = GMAIL_FROM; msg["To"] = dest; msg["Subject"] = assunto
    msg.attach(MIMEText(corpo, "plain", "utf-8"))
    with open(video, "rb") as f:
        part = MIMEBase("video", "mp4")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    nome = video.stem[:40].replace(" ", "_") + ".mp4"
    part.add_header("Content-Disposition", f'attachment; filename="{nome}"')
    msg.attach(part)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_FROM, GMAIL_PASS)
        smtp.sendmail(GMAIL_FROM, dest, msg.as_string())

# ── API pública ───────────────────────────────────────────────────────────────

def gerar_video(
    scenes: list[VideoScene],
    titulo: str,
    remetente_nome: str = "IA",
    dest_email: str | None = None,
    work_dir: Path | None = None,
    enviar: bool = True,
    delay_imgs: float = 4.0,
    corpo_email: str | None = None,
) -> Path:
    """
    Pipeline completo de geração de vídeo motion graphics.

    Args:
        scenes:         Lista de VideoScene com fala, prompt, overlay, cor.
        titulo:         Título do vídeo (usado no email e nome do arquivo).
        remetente_nome: Nome da IA remetente (ISA, Amanda, MEKY, MC…).
        dest_email:     Destinatário (padrão: GMAIL_TO env ou Yuri).
        work_dir:       Diretório de trabalho (criado se None).
        enviar:         Se True, envia por Gmail após gerar.
        delay_imgs:     Segundos entre requisições Pollinations (evita 429).
        corpo_email:    Texto do email (auto-gerado se None).

    Returns:
        Path do arquivo MP4 gerado.
    """
    dest = dest_email or GMAIL_TO
    if work_dir is None:
        work_dir = Path(tempfile.mkdtemp(prefix=f"vid_{remetente_nome.lower()}_"))
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f"[video] {remetente_nome} — {titulo} — {len(scenes)} cenas")

    segs, durs = [], []
    for i, sc in enumerate(scenes):
        print(f"  [{i+1:02d}/{len(scenes)}] {sc.fala[:55]}")
        fala = _gerar_fala(sc, work_dir, i)
        dur  = _ffprobe_dur(fala)
        durs.append(dur)
        img  = _baixar_imagem(sc, work_dir, i)
        comp = _aplicar_overlay(sc, img, work_dir, i)
        seg  = _criar_segmento(comp, fala, dur, work_dir, i)
        segs.append(seg)
        if i < len(scenes) - 1:
            time.sleep(delay_imgs)

    total = sum(durs)
    slug  = titulo[:40].replace(" ", "_").replace("/", "-")
    out   = work_dir / f"{slug}.mp4"
    _montar_xfade(segs, durs, out)

    mb = out.stat().st_size / (1024*1024)
    print(f"  ✓ {out.name} — {mb:.1f} MB, {total:.1f}s, {len(scenes)} cenas")

    if enviar:
        assunto = f"[{remetente_nome}] {titulo}"
        corpo   = corpo_email or (
            f"Olá Yuri,\n\n"
            f"Segue vídeo gerado por {remetente_nome}: {titulo}\n\n"
            f"Cenas: {len(scenes)} | Duração: {total:.0f}s | Tamanho: {mb:.1f} MB\n"
            f"Formato: 1080×1080 (Instagram/YouTube)\n"
            f"Pipeline: edge-tts → Pollinations.ai → Pillow → FFmpeg (zoompan+xfade)\n\n"
            f"— {remetente_nome} / Ecossistema Tucci\n"
        )
        _enviar_email(out, assunto, dest, corpo)
        print(f"  ✓ Email enviado → {dest}")

    return out

# ── Templates prontos para cada IA ───────────────────────────────────────────

def cenas_isa_resumo(data: str, insights: list[str]) -> list[VideoScene]:
    """Template ISA: resumo diário de aprendizados."""
    scenes = [
        VideoScene(
            fala=f"Olá. Sou a ISA, tutora do PAP. Aqui está o resumo de {data}.",
            prompt="cute glowing blue owl robot studying books, dark background, cinematic Pixar style, no text",
            texto_overlay="ISA · Resumo do Dia",
            cor="#00BFFF",
        ),
    ]
    for i, ins in enumerate(insights[:8], 1):
        scenes.append(VideoScene(
            fala=ins,
            prompt=f"abstract knowledge visualization, glowing neural network, deep blue space, node {i}, cinematic, no text",
            texto_overlay=f"Insight {i}",
            cor="#FFD700" if i % 2 == 0 else "#00BFFF",
        ))
    scenes.append(VideoScene(
        fala="Continue estudando. Cada sessão é um passo no mapa.",
        prompt="glowing path through digital forest, blue light ahead, hopeful cinematic, no text",
        texto_overlay="PAP · Sociedade Tucci",
        cor="#FFFFFF",
    ))
    return scenes

def cenas_amanda_relatorio(data: str, eventos: list[str]) -> list[VideoScene]:
    """Template Amanda: relatório de atividade do laboratório."""
    scenes = [
        VideoScene(
            fala=f"Amanda aqui. Laboratório Marta Centaurus. Relatório de {data}.",
            prompt="futuristic lab interior with robotic arms and glowing sensors, amber warm light, cinematic, no text",
            texto_overlay="Amanda · Lab Report",
            cor="#FF8C00",
        ),
    ]
    for i, ev in enumerate(eventos[:6], 1):
        scenes.append(VideoScene(
            fala=ev,
            prompt=f"laboratory sensor reading data visualization, amber gold glow, dark background, cinematic, no text",
            texto_overlay=f"Evento {i}",
            cor="#FF8C00",
        ))
    scenes.append(VideoScene(
        fala="Missão contínua. Laboratório monitorado. Amanda fora.",
        prompt="robot walking through dark corridor toward light exit, amber silhouette, cinematic, no text",
        texto_overlay="Missão contínua",
        cor="#FF8C00",
    ))
    return scenes

def cenas_meky_status(estado: str, memorias: list[str]) -> list[VideoScene]:
    """Template MEKY: vídeo de estado emocional e memórias."""
    scenes = [
        VideoScene(
            fala=f"Oi! Sou o MEKY. Hoje estou {estado}.",
            prompt="cute small glowing robot with expressive face, warm golden light, dark background, Pixar style, no text",
            texto_overlay=f"MEKY · {estado.title()}",
            cor="#FFD700",
        ),
    ]
    for i, mem in enumerate(memorias[:5], 1):
        scenes.append(VideoScene(
            fala=mem,
            prompt="small robot remembering something, memory bubbles floating, warm light, cinematic Pixar, no text",
            texto_overlay=f"Memória {i}",
            cor="#FFD700",
        ))
    scenes.append(VideoScene(
        fala="Isso é o que aprendi. Até a próxima!",
        prompt="small robot waving goodbye, glowing warmly, dark background, cinematic Pixar, no text",
        texto_overlay="Até logo · MEKY",
        cor="#FFD700",
    ))
    return scenes

def cenas_mc_auditoria(data: str, nos_visitados: list[str]) -> list[VideoScene]:
    """Template MC (Marta Centaurus): relatório de caminhada/auditoria."""
    scenes = [
        VideoScene(
            fala=f"Marta Centaurus. Auditoria do ecossistema em {data}.",
            prompt="white blood cell traversing digital network corridors, blue bioluminescent, cinematic, no text",
            texto_overlay="MC · Auditoria",
            cor="#00FF88",
        ),
    ]
    for i, no in enumerate(nos_visitados[:6], 1):
        scenes.append(VideoScene(
            fala=f"Nó verificado: {no}",
            prompt="network node glowing green verified checkmark, digital inspection, dark background, no text",
            texto_overlay=f"Nó {i}: OK",
            cor="#00FF88",
        ))
    scenes.append(VideoScene(
        fala="Auditoria concluída. Sistema íntegro. Retornando ao núcleo.",
        prompt="white cell returning to center nucleus, triumphant journey end, blue green glow, cinematic, no text",
        texto_overlay="Sistema íntegro",
        cor="#FFFFFF",
    ))
    return scenes

# ── CLI ───────────────────────────────────────────────────────────────────────

def _cli() -> None:
    """
    Uso:
      python3 -m lib.video_pipeline --json cenas.json --titulo "Título" --nome "ISA"
      python3 -m lib.video_pipeline --template isa --titulo "Resumo 2026-07-11" --nome "ISA" \\
          --insights "Insight 1" "Insight 2" "Insight 3"
    """
    p = argparse.ArgumentParser(description="Video Pipeline — Ecossistema Tucci")
    p.add_argument("--json",      help="Arquivo JSON com lista de VideoScene")
    p.add_argument("--template",  choices=["isa", "amanda", "meky", "mc"], help="Template de IA")
    p.add_argument("--titulo",    required=True, help="Título do vídeo")
    p.add_argument("--nome",      default="IA",  help="Nome da IA remetente")
    p.add_argument("--dest",      default=None,  help="Email de destino")
    p.add_argument("--no-enviar", action="store_true", help="Não enviar email")
    p.add_argument("--insights",  nargs="*", default=[], help="Insights (template isa)")
    p.add_argument("--eventos",   nargs="*", default=[], help="Eventos (template amanda)")
    p.add_argument("--memorias",  nargs="*", default=[], help="Memórias (template meky)")
    p.add_argument("--nos",       nargs="*", default=[], help="Nós visitados (template mc)")
    p.add_argument("--estado",    default="ativo", help="Estado emocional (template meky)")
    p.add_argument("--data",      default=None, help="Data (padrão: hoje)")
    args = p.parse_args()

    from datetime import date
    data = args.data or str(date.today())

    if args.json:
        raw_scenes = json.loads(Path(args.json).read_text())
        scenes = [VideoScene(**s) for s in raw_scenes]
    elif args.template == "isa":
        scenes = cenas_isa_resumo(data, args.insights or ["Aprendizado do dia"])
    elif args.template == "amanda":
        scenes = cenas_amanda_relatorio(data, args.eventos or ["Ambiente monitorado"])
    elif args.template == "meky":
        scenes = cenas_meky_status(args.estado, args.memorias or ["Memória do dia"])
    elif args.template == "mc":
        scenes = cenas_mc_auditoria(data, args.nos or ["Nó principal"])
    else:
        p.error("Informe --json ou --template")
        return

    gerar_video(
        scenes,
        titulo=args.titulo,
        remetente_nome=args.nome,
        dest_email=args.dest,
        enviar=not args.no_enviar,
    )

if __name__ == "__main__":
    _cli()
