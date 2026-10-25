import tkinter as tk
import threading
import queue
import json
import os
import random
import math
import time
import webbrowser
import subprocess
import sys
import shutil
import base64
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime
import tkinter.messagebox as messagebox
from http.server import BaseHTTPRequestHandler, HTTPServer

import ollama
import speech_recognition as sr
import pyttsx3
import openwakeword
from openwakeword.model import Model
import sounddevice as sd


# =========================================================
# SHIVA CONFIG
# =========================================================

MODEL_NAME = "llama3.2"
MEMORY_FILE = "memory.json"

WAKE_WORD = "hey_jarvis"
WAKE_THRESHOLD = 0.5

INSTAGRAM_URLS = {
    "NEELESH BHATT": "https://www.instagram.com/itz_neelesh.10/",
    "PRAJJWAL BEDI": "https://www.instagram.com/_prajjwal_bedi/"
}

INSTAGRAM_IDS = {
    "NEELESH BHATT": "@itz_neelesh.10",
    "PRAJJWAL BEDI": "@_prajjwal_bedi"
}

# Display order: first Neelesh Bhatt, then Prajjwal Bedi.
INVENTORS = [
    "NEELESH BHATT",
    "PRAJJWAL BEDI"
]

# =========================================================
# GREEN HACKER THEME
# =========================================================

BLACK = "#020403"
DARK = "#050907"
PANEL = "#07100b"
PANEL2 = "#0a160e"

GREEN = "#00ff66"
GREEN2 = "#00cc55"
GREEN_DARK = "#075c2b"
GREEN_DIM = "#164d2d"

WHITE_GREEN = "#caffdc"
MUTED = "#4c8a63"

RED = "#ff304f"

# Sword only
SWORD_BLUE = "#008cff"
SWORD_BLUE2 = "#00cfff"
SWORD_DARK = "#06233b"

# Lightning only
LIGHTNING_YELLOW = "#ffe600"
LIGHTNING_WHITE = "#ffffff"


# =========================================================
# MEMORY
# =========================================================

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return []

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data if isinstance(data, list) else []

    except Exception:
        return []


def save_memory(data):
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


memory = load_memory()


# =========================================================
# VOICE / TEXT TO SPEECH
# =========================================================

speech_done = threading.Event()
speech_done.set()
tts_lock = threading.Lock()


def speak(text, voice_only=False):
    """Speak text aloud and set speech_done only after playback ends."""
    text = str(text).strip()
    if not text:
        speech_done.set()
        return

    speech_done.clear()

    def worker():
        engine = None
        errors = []
        try:
            # On Windows, use SAPI's default audio device. Pass text as
            # Base64 so quotes/apostrophes cannot break the PowerShell command.
            if os.name == "nt":
                try:
                    import base64
                    text_b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
                    voice_select = ""
                    ps = (
                        "Add-Type -AssemblyName System.Speech; "
                        "$ErrorActionPreference='Stop'; "
                        "$bytes=[Convert]::FromBase64String('" + text_b64 + "'); "
                        "$t=[Text.Encoding]::UTF8.GetString($bytes); "
                        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                        "$s.SetOutputToDefaultAudioDevice(); $s.Volume=100; $s.Rate=0; " +
                        "$s.Speak($t); $s.Dispose(); exit 0"
                    )
                    encoded = base64.b64encode(ps.encode("utf-16le")).decode("ascii")
                    result = subprocess.run(
                        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        timeout=max(45, min(180, len(text) * 0.5 + 20)), check=False
                    )
                    if result.returncode == 0:
                        return
                    errors.append("Windows SAPI: " + result.stderr.decode("utf-8", "ignore")[:500])
                except Exception as exc:
                    errors.append("Windows SAPI: " + repr(exc))

            # Fallback for Windows if SAPI failed, and for other platforms.
            try:
                engine = pyttsx3.init(driverName="sapi5") if os.name == "nt" else pyttsx3.init()
            except Exception:
                engine = pyttsx3.init()
            engine.setProperty("rate", 175)
            engine.setProperty("volume", 1.0)
            engine.say(text)
            engine.runAndWait()
        except Exception as exc:
            errors.append(repr(exc))
            print("TTS error:", " | ".join(errors))
            if not voice_only:
                try:
                    root.after(0, add_chat, "SHIVA", "Voice playback failed: " + " | ".join(errors)[:300])
                except Exception:
                    pass
        finally:
            try:
                if engine is not None:
                    engine.stop()
            except Exception:
                pass
            speech_done.set()

    threading.Thread(target=worker, daemon=True).start()


# =========================================================
# WAKE WORD
# =========================================================

wake_model = None
wake_running = False


def initialize_wake_word():

    global wake_model

    try:
        openwakeword.utils.download_models()

        wake_model = Model(
            wakeword_models=["hey_jarvis"],
            inference_framework="onnx"
        )

        print("Wake word loaded.")

    except Exception as e:
        print("Wake word error:", e)


# =========================================================
# WINDOW
# =========================================================

root = tk.Tk()

root.title("SHIVA // HACKER COMMAND CENTER")
root.geometry("1450x850")
root.minsize(1100, 700)
root.configure(bg=BLACK)


# =========================================================
# HEADER
# =========================================================

header = tk.Frame(
    root,
    bg=BLACK,
    height=70
)

header.pack(fill="x")
header.pack_propagate(False)


tk.Label(
    header,
    text="S H I V A",
    font=("Consolas", 30, "bold"),
    fg=GREEN,
    bg=BLACK
).pack(
    side="left",
    padx=28
)


tk.Label(
    header,
    text="// PERSONAL AI COMMAND CENTER",
    font=("Consolas", 11),
    fg=MUTED,
    bg=BLACK
).pack(
    side="left"
)


status_label = tk.Label(
    header,
    text="● SYSTEM ONLINE",
    font=("Consolas", 11, "bold"),
    fg=GREEN,
    bg=BLACK
)

status_label.pack(
    side="right",
    padx=30
)


# =========================================================
# MAIN
# =========================================================

main = tk.Frame(
    root,
    bg=BLACK
)

main.pack(
    fill="both",
    expand=True,
    padx=18,
    pady=(0, 18)
)


# =========================================================
# LEFT INVENTOR PANEL
# =========================================================

left_panel = tk.Frame(
    main,
    bg=PANEL,
    width=260,
    highlightbackground=GREEN_DARK,
    highlightthickness=1
)

left_panel.pack(
    side="left",
    fill="y",
    padx=(0, 12)
)

left_panel.pack_propagate(False)


tk.Label(
    left_panel,
    text="// PROJECT INVENTORS",
    font=("Consolas", 12, "bold"),
    fg=GREEN,
    bg=PANEL
).pack(
    anchor="w",
    padx=20,
    pady=(25, 18)
)


# =========================================================
# CLICKABLE + ANIMATED INVENTORS
# =========================================================

inventor_widgets = []
active_inventor = 0
inventor_animation_tick = 0


def open_instagram(url):
    try:
        webbrowser.open_new_tab(url)
    except Exception as e:
        print("Instagram error:", e)


def bind_instagram_click(widget, url):

    widget.bind(
        "<Button-1>",
        lambda event, link=url:
        open_instagram(link)
    )

    widget.bind(
        "<Enter>",
        lambda event:
        widget.config(cursor="hand2")
    )


for name in INVENTORS:

    box = tk.Frame(
        left_panel,
        bg=BLACK,
        highlightbackground=GREEN_DARK,
        highlightthickness=1,
        cursor="hand2"
    )

    box.pack(
        fill="x",
        padx=14,
        pady=7
    )

    indicator = tk.Label(
        box,
        text=">",
        font=("Consolas", 10, "bold"),
        fg=GREEN_DIM,
        bg=BLACK,
        width=3,
        cursor="hand2"
    )

    indicator.pack(
        side="left",
        padx=(5, 0)
    )

    name_label = tk.Label(
        box,
        text=name,
        font=("Consolas", 11, "bold"),
        fg=WHITE_GREEN,
        bg=BLACK,
        cursor="hand2"
    )

    name_label.pack(
        side="top",
        anchor="w",
        padx=5,
        pady=(10, 0)
    )

    instagram_label = tk.Label(
        box,
        text=INSTAGRAM_IDS[name],
        font=("Consolas", 9, "bold"),
        fg=MUTED,
        bg=BLACK,
        cursor="hand2"
    )

    instagram_label.pack(
        side="top",
        anchor="w",
        padx=5,
        pady=(0, 10)
    )

    url = INSTAGRAM_URLS[name]

    bind_instagram_click(
        box,
        url
    )

    bind_instagram_click(
        indicator,
        url
    )

    bind_instagram_click(
        name_label,
        url
    )

    bind_instagram_click(
        instagram_label,
        url
    )

    inventor_widgets.append({
        "box": box,
        "label": name_label,
        "instagram": instagram_label,
        "indicator": indicator
    })


def animate_inventors():

    global active_inventor
    global inventor_animation_tick

    inventor_animation_tick += 1

    if inventor_animation_tick >= 14:

        inventor_animation_tick = 0

        active_inventor += 1

        if active_inventor >= len(INVENTORS):
            active_inventor = 0

    for index, item in enumerate(inventor_widgets):

        box = item["box"]
        label = item["label"]
        instagram = item["instagram"]
        indicator = item["indicator"]

        if index == active_inventor:

            box.config(
                bg="#061a0d",
                highlightbackground=GREEN,
                highlightthickness=2
            )

            label.config(
                fg=GREEN,
                bg="#061a0d",
                font=("Consolas", 11, "bold")
            )

            instagram.config(
                fg=GREEN2,
                bg="#061a0d",
                font=("Consolas", 9, "bold")
            )

            phase = inventor_animation_tick % 4

            if phase == 0:
                indicator.config(text=">")

            elif phase == 1:
                indicator.config(text=">>")

            elif phase == 2:
                indicator.config(text=">>>")

            else:
                indicator.config(text=">>")

            indicator.config(
                fg=GREEN,
                bg="#061a0d"
            )

        else:

            box.config(
                bg=BLACK,
                highlightbackground=GREEN_DARK,
                highlightthickness=1
            )

            label.config(
                fg=WHITE_GREEN,
                bg=BLACK,
                font=("Consolas", 11, "bold")
            )

            instagram.config(
                fg=MUTED,
                bg=BLACK,
                font=("Consolas", 9, "bold")
            )

            indicator.config(
                text=" ",
                fg=GREEN_DIM,
                bg=BLACK
            )

    root.after(
        110,
        animate_inventors
    )


def open_github_profile():
    """Open the SHIVA AI creator's GitHub profile."""
    url = "https://github.com/NEELESH-BHATT-10"
    try:
        if sys.platform.startswith("win"):
            chrome_paths = [
                os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"),
                             "Google", "Chrome", "Application", "chrome.exe"),
                os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
                             "Google", "Chrome", "Application", "chrome.exe"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""),
                             "Google", "Chrome", "Application", "chrome.exe"),
            ]
            chrome = next((p for p in chrome_paths if p and os.path.isfile(p)), None)
            if chrome:
                subprocess.Popen([chrome, "--new-tab", url])
                return
        try:
            webbrowser.get("chrome").open_new_tab(url)
        except Exception:
            webbrowser.open_new_tab(url)
    except Exception as exc:
        messagebox.showerror("GitHub", "Could not open the GitHub profile.\n" + str(exc))


def create_github_button(parent):
    """Add a clickable GitHub profile shortcut matching SHIVA AI's theme."""
    button = tk.Frame(parent, bg="#ffad33", cursor="hand2")
    button.pack(fill="x", padx=14, pady=(10, 8))

    icon = tk.Canvas(button, width=30, height=30, bg="#ffad33",
                     highlightthickness=0, cursor="hand2")
    icon.pack(side="left", padx=(10, 7), pady=6)
    # Small locally drawn GitHub-inspired icon; no image download is needed.
    icon.create_oval(5, 7, 25, 27, fill="#111111", outline="#111111")
    icon.create_polygon(6, 12, 5, 3, 13, 8, fill="#111111", outline="#111111")
    icon.create_polygon(17, 8, 25, 3, 24, 13, fill="#111111", outline="#111111")
    icon.create_oval(10, 13, 12, 15, fill="#ffad33", outline="#ffad33")
    icon.create_oval(18, 13, 20, 15, fill="#ffad33", outline="#ffad33")
    icon.create_arc(11, 15, 19, 22, start=200, extent=140, style="arc",
                    outline="#ffad33", width=2)

    label = tk.Label(button, text="GITHUB PROFILE", font=("Consolas", 11, "bold"),
                     fg="#111111", bg="#ffad33", cursor="hand2")
    label.pack(side="left", fill="x", expand=True, pady=9)

    for widget in (button, icon, label):
        widget.bind("<Button-1>", lambda event: open_github_profile())
        widget.bind("<Enter>", lambda event: button.config(bg="#ffd080"))
        widget.bind("<Leave>", lambda event: button.config(bg="#ffad33"))
    return button


# GitHub shortcut appears in the left sidebar below the creator cards.
create_github_button(left_panel)


# =========================================================
# SYSTEM STATUS
# =========================================================

tk.Label(
    left_panel,
    text="// SYSTEM STATUS",
    font=("Consolas", 10, "bold"),
    fg=MUTED,
    bg=PANEL
).pack(
    anchor="w",
    padx=20,
    pady=(35, 5)
)


system_state = tk.Label(
    left_panel,
    text="● READY",
    font=("Consolas", 12, "bold"),
    fg=GREEN,
    bg=PANEL
)

system_state.pack(
    anchor="w",
    padx=20
)


wake_state = tk.Label(
    left_panel,
    text="WAKE: HEY JARVIS",
    font=("Consolas", 10),
    fg=MUTED,
    bg=PANEL
)

wake_state.pack(
    anchor="w",
    padx=20,
    pady=8
)


# =========================================================
# COPYRIGHT BUTTON (BOTTOM-LEFT)
# =========================================================

COPYRIGHT_ORANGE = "#ff8c00"


def open_copyright_page():
    """Create the SHIVA copyright information page and open it in Chrome."""
    copyright_html = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SHIVA AI | Copyright & Project Notice</title>
<style>
:root{color-scheme:dark;--bg:#050807;--panel:#0b1510;--green:#00ff75;--orange:#ff8c00;--text:#e9fff0;--muted:#9db5a5}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at top,#12351f 0%,var(--bg) 55%);color:var(--text);font-family:Segoe UI,Arial,sans-serif;line-height:1.7}
header{padding:52px 22px 38px;text-align:center;border-bottom:1px solid #245638}header .mark{display:inline-grid;place-items:center;width:82px;height:82px;border:3px solid var(--orange);border-radius:50%;color:var(--orange);font-size:48px;font-weight:800;box-shadow:0 0 25px #ff8c0038}
h1{margin:18px 0 4px;font-size:clamp(30px,5vw,48px);letter-spacing:3px}header p{margin:0;color:var(--muted)}main{max-width:900px;margin:28px auto;padding:0 18px 45px}.card{background:linear-gradient(145deg,#0c1911,#080e0b);border:1px solid #244b31;border-radius:14px;padding:22px 24px;margin:16px 0;box-shadow:0 8px 25px #0005}h2{color:var(--green);font-size:21px;margin:0 0 9px}a{color:var(--orange)}.notice{border-left:4px solid var(--orange)}.tag{display:inline-block;border:1px solid #3a7049;border-radius:30px;padding:4px 12px;margin:4px;color:#c7ffda;font-size:13px}footer{text-align:center;padding:25px;color:var(--muted);border-top:1px solid #244b31;font-size:14px}
</style>
</head>
<body>
<header><div class="mark">©</div><h1>SHIVA AI</h1><p>Copyright • Credits • Project Use Notice</p><div style="margin-top:16px"><span class="tag">Python Project</span><span class="tag">AI Assistant</span><span class="tag">Created by Neelesh Bhatt and Co.</span></div></header>
<main>
<section class="card notice"><h2>Copyright Notice</h2><p><strong>© 2026 Neelesh Bhatt and Co. All rights reserved.</strong></p><p>SHIVA AI is a personal AI-assistant project. The project name, original interface design, project-specific code, visual presentation, animations, and accompanying documentation are claimed as the work of Neelesh Bhatt and Co., to the extent permitted by applicable law.</p></section>
<section class="card"><h2>About SHIVA AI</h2><p>SHIVA AI is a Python-based assistant interface designed to bring together text chat, voice interaction, local AI model access, wake-word functionality, and a custom hacker-inspired visual theme. Features may depend on the computer, installed packages, and local configuration.</p></section>
<section class="card"><h2>Project Credits</h2><p><strong>Project credit:</strong> Neelesh Bhatt and Co.</p><p><strong>Creator contact/social profile:</strong> <a href="https://www.instagram.com/itz_neelesh.10/" target="_blank" rel="noopener noreferrer">@itz_neelesh.10</a></p><p><strong>Additional project credit:</strong> <a href="https://www.instagram.com/_prajjwal_bedi/" target="_blank" rel="noopener noreferrer">@_prajjwal_bedi</a></p><p>Credits are shown for project attribution and do not by themselves establish legal ownership of third-party tools or materials.</p></section>
<section class="card"><h2>Third-Party Software</h2><p>SHIVA AI may use third-party libraries and services, including Python packages, Ollama, an AI model, speech-recognition components, and text-to-speech components. Those products, names, models, and services remain the property of their respective owners and are subject to their own licences and terms. This page does not claim ownership of third-party software, model outputs, logos, or trademarks.</p></section>
<section class="card"><h2>Responsible Use</h2><p>Use SHIVA AI responsibly and lawfully. Review any output before relying on it, especially for important decisions. Voice recognition and AI responses can be inaccurate, and features may not work on every system. Keep credentials, private files, and personal information secure.</p></section>
<section class="card"><h2>Permission and Redistribution</h2><p>Unless permission or an applicable licence says otherwise, do not present the project-specific work as your own or redistribute modified copies in a way that removes attribution. If you want to reuse the project, seek permission from the project owner and preserve applicable third-party notices. This notice is informational and does not replace legal advice or any licence that applies to particular code.</p></section>
<section class="card"><h2>Changes to This Page</h2><p>This notice may be updated as SHIVA AI develops. The year, credits, features, and ownership statements should be reviewed and kept accurate as the project changes.</p></section>
<section class="card notice"><h2>All Rights Reserved</h2><p>© 2026 Neelesh Bhatt and Co. All rights reserved. SHIVA AI — project credit and copyright information.</p></section>
</main><footer>Made for the SHIVA AI project • © 2026 Neelesh Bhatt and Co.</footer>
</body></html>'''

    page_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SHIVA_AI_Copyright.html")
    try:
        with open(page_path, "w", encoding="utf-8") as page_file:
            page_file.write(copyright_html)
        page_url = "file:///" + page_path.replace(os.sep, "/").replace(" ", "%20")
        try:
            chrome = webbrowser.get("chrome")
            chrome.open_new_tab(page_url)
        except Exception:
            webbrowser.open_new_tab(page_url)
    except Exception as error:
        print("Could not open SHIVA copyright page:", error)
        try:
            webbrowser.open_new_tab("https://www.instagram.com/itz_neelesh.10/")
        except Exception:
            pass


# =========================================================
# HEISENBERG AI — EXTERNAL CHROME IMAGE STUDIO
# =========================================================
def open_heisenberg_ai_in_chrome():
    """Create and open the HEISENBERG AI image-generation studio in Google Chrome."""
    page_html = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HEISENBERG AI Image Studio</title>
<style>
:root{color-scheme:dark;--bg:#041316;--panel:#0b2529;--green:#50e3c2;--teal:#2db9ad;--cream:#e4fff8;--muted:#8cb9b4}*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(ellipse at top,#124e50,#071b20 58%,#030b0e);color:var(--cream);font-family:Segoe UI,Arial,sans-serif;padding:20px}main{max-width:900px;margin:20px auto}.hero{text-align:center;margin-bottom:24px}.chem-logo{display:flex;justify-content:center;gap:8px;margin:0 auto 12px}.element{position:relative;display:grid;place-items:center;width:58px;height:62px;border:2px solid var(--green);background:linear-gradient(145deg,#123d3e,#061b20);color:var(--green);font-weight:900;font-size:30px;box-shadow:0 0 18px #50e3c233}.element small{position:absolute;top:3px;left:5px;font-size:9px;color:var(--cream)}h1{margin:5px;color:var(--green);font-size:clamp(32px,6vw,54px);letter-spacing:3px;text-shadow:0 0 18px #50e3c233}.byline{color:#78d9ca;letter-spacing:1px}.card{background:linear-gradient(145deg,#0b292d,#07171b);border:1px solid #247d78;border-radius:18px;padding:clamp(18px,4vw,30px);box-shadow:0 16px 45px #0008}label{display:block;color:var(--green);font-weight:800;margin:0 0 9px}textarea,select{width:100%;border:1px solid #287f79;border-radius:10px;background:#041316;color:var(--cream);padding:13px;font:16px/1.5 Segoe UI,Arial,sans-serif}textarea{min-height:125px;resize:vertical}.row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:17px 0}button,.download{display:inline-block;border:1px solid #50e3c2;border-radius:11px;background:linear-gradient(100deg,#147f78,#50e3c2);color:#031513;font-weight:900;font-size:16px;padding:14px 22px;cursor:pointer;text-decoration:none;text-align:center}.actions{display:flex;flex-wrap:wrap;gap:12px;margin-top:18px}.status{color:var(--green);min-height:28px;margin:16px 0}.result{margin-top:18px;min-height:200px;border:1px dashed #287f79;border-radius:12px;background:#041316;display:flex;align-items:center;justify-content:center;padding:12px}.result img{max-width:100%;max-height:70vh;object-fit:contain;border-radius:8px}.placeholder{color:var(--muted);text-align:center;line-height:1.7}.note{font-size:12px;color:#8cb9b4;line-height:1.6;margin-top:18px}footer{text-align:center;color:#76a9a3;font-size:12px;margin:22px 0}@media(max-width:600px){.row{grid-template-columns:1fr}.actions button,.actions a{width:100%}}
</style></head><body><main><header class="hero"><div class="chem-logo"><div class="element"><small>01</small>H</div><div class="element"><small>AI</small>H</div></div><h1>HEISENBERG AI</h1><div class="byline">BY NEELESH BHATT</div><p>Describe an image, select a shape and style, then generate and save it.</p></header>
<section class="card"><label for="prompt">DESCRIBE YOUR IMAGE</label><textarea id="prompt" placeholder="Describe the image you want to create...">A cinematic blue-green chemistry lab atmosphere with dramatic teal lighting, original digital art</textarea>
<div class="row"><div><label for="shape">IMAGE SHAPE</label><select id="shape"><option value="768,768">Square</option><option value="1024,576">Landscape</option><option value="576,1024">Portrait</option></select></div><div><label for="style">ART STYLE</label><select id="style"><option value="">Automatic</option><option value="photorealistic">Photorealistic</option><option value="digital art">Digital art</option><option value="watercolor painting">Watercolor</option><option value="anime illustration">Anime</option><option value="3D render">3D render</option></select></div></div>
<div class="actions"><button id="generate" onclick="generateImage()">✦ GENERATE IMAGE</button><a id="download" class="download" href="#" download="HEISENBERG_AI_image.jpg" style="display:none">⬇ SAVE IMAGE</a></div><div class="status" id="status">Ready. Enter a prompt and click Generate Image.</div><div class="result" id="result"><div class="placeholder">Your generated image will appear here.</div></div><p class="note">Requires internet access and a working third-party image-generation service. If generation fails, try again later. Do not enter private or sensitive information in prompts.</p></section><footer>© 2026 HEISENBERG AI • Neelesh Bhatt and Co.</footer></main>
<script>
async function generateImage(){const prompt=document.getElementById('prompt').value.trim();if(!prompt){document.getElementById('status').textContent='Please describe your image first.';return;}const btn=document.getElementById('generate'),status=document.getElementById('status'),result=document.getElementById('result'),download=document.getElementById('download');const [width,height]=document.getElementById('shape').value.split(',');const style=document.getElementById('style').value;const fullPrompt=style?prompt+', '+style:prompt;const url='https://image.pollinations.ai/prompt/'+encodeURIComponent(fullPrompt)+'?width='+width+'&height='+height+'&nologo=true&seed='+Math.floor(Math.random()*1000000000);btn.disabled=true;status.textContent='Generating image… please wait.';download.style.display='none';result.innerHTML='<div class="placeholder">⚗ HEISENBERG AI is creating your image…</div>';const img=new Image();img.alt='Image generated by HEISENBERG AI';img.onload=()=>{result.innerHTML='';result.appendChild(img);download.href=url;download.style.display='inline-block';status.textContent='Image generated. Click SAVE IMAGE to download.';btn.disabled=false;};img.onerror=()=>{result.innerHTML='<div class="placeholder">The image service did not return an image.<br>Check your internet connection or try again later.</div>';status.textContent='Image generation failed or the service is unavailable.';btn.disabled=false;};img.src=url;}
</script></body></html>'''
    try:
        folder = os.path.dirname(os.path.abspath(__file__))
        page_path = os.path.join(folder, "HEISENBERG_AI_Image_Studio.html")
        with open(page_path, "w", encoding="utf-8") as page_file:
            page_file.write(page_html)
        page_url = "file:///" + urllib.parse.quote(page_path.replace(os.sep, "/"), safe=":/")

        # Prefer launching the actual Chrome executable, not just a browser alias.
        chrome_paths = []
        if sys.platform.startswith("win"):
            for env_key, suffix in (("PROGRAMFILES", "Google/Chrome/Application/chrome.exe"),
                                    ("PROGRAMFILES(X86)", "Google/Chrome/Application/chrome.exe"),
                                    ("LOCALAPPDATA", "Google/Chrome/Application/chrome.exe")):
                base = os.environ.get(env_key)
                if base:
                    chrome_paths.append(os.path.join(base, *suffix.split("/")))
        elif sys.platform == "darwin":
            chrome_paths.extend(["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                                 os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")])
        else:
            for executable in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
                found = shutil.which(executable)
                if found:
                    chrome_paths.append(found)
        chrome = next((candidate for candidate in chrome_paths if os.path.isfile(candidate)), None)
        if chrome:
            subprocess.Popen([chrome, "--new-tab", page_url])
        else:
            try:
                webbrowser.get("chrome").open_new_tab(page_url)
            except Exception:
                webbrowser.open_new_tab(page_url)
    except Exception as error:
        messagebox.showerror("HEISENBERG AI Image Studio", "Could not open the image generator in Chrome/browser:\n" + str(error), parent=root)


def open_image_creator():
    """Compatibility handler: image studio now opens in an external browser."""
    open_heisenberg_ai_in_chrome()


def open_images_page():
    """Open the external HEISENBERG AI image studio page in Chrome/browser."""
    open_heisenberg_ai_in_chrome()


# =========================================================
# GAMES BY NEELESH BHATT — LOCAL CHROME GAME CHOOSER
# The local launcher listens only on 127.0.0.1.
# =========================================================
# The game programs are embedded in this single file and are written beside it when needed.
GAME_SOURCE = {'tictactoe': '"""TIC TAC TOE — Saffron Edition. Requires pygame."""\nimport pygame, sys\npygame.init(); W,H=900,690\nscreen=pygame.display.set_mode((W,H)); pygame.display.set_caption(\'TIC TAC TOE • Saffron Edition\'); clock=pygame.time.Clock()\nBG=(32,14,5); ORANGE=(255,111,0); GOLD=(255,193,7); CREAM=(255,242,215); MUTED=(212,164,105)\ntitle=pygame.font.SysFont(\'arial\',42,bold=True); font=pygame.font.SysFont(\'arial\',25,bold=True); small=pygame.font.SysFont(\'arial\',18,bold=True)\nBOARD=pygame.Rect(210,155,480,480); CELL=160; LINES=[(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]\nboard=[None]*9; current=\'X\'; mode=\'computer\'; score={\'X\':0,\'O\':0}; winner=None; win_line=None; game_over=False\n\ndef minimax(b,p):\n    for line in LINES:\n        vals=[b[i] for i in line]\n        if vals[0] and vals.count(vals[0])==3: return (10 if vals[0]==\'O\' else -10),None\n    if all(b): return 0,None\n    best=-1000 if p==\'O\' else 1000; move=None\n    for i,v in enumerate(b):\n        if v is None:\n            b[i]=p; val,_=minimax(b,\'X\' if p==\'O\' else \'O\'); b[i]=None\n            if (p==\'O\' and val>best) or (p==\'X\' and val<best): best,move=val,i\n    return best,move\n\ndef check():\n    global winner,win_line,game_over\n    for line in LINES:\n        vals=[board[i] for i in line]\n        if vals[0] and vals.count(vals[0])==3: winner=vals[0]; win_line=line; game_over=True; score[winner]+=1; return\n    if all(board): game_over=True\n\ndef reset():\n    global board,current,winner,win_line,game_over\n    board=[None]*9; current=\'X\'; winner=None; win_line=None; game_over=False\n\ndef draw_mark(m,rect):\n    x,y=rect.center; r=44\n    if m==\'X\': pygame.draw.line(screen,CREAM,(x-r,y-r),(x+r,y+r),12); pygame.draw.line(screen,ORANGE,(x+r,y-r),(x-r,y+r),12)\n    else: pygame.draw.circle(screen,CREAM,(x,y),r,12); pygame.draw.circle(screen,ORANGE,(x,y),r,5)\n\ndef draw():\n    screen.fill(BG); t=title.render(\'TIC TAC TOE\',True,ORANGE); screen.blit(t,t.get_rect(center=(W//2,55)))\n    sub=small.render(\'SAFFRON EDITION • X vs O • M: CHANGE MODE • R: RESET\',True,GOLD); screen.blit(sub,sub.get_rect(center=(W//2,105)))\n    pygame.draw.rect(screen,(83,40,13),BOARD.inflate(12,12),border_radius=12); pygame.draw.rect(screen,(255,220,160),BOARD,border_radius=8)\n    for i in range(1,3): pygame.draw.line(screen,ORANGE,(BOARD.x+i*CELL,BOARD.y),(BOARD.x+i*CELL,BOARD.bottom),7); pygame.draw.line(screen,ORANGE,(BOARD.x,BOARD.y+i*CELL),(BOARD.right,BOARD.y+i*CELL),7)\n    for i,m in enumerate(board):\n        rect=pygame.Rect(BOARD.x+(i%3)*CELL,BOARD.y+(i//3)*CELL,CELL,CELL)\n        if m: draw_mark(m,rect)\n    if win_line:\n        a,b=win_line[0],win_line[2]; pygame.draw.line(screen,GOLD,(BOARD.x+(a%3)*CELL+CELL//2,BOARD.y+(a//3)*CELL+CELL//2),(BOARD.x+(b%3)*CELL+CELL//2,BOARD.y+(b//3)*CELL+CELL//2),12)\n    status=f\'{winner} WINS!\' if winner else (\'DRAW GAME\' if game_over else f\'{current} TURN\')\n    s=font.render(status,True,GOLD if game_over else CREAM); screen.blit(s,s.get_rect(center=(W//2,665)))\n    screen.blit(small.render(f\'X: {score["X"]}\',True,CREAM),(55,210)); screen.blit(small.render(f\'O: {score["O"]}\',True,CREAM),(740,210))\n    mode_text=small.render(\'VS COMPUTER\' if mode==\'computer\' else \'TWO PLAYER\',True,MUTED); screen.blit(mode_text,mode_text.get_rect(center=(W//2,135))); pygame.display.flip()\n\ndef main():\n    global current,mode\n    running=True\n    while running:\n        clock.tick(60)\n        if mode==\'computer\' and current==\'O\' and not game_over:\n            pygame.time.delay(180); _,m=minimax(board,\'O\')\n            if m is not None: board[m]=\'O\'; check(); current=\'X\'\n        for e in pygame.event.get():\n            if e.type==pygame.QUIT: running=False\n            elif e.type==pygame.KEYDOWN:\n                if e.key==pygame.K_ESCAPE: running=False\n                elif e.key==pygame.K_r: reset()\n                elif e.key==pygame.K_m: mode=\'two\' if mode==\'computer\' else \'computer\'; reset()\n            elif e.type==pygame.MOUSEBUTTONDOWN and e.button==1 and not game_over and (mode==\'two\' or current==\'X\') and BOARD.collidepoint(e.pos):\n                col=(e.pos[0]-BOARD.x)//CELL; row=(e.pos[1]-BOARD.y)//CELL; i=row*3+col\n                if board[i] is None: board[i]=current; check(); current=\'O\' if current==\'X\' else \'X\'\n        draw()\n    pygame.quit(); sys.exit()\nif __name__==\'__main__\': main()\n', 'ludo': '"""\nLUDO — a bright saffron/orange Ludo game\nRun in PyCharm:\n    1) Install pygame:  python -m pip install pygame\n    2) Run this file.\n\nControls:\n    • Click ROLL DICE, then click one of the highlighted tokens.\n    • A 6 is needed to bring a token out of the yard.\n    • Roll a 6 or capture an opponent to earn another turn.\n    • First player to bring all four tokens home wins.\n\nLocal pass-and-play for 2–4 players. No internet required.\n"""\n\nimport math\nimport random\nimport sys\nimport pygame\n\npygame.init()\npygame.display.set_caption("LUDO • Saffron Edition")\n\n# ---------- Window / theme ----------\nCELL = 40\nBOARD_CELLS = 15\nBOARD_SIZE = CELL * BOARD_CELLS\nSIDEBAR = 300\nMARGIN = 22\nWIDTH = BOARD_SIZE + SIDEBAR + MARGIN * 2\nHEIGHT = BOARD_SIZE + MARGIN * 2\nFPS = 60\n\nBG = (255, 239, 210)\nSAFFRON = (255, 111, 0)\nORANGE_ACCENT = (255, 128, 0)\nDEEP_ORANGE = (191, 80, 0)  # rich orange-brown accent\nGOLD = (255, 193, 7)\nCREAM = (255, 250, 235)\nINK = (74, 35, 8)\nMUTED = (128, 83, 42)\nWHITE = (255, 255, 255)\nGREEN = (36, 155, 85)\nRED = (222, 54, 54)\nBLUE = (48, 112, 220)\nYELLOW = (246, 184, 35)\nPURPLE = (126, 64, 160)\nPALETTE = [RED, GREEN, YELLOW, BLUE]\nPLAYER_NAMES = ["AGNI • Red", "DHARMA • Green", "TEJAS • Yellow", "SHAKTI • Blue"]\n\nscreen = pygame.display.set_mode((WIDTH, HEIGHT))\nclock = pygame.time.Clock()\nfont = pygame.font.SysFont("arial", 18, bold=True)\nsmall_font = pygame.font.SysFont("arial", 14)\ntiny_font = pygame.font.SysFont("arial", 11, bold=True)\ntitle_font = pygame.font.SysFont("arial", 29, bold=True)\nbig_font = pygame.font.SysFont("arial", 42, bold=True)\n\nBOARD_X = MARGIN\nBOARD_Y = MARGIN\n\n# The 52-cell outer loop, in clockwise order on a 15 x 15 board.\nTRACK = [\n    (1, 6), (2, 6), (3, 6), (4, 6), (5, 6),\n    (6, 5), (6, 4), (6, 3), (6, 2), (6, 1), (6, 0),\n    (7, 0), (8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5),\n    (9, 6), (10, 6), (11, 6), (12, 6), (13, 6), (14, 6),\n    (14, 7), (14, 8), (13, 8), (12, 8), (11, 8), (10, 8), (9, 8),\n    (8, 9), (8, 10), (8, 11), (8, 12), (8, 13), (8, 14),\n    (7, 14), (6, 14), (6, 13), (6, 12), (6, 11), (6, 10), (6, 9),\n    (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8),\n    (0, 7), (0, 6)\n]\nSTART_INDEX = [0, 13, 26, 39]\nSAFE_INDICES = {0, 8, 13, 21, 26, 34, 39, 47}\n\nHOME_LANES = [\n    [(1, 7), (2, 7), (3, 7), (4, 7), (5, 7), (6, 7)],       # red\n    [(7, 1), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6)],       # green\n    [(13, 7), (12, 7), (11, 7), (10, 7), (9, 7), (8, 7)],   # yellow\n    [(7, 13), (7, 12), (7, 11), (7, 10), (7, 9), (7, 8)],  # blue\n]\nYARDS = [\n    [(1.8, 1.8), (4.2, 1.8), (1.8, 4.2), (4.2, 4.2)],\n    [(10.8, 1.8), (13.2, 1.8), (10.8, 4.2), (13.2, 4.2)],\n    [(10.8, 10.8), (13.2, 10.8), (10.8, 13.2), (13.2, 13.2)],\n    [(1.8, 10.8), (4.2, 10.8), (1.8, 13.2), (4.2, 13.2)],\n]\nBASES = [\n    (0, 0, RED), (9, 0, GREEN), (9, 9, YELLOW), (0, 9, BLUE)\n]\nCENTER = (7.5, 7.5)\n\ndef cell_rect(col, row, inset=1):\n    return pygame.Rect(BOARD_X + col * CELL + inset,\n                       BOARD_Y + row * CELL + inset,\n                       CELL - inset * 2, CELL - inset * 2)\n\ndef cell_center(cell):\n    col, row = cell\n    return (BOARD_X + col * CELL + CELL // 2,\n            BOARD_Y + row * CELL + CELL // 2)\n\ndef draw_text(text, fnt, color, x, y, anchor="topleft"):\n    image = fnt.render(text, True, color)\n    rect = image.get_rect()\n    setattr(rect, anchor, (x, y))\n    screen.blit(image, rect)\n    return rect\n\ndef lighten(color, amount=35):\n    return tuple(min(255, c + amount) for c in color)\n\nclass Token:\n    def __init__(self, player, number):\n        self.player = player\n        self.number = number\n        self.progress = -1  # -1 = yard, 0..51 = track, 52..57 = home lane\n        self.anim_from = None\n        self.anim_to = None\n        self.anim_start = 0\n        self.anim_duration = 0\n        self.animating = False\n        self.bounce = random.random() * math.tau\n\n    @property\n    def finished(self):\n        return self.progress == 57\n\nclass LudoGame:\n    def __init__(self):\n        self.player_count = 4\n        self.players = [Token(p, n) for p in range(4) for n in range(4)]\n        self.current = 0\n        self.dice = None\n        self.awaiting_move = False\n        self.legal_tokens = []\n        self.message = "Welcome! Roll the dice to begin."\n        self.roll_button = pygame.Rect(BOARD_X + BOARD_SIZE + 28, 215, SIDEBAR - 56, 58)\n        self.reset_button = pygame.Rect(BOARD_X + BOARD_SIZE + 28, 286, SIDEBAR - 56, 40)\n        self.last_roll_six = False\n        self.winner = None\n        self.dice_anim_until = 0\n        self.dice_anim_value = 1\n        self.turns_taken = 0\n\n    def tokens_for(self, player):\n        return [t for t in self.players if t.player == player]\n\n    def board_position(self, token):\n        if token.progress < 0:\n            col, row = YARDS[token.player][token.number]\n            return (BOARD_X + col * CELL, BOARD_Y + row * CELL)\n        if token.progress <= 51:\n            idx = (START_INDEX[token.player] + token.progress) % 52\n            return cell_center(TRACK[idx])\n        lane_index = token.progress - 52\n        return cell_center(HOME_LANES[token.player][lane_index])\n\n    def roll(self):\n        if self.winner is not None or self.awaiting_move or any(t.animating for t in self.players):\n            return\n        self.dice = random.randint(1, 6)\n        self.dice_anim_until = pygame.time.get_ticks() + 260\n        self.dice_anim_value = random.randint(1, 6)\n        self.last_roll_six = self.dice == 6\n        self.legal_tokens = self.get_legal_tokens(self.current, self.dice)\n        self.message = f"{PLAYER_NAMES[self.current]} rolled {self.dice}."\n        if not self.legal_tokens:\n            self.awaiting_move = False\n            if self.dice == 6:\n                self.message += " No legal move — roll again!"\n            else:\n                self.message += " No move available."\n                self.advance_turn()\n        else:\n            self.awaiting_move = True\n            if len(self.legal_tokens) == 1:\n                self.message += " Select the glowing token."\n            else:\n                self.message += " Choose a glowing token."\n\n    def get_legal_tokens(self, player, roll):\n        legal = []\n        for token in self.tokens_for(player):\n            if token.finished:\n                continue\n            if token.progress == -1:\n                if roll == 6:\n                    legal.append(token)\n            elif token.progress + roll <= 57:\n                legal.append(token)\n        return legal\n\n    def move_token(self, token):\n        if not self.awaiting_move or token not in self.legal_tokens:\n            return\n        old_pos = self.board_position(token)\n        if token.progress == -1:\n            token.progress = 0\n        else:\n            token.progress += self.dice\n        new_pos = self.board_position(token)\n        token.anim_from = old_pos\n        token.anim_to = new_pos\n        token.anim_start = pygame.time.get_ticks()\n        token.anim_duration = 170 + self.dice * 24\n        token.animating = True\n        self.awaiting_move = False\n        self.legal_tokens = []\n        self.message = f"{PLAYER_NAMES[self.current]} moves a token…"\n        self.pending_token = token\n        self.pending_six = self.dice == 6\n\n    def finish_animation(self, token):\n        token.animating = False\n        self.capture_opponents(token)\n        if all(t.finished for t in self.tokens_for(token.player)):\n            self.winner = token.player\n            self.message = f"{PLAYER_NAMES[token.player]} wins! Jai Shri Ram • Victory!"\n            return\n        if self.pending_six or self.captured_this_move:\n            self.message = "Extra turn! Roll again."\n        else:\n            self.advance_turn()\n        self.pending_token = None\n\n    def capture_opponents(self, moved):\n        self.captured_this_move = False\n        if moved.progress < 0 or moved.progress > 51:\n            return\n        idx = (START_INDEX[moved.player] + moved.progress) % 52\n        if idx in SAFE_INDICES:\n            return\n        for other in self.players:\n            if other.player == moved.player or other.progress < 0 or other.progress > 51:\n                continue\n            other_idx = (START_INDEX[other.player] + other.progress) % 52\n            if other_idx == idx:\n                other.progress = -1\n                self.captured_this_move = True\n\n    def advance_turn(self):\n        self.current = (self.current + 1) % self.player_count\n        self.dice = None\n        self.awaiting_move = False\n        self.legal_tokens = []\n        self.turns_taken += 1\n        self.message = f"{PLAYER_NAMES[self.current]}\'s turn — roll the dice."\n\n    def update(self):\n        now = pygame.time.get_ticks()\n        for token in self.players:\n            if token.animating and now - token.anim_start >= token.anim_duration:\n                self.finish_animation(token)\n\n    def draw_board(self):\n        # Board shadow and warm parchment base\n        board_rect = pygame.Rect(BOARD_X, BOARD_Y, BOARD_SIZE, BOARD_SIZE)\n        pygame.draw.rect(screen, (225, 156, 83), board_rect.inflate(10, 10), border_radius=12)\n        pygame.draw.rect(screen, CREAM, board_rect, border_radius=7)\n\n        # Four large home quarters\n        for x, y, color in BASES:\n            r = pygame.Rect(BOARD_X + x * CELL, BOARD_Y + y * CELL, 6 * CELL, 6 * CELL)\n            pygame.draw.rect(screen, color, r, border_radius=8)\n            inner = r.inflate(-CELL * 1.1, -CELL * 1.1)\n            pygame.draw.rect(screen, CREAM, inner, border_radius=12)\n            # Decorative dots in each base\n            for dx, dy in [(0, 0), (1, 0), (0, 1), (1, 1)]:\n                cx = inner.x + inner.width * (0.32 + dx * 0.36)\n                cy = inner.y + inner.height * (0.32 + dy * 0.36)\n                pygame.draw.circle(screen, lighten(color, 30), (int(cx), int(cy)), 7)\n\n        # Track cells\n        for i, cell in enumerate(TRACK):\n            color = WHITE\n            if i in START_INDEX:\n                color = PALETTE[START_INDEX.index(i)]\n            elif i in SAFE_INDICES:\n                color = (255, 222, 156)\n            rect = cell_rect(*cell)\n            pygame.draw.rect(screen, color, rect, border_radius=5)\n            pygame.draw.rect(screen, (215, 177, 132), rect, 1, border_radius=5)\n            if i in SAFE_INDICES:\n                cx, cy = cell_center(cell)\n                pygame.draw.circle(screen, GOLD, (cx, cy), 6, 2)\n\n        # Home lanes\n        for p, lane in enumerate(HOME_LANES):\n            for j, cell in enumerate(lane):\n                rect = cell_rect(*cell)\n                pygame.draw.rect(screen, lighten(PALETTE[p], 48), rect, border_radius=5)\n                pygame.draw.rect(screen, PALETTE[p], rect, 1, border_radius=5)\n                if j == 5:\n                    pygame.draw.circle(screen, PALETTE[p], cell_center(cell), 7)\n\n        # Center mandala-inspired sun\n        cx, cy = cell_center((7, 7))\n        pygame.draw.circle(screen, GOLD, (cx, cy), 48)\n        pygame.draw.circle(screen, SAFFRON, (cx, cy), 37, 4)\n        for i in range(12):\n            a = i * math.tau / 12\n            p1 = (cx + math.cos(a) * 40, cy + math.sin(a) * 40)\n            p2 = (cx + math.cos(a) * 49, cy + math.sin(a) * 49)\n            pygame.draw.line(screen, SAFFRON, p1, p2, 3)\n        draw_text("ॐ", pygame.font.SysFont("arial", 36, bold=True), INK, cx, cy, "center")\n\n        # Player labels on base corners\n        draw_text("AGNI", tiny_font, WHITE, BOARD_X + 12, BOARD_Y + 10)\n        draw_text("DHARMA", tiny_font, WHITE, BOARD_X + BOARD_SIZE - 12, BOARD_Y + 10, "topright")\n        draw_text("SHAKTI", tiny_font, WHITE, BOARD_X + 12, BOARD_Y + BOARD_SIZE - 12, "bottomleft")\n        draw_text("TEJAS", tiny_font, INK, BOARD_X + BOARD_SIZE - 12, BOARD_Y + BOARD_SIZE - 12, "bottomright")\n\n        # Tokens\n        now = pygame.time.get_ticks()\n        for token in self.players:\n            pos = self.token_draw_position(token, now)\n            if pos is None:\n                continue\n            x, y = int(pos[0]), int(pos[1])\n            is_legal = token in self.legal_tokens and self.awaiting_move\n            radius = 13 if is_legal else 11\n            if is_legal:\n                pulse = 3 + int(2 * (1 + math.sin(now / 100 + token.bounce)))\n                pygame.draw.circle(screen, GOLD, (x, y), radius + pulse, 3)\n            pygame.draw.circle(screen, (98, 49, 13), (x + 2, y + 3), radius + 1)\n            pygame.draw.circle(screen, PALETTE[token.player], (x, y), radius)\n            pygame.draw.circle(screen, lighten(PALETTE[token.player], 65), (x - 3, y - 4), 4)\n            pygame.draw.circle(screen, WHITE, (x, y), radius, 1)\n            if token.finished:\n                pygame.draw.circle(screen, GOLD, (x, y), radius + 4, 2)\n\n    def token_draw_position(self, token, now):\n        if token.animating:\n            t = min(1.0, (now - token.anim_start) / token.anim_duration)\n            # Smoothstep interpolation\n            t = t * t * (3 - 2 * t)\n            x = token.anim_from[0] + (token.anim_to[0] - token.anim_from[0]) * t\n            y = token.anim_from[1] + (token.anim_to[1] - token.anim_from[1]) * t\n            # small hop for lively but lightweight animation\n            y -= math.sin(t * math.pi) * 10\n            return x, y\n        if token.progress == -1:\n            col, row = YARDS[token.player][token.number]\n            return (BOARD_X + col * CELL, BOARD_Y + row * CELL)\n        return self.board_position(token)\n\n    def draw_sidebar(self):\n        x = BOARD_X + BOARD_SIZE + 22\n        y = BOARD_Y\n        panel = pygame.Rect(x, y, SIDEBAR - 14, BOARD_SIZE)\n        pygame.draw.rect(screen, (255, 222, 174), panel, border_radius=18)\n        pygame.draw.rect(screen, SAFFRON, panel, 3, border_radius=18)\n\n        draw_text("LUDO", title_font, DEEP_ORANGE, x + 18, y + 18)\n        draw_text("L U D O", font, INK, x + 20, y + 52)\n        pygame.draw.line(screen, GOLD, (x + 18, y + 82), (x + panel.width - 18, y + 82), 3)\n\n        draw_text("CURRENT TURN", small_font, MUTED, x + 18, y + 98)\n        pygame.draw.rect(screen, PALETTE[self.current], (x + 18, y + 119, 14, 35), border_radius=5)\n        draw_text(PLAYER_NAMES[self.current], font, INK, x + 42, y + 126)\n\n        # Dice\n        dice_rect = pygame.Rect(x + 78, y + 166, 92, 88)\n        pygame.draw.rect(screen, WHITE, dice_rect, border_radius=17)\n        pygame.draw.rect(screen, SAFFRON, dice_rect, 3, border_radius=17)\n        value = self.dice_anim_value if pygame.time.get_ticks() < self.dice_anim_until else (self.dice or 0)\n        if value:\n            self.draw_die(value, dice_rect)\n        else:\n            draw_text("?", big_font, INK, dice_rect.centerx, dice_rect.centery, "center")\n\n        mouse = pygame.mouse.get_pos()\n        roll_color = lighten(SAFFRON, 25) if self.roll_button.collidepoint(mouse) else SAFFRON\n        pygame.draw.rect(screen, roll_color, self.roll_button, border_radius=14)\n        pygame.draw.rect(screen, GOLD, self.roll_button, 2, border_radius=14)\n        draw_text("🎲  ROLL DICE", font, WHITE, self.roll_button.centerx, self.roll_button.centery, "center")\n\n        reset_color = lighten(DEEP_ORANGE, 25) if self.reset_button.collidepoint(mouse) else DEEP_ORANGE\n        pygame.draw.rect(screen, reset_color, self.reset_button, border_radius=10)\n        draw_text("NEW GAME", small_font, WHITE, self.reset_button.centerx, self.reset_button.centery, "center")\n\n        # Status message\n        msg_y = y + 342\n        pygame.draw.rect(screen, CREAM, (x + 14, msg_y, panel.width - 28, 70), border_radius=10)\n        lines = self.wrap_text(self.message, small_font, panel.width - 48)\n        for i, line in enumerate(lines[:3]):\n            draw_text(line, small_font, INK, x + 24, msg_y + 10 + i * 18)\n\n        # Instructions box\n        box_y = y + 425\n        pygame.draw.rect(screen, (255, 247, 225), (x + 14, box_y, panel.width - 28, 153), border_radius=12)\n        draw_text("HOW TO PLAY", font, DEEP_ORANGE, x + 25, box_y + 12)\n        instructions = [\n            "1. Roll the dice; 6 exits the yard.",\n            "2. Click a glowing token to move.",\n            "3. Exact roll needed to reach home.",\n            "4. Capture rivals for an extra turn.",\n            "5. Gold rings mark safe squares.",\n            "6. First to bring 4 tokens home wins.",\n        ]\n        for i, line in enumerate(instructions):\n            draw_text(line, tiny_font, INK, x + 25, box_y + 42 + i * 17)\n\n        # Tiny footer\n        draw_text("SAFFRON • SUN • DHARMA", tiny_font, MUTED, x + 20, y + 594)\n        draw_text("Local multiplayer · No internet", tiny_font, MUTED, x + 20, y + 612)\n\n        if self.winner is not None:\n            overlay = pygame.Surface((BOARD_SIZE, BOARD_SIZE), pygame.SRCALPHA)\n            overlay.fill((255, 128, 0, 100))\n            screen.blit(overlay, (BOARD_X, BOARD_Y))\n            draw_text("VICTORY!", big_font, WHITE, BOARD_X + BOARD_SIZE // 2,\n                      BOARD_Y + BOARD_SIZE // 2 - 12, "center")\n            draw_text("JAI SHRI RAM", font, WHITE, BOARD_X + BOARD_SIZE // 2,\n                      BOARD_Y + BOARD_SIZE // 2 + 28, "center")\n\n    def draw_die(self, value, rect):\n        dots = {\n            1: [(0, 0)],\n            2: [(-1, -1), (1, 1)],\n            3: [(-1, -1), (0, 0), (1, 1)],\n            4: [(-1, -1), (1, -1), (-1, 1), (1, 1)],\n            5: [(-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)],\n            6: [(-1, -1), (-1, 0), (-1, 1), (1, -1), (1, 0), (1, 1)]\n        }\n        cx, cy = rect.center\n        for dx, dy in dots[value]:\n            pygame.draw.circle(screen, DEEP_ORANGE, (cx + dx * 23, cy + dy * 22), 6)\n\n    @staticmethod\n    def wrap_text(text, fnt, max_width):\n        words = text.split()\n        lines, current = [], ""\n        for word in words:\n            test = (current + " " + word).strip()\n            if fnt.size(test)[0] <= max_width:\n                current = test\n            else:\n                if current:\n                    lines.append(current)\n                current = word\n        if current:\n            lines.append(current)\n        return lines\n\n    def token_at(self, mouse_pos):\n        now = pygame.time.get_ticks()\n        for token in reversed(self.legal_tokens):\n            pos = self.token_draw_position(token, now)\n            if pos and math.dist(mouse_pos, pos) <= 22:\n                return token\n        return None\n\n    def reset(self):\n        self.__init__()\n\ndef main():\n    game = LudoGame()\n    running = True\n    while running:\n        clock.tick(FPS)\n        game.update()\n        for event in pygame.event.get():\n            if event.type == pygame.QUIT:\n                running = False\n            elif event.type == pygame.KEYDOWN:\n                if event.key == pygame.K_ESCAPE:\n                    running = False\n                elif event.key == pygame.K_SPACE:\n                    game.roll()\n                elif event.key == pygame.K_n:\n                    game.reset()\n            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:\n                if game.reset_button.collidepoint(event.pos):\n                    game.reset()\n                elif game.roll_button.collidepoint(event.pos):\n                    game.roll()\n                elif game.awaiting_move:\n                    token = game.token_at(event.pos)\n                    if token:\n                        game.move_token(token)\n\n        screen.fill(BG)\n        # Subtle saffron border\n        pygame.draw.rect(screen, SAFFRON, (5, 5, WIDTH - 10, HEIGHT - 10), 4, border_radius=20)\n        game.draw_board()\n        game.draw_sidebar()\n        pygame.display.flip()\n\n    pygame.quit()\n    sys.exit()\n\nif __name__ == "__main__":\n    main()\n', 'fighters': 'import pygame\nimport random\nimport math\n\n# ==================================================\n# TWO PLAYER FIGHTING GAME\n# Tekken-inspired original 2D fighting game\n# ==================================================\n\npygame.init()\n\nWIDTH = 1100\nHEIGHT = 650\nFPS = 23\n\nscreen = pygame.display.set_mode((WIDTH, HEIGHT))\npygame.display.set_caption("ULTIMATE FIGHTERS - 2 PLAYER")\n\nclock = pygame.time.Clock()\n\n# Fonts\nFONT = pygame.font.SysFont("arial", 22, bold=True)\nBIG_FONT = pygame.font.SysFont("arial", 48, bold=True)\nSMALL_FONT = pygame.font.SysFont("arial", 17, bold=True)\n\n# Colors\nWHITE = (255, 255, 255)\nBLACK = (15, 15, 20)\nRED = (230, 45, 45)\nGREEN = (40, 220, 90)\nYELLOW = (255, 220, 50)\nBLUE = (50, 130, 255)\nGOLD = (255, 180, 40)\n\nGROUND_Y = 535\n\n# ==================================================\n# CHARACTERS\n# ==================================================\n\nHEROES = [\n    {"name": "NEELESH", "color": (35, 150, 255), "speed": 5, "power": 13},\n    {"name": "RAGVENDRA", "color": (235, 60, 55), "speed": 4, "power": 16},\n    {"name": "KARTIK", "color": (40, 220, 120), "speed": 6, "power": 10},\n    {"name": "PRAJWAL", "color": (180, 70, 240), "speed": 5, "power": 12},\n    {"name": "RANJIT", "color": (255, 150, 30), "speed": 4, "power": 17},\n    {"name": "JOGINDER", "color": (50, 210, 220), "speed": 5, "power": 14},\n    {"name": "HIZRU", "color": (245, 90, 160), "speed": 6, "power": 11},\n    {"name": "RAVI", "color": (190, 190, 200), "speed": 5, "power": 13},\n    {"name": "CHITRANJAN", "color": (130, 210, 40), "speed": 4, "power": 18},\n    {"name": "JAGDISH", "color": (255, 210, 60), "speed": 5, "power": 15},\n]\n\nBACKGROUNDS = [\n    "INDIAN TEMPLE",\n    "MOUNTAIN SUNSET",\n    "NEON ARENA"\n]\n\np1_choice = 0\np2_choice = 1\nbg_choice = 0\n\ngame_state = "select"\nwinner_text = ""\n\n# ==================================================\n# DRAW TEXT\n# ==================================================\n\ndef draw_text(text, font, color, x, y, center=True):\n    image = font.render(str(text), True, color)\n    rect = image.get_rect()\n\n    if center:\n        rect.center = (int(x), int(y))\n    else:\n        rect.topleft = (int(x), int(y))\n\n    screen.blit(image, rect)\n\n\n# ==================================================\n# BACKGROUNDS\n# ==================================================\n\ndef draw_temple():\n    screen.fill((25, 35, 65))\n\n    # Sky\n    pygame.draw.circle(screen, (255, 200, 90), (850, 130), 55)\n\n    # Mountains\n    pygame.draw.polygon(\n        screen, (70, 75, 115),\n        [(0, 370), (170, 160), (330, 370)]\n    )\n    pygame.draw.polygon(\n        screen, (90, 90, 130),\n        [(250, 370), (500, 190), (730, 370)]\n    )\n    pygame.draw.polygon(\n        screen, (55, 65, 105),\n        [(600, 370), (850, 170), (1100, 370)]\n    )\n\n    # Temple\n    pygame.draw.rect(screen, (150, 85, 45), (390, 270, 320, 260))\n    pygame.draw.polygon(\n        screen, (220, 145, 55),\n        [(350, 270), (550, 155), (750, 270)]\n    )\n\n    pygame.draw.rect(screen, (90, 50, 35), (500, 350, 100, 180))\n\n    for x in (420, 665):\n        pygame.draw.rect(screen, (225, 175, 95), (x, 290, 30, 240))\n\n    # Ground\n    pygame.draw.rect(screen, (65, 100, 55), (0, 500, WIDTH, 150))\n    pygame.draw.line(screen, (140, 165, 90), (0, 500), (WIDTH, 500), 4)\n\n\ndef draw_mountains():\n    screen.fill((255, 130, 75))\n\n    pygame.draw.circle(screen, (255, 225, 120), (820, 140), 65)\n\n    pygame.draw.polygon(\n        screen, (120, 65, 105),\n        [(0, 430), (220, 130), (430, 430)]\n    )\n    pygame.draw.polygon(\n        screen, (95, 65, 110),\n        [(280, 430), (550, 100), (850, 430)]\n    )\n    pygame.draw.polygon(\n        screen, (70, 55, 100),\n        [(680, 430), (950, 170), (1100, 380), (1100, 500), (0, 500)]\n    )\n\n    pygame.draw.rect(screen, (55, 90, 65), (0, 500, WIDTH, 150))\n    pygame.draw.line(screen, (130, 175, 90), (0, 500), (WIDTH, 500), 4)\n\n\ndef draw_neon():\n    screen.fill((15, 8, 35))\n\n    # Neon grid\n    for x in range(0, WIDTH, 55):\n        pygame.draw.line(screen, (65, 30, 105), (550, 350), (x, 540), 1)\n\n    for y in range(370, 540, 20):\n        pygame.draw.line(screen, (70, 25, 110), (0, y), (WIDTH, y), 1)\n\n    # Neon panels\n    pygame.draw.rect(screen, (30, 15, 65), (0, 0, WIDTH, 350))\n\n    pygame.draw.rect(screen, (30, 210, 255), (65, 100, 15, 160))\n    pygame.draw.rect(screen, (235, 40, 180), (1020, 100, 15, 160))\n\n    pygame.draw.rect(screen, (35, 20, 65), (300, 100, 500, 190), 3)\n    draw_text("FIGHT ARENA", FONT, (50, 225, 255), 550, 190)\n\n    pygame.draw.rect(screen, (25, 20, 40), (0, 500, WIDTH, 150))\n    pygame.draw.line(screen, (40, 220, 255), (0, 500), (WIDTH, 500), 3)\n\n\ndef draw_background():\n    if bg_choice == 0:\n        draw_temple()\n    elif bg_choice == 1:\n        draw_mountains()\n    else:\n        draw_neon()\n\n\n# ==================================================\n# FIGHTER CLASS\n# ==================================================\n\nclass Fighter:\n\n    def __init__(self, x, hero_index, player_number):\n        self.hero_index = hero_index\n        self.data = HEROES[hero_index]\n        self.player_number = player_number\n\n        self.x = float(x)\n        self.y = float(GROUND_Y - 105)\n\n        self.width = 48\n        self.height = 105\n\n        self.vx = 0\n        self.vy = 0\n\n        self.speed = self.data["speed"]\n        self.health = 100\n        self.facing = 1 if player_number == 1 else -1\n\n        self.attack_timer = 0\n        self.attack_kind = ""\n        self.hit_this_attack = False\n\n        self.blocking = False\n        self.jump_count = 0\n        self.flash_timer = 0\n\n        self.combo = 0\n        self.combo_timer = 0\n\n    @property\n    def rect(self):\n        return pygame.Rect(\n            int(self.x - self.width / 2),\n            int(self.y),\n            self.width,\n            self.height\n        )\n\n    def jump(self):\n        if self.jump_count == 0:\n            self.vy = -15\n            self.jump_count = 1\n\n    def attack(self, kind):\n        if self.attack_timer <= 0:\n            self.attack_kind = kind\n            self.attack_timer = 9 if kind == "punch" else 13\n            self.hit_this_attack = False\n\n    def move(self, keys, controls, opponent):\n\n        self.vx = 0\n        self.blocking = False\n\n        if keys[controls["left"]]:\n            self.vx = -self.speed\n            self.facing = -1\n\n        if keys[controls["right"]]:\n            self.vx = self.speed\n            self.facing = 1\n\n        if keys[controls["block"]]:\n            self.blocking = True\n            self.vx *= 0.25\n\n        self.x += self.vx\n\n        # Keep fighters inside the arena\n        self.x = max(35, min(WIDTH - 35, self.x))\n\n        # Gravity\n        self.vy += 0.8\n        self.y += self.vy\n\n        ground_top = GROUND_Y - self.height\n\n        if self.y >= ground_top:\n            self.y = ground_top\n            self.vy = 0\n            self.jump_count = 0\n\n        # Face the opponent when not moving\n        if abs(self.vx) < 0.1:\n            self.facing = 1 if opponent.x > self.x else -1\n\n        if self.attack_timer > 0:\n            self.attack_timer -= 1\n\n        if self.flash_timer > 0:\n            self.flash_timer -= 1\n\n        if self.combo_timer > 0:\n            self.combo_timer -= 1\n        else:\n            self.combo = 0\n\n    def attack_rect(self):\n        reach = 70 if self.attack_kind == "punch" else 85\n\n        top = self.y + 25 if self.attack_kind == "punch" else self.y + 50\n\n        return pygame.Rect(\n            int(self.x + self.facing * 15 - (0 if self.facing > 0 else reach)),\n            int(top),\n            reach,\n            35\n        )\n\n    def try_hit(self, opponent):\n\n        if self.attack_timer <= 0:\n            return\n\n        if self.hit_this_attack:\n            return\n\n        # Attack connects during the active frames\n        if self.attack_timer > 7:\n            return\n\n        if self.attack_rect().colliderect(opponent.rect):\n\n            self.hit_this_attack = True\n\n            if opponent.blocking:\n                damage = 2\n            else:\n                damage = self.data["power"]\n                opponent.flash_timer = 5\n                opponent.combo += 1\n                opponent.combo_timer = 40\n\n                # Small pushback\n                opponent.x += self.facing * 18\n\n            opponent.health = max(0, opponent.health - damage)\n\n    def draw(self):\n\n        body_color = self.data["color"]\n\n        if self.flash_timer > 0:\n            body_color = WHITE\n\n        # Shadow\n        pygame.draw.ellipse(\n            screen,\n            (25, 25, 25),\n            (int(self.x - 34), GROUND_Y - 9, 68, 15)\n        )\n\n        # Body proportions\n        head_size = 28\n        head_x = int(self.x)\n        head_y = int(self.y + 18)\n\n        torso = pygame.Rect(\n            int(self.x - 18),\n            int(self.y + 35),\n            36,\n            36\n        )\n\n        # Head\n        pygame.draw.circle(screen, (225, 180, 140), (head_x, head_y), head_size // 2)\n\n        # Hair/headband\n        pygame.draw.arc(\n            screen, body_color,\n            (head_x - 15, head_y - 15, 30, 25),\n            math.pi, 2 * math.pi, 5\n        )\n\n        # Eyes\n        eye_x = head_x + self.facing * 7\n        pygame.draw.circle(screen, BLACK, (eye_x, head_y - 1), 2)\n\n        # Torso\n        pygame.draw.rect(screen, body_color, torso, border_radius=5)\n\n        # Belt\n        pygame.draw.rect(\n            screen, (35, 25, 25),\n            (int(self.x - 18), int(self.y + 62), 36, 7)\n        )\n\n        # Arms\n        arm_y = int(self.y + 43)\n        left_arm = (int(self.x - 15), arm_y)\n        right_arm = (int(self.x + 15), arm_y)\n\n        if self.attack_timer > 0:\n            active = 70 if self.attack_kind == "punch" else 58\n\n            start = (int(self.x + self.facing * 14), arm_y)\n            end = (\n                int(self.x + self.facing * active),\n                int(self.y + (42 if self.attack_kind == "punch" else 60))\n            )\n\n            pygame.draw.line(screen, body_color, start, end, 12)\n            pygame.draw.circle(screen, (225, 180, 140), end, 8)\n\n            # Other arm\n            pygame.draw.line(\n                screen, body_color,\n                (int(self.x - self.facing * 13), arm_y),\n                (int(self.x - self.facing * 30), int(self.y + 65)),\n                10\n            )\n\n        elif self.blocking:\n            pygame.draw.line(\n                screen, body_color,\n                (int(self.x - 15), int(self.y + 45)),\n                (int(self.x - self.facing * 5), int(self.y + 25)),\n                10\n            )\n\n            pygame.draw.line(\n                screen, body_color,\n                (int(self.x + 15), int(self.y + 45)),\n                (int(self.x + self.facing * 5), int(self.y + 25)),\n                10\n            )\n\n        else:\n            pygame.draw.line(\n                screen, body_color,\n                left_arm,\n                (int(self.x - 25), int(self.y + 70)),\n                10\n            )\n\n            pygame.draw.line(\n                screen, body_color,\n                right_arm,\n                (int(self.x + 25), int(self.y + 70)),\n                10\n            )\n\n        # Legs\n        leg_y = int(self.y + 70)\n\n        if self.attack_timer > 0 and self.attack_kind == "kick":\n\n            pygame.draw.line(\n                screen, body_color,\n                (int(self.x + self.facing * 7), leg_y),\n                (int(self.x + self.facing * 58), leg_y + 7),\n                14\n            )\n\n            pygame.draw.line(\n                screen, body_color,\n                (int(self.x - 8), leg_y),\n                (int(self.x - 14), int(self.y + 100)),\n                13\n            )\n\n        else:\n\n            pygame.draw.line(\n                screen, body_color,\n                (int(self.x - 8), leg_y),\n                (int(self.x - 12), int(self.y + 100)),\n                13\n            )\n\n            pygame.draw.line(\n                screen, body_color,\n                (int(self.x + 8), leg_y),\n                (int(self.x + 12), int(self.y + 100)),\n                13\n            )\n\n        # Block shield\n        if self.blocking:\n            pygame.draw.circle(\n                screen,\n                (100, 190, 255),\n                (int(self.x), int(self.y + 50)),\n                38,\n                3\n            )\n\n        # Player label\n        label = f"P{self.player_number}: {self.data[\'name\']}"\n\n        draw_text(\n            label, SMALL_FONT, WHITE,\n            self.x, self.y - 20\n        )\n\n\n# ==================================================\n# HEALTH BARS\n# ==================================================\n\ndef draw_health_bars(p1, p2):\n\n    # Player 1\n    draw_text(\n        f"P1 - {p1.data[\'name\']}",\n        FONT, WHITE, 235, 35\n    )\n\n    pygame.draw.rect(screen, (60, 20, 20), (60, 55, 350, 28))\n    pygame.draw.rect(\n        screen, GREEN,\n        (60, 55, int(350 * p1.health / 100), 28)\n    )\n\n    pygame.draw.rect(screen, WHITE, (60, 55, 350, 28), 2)\n\n    # Player 2\n    draw_text(\n        f"P2 - {p2.data[\'name\']}",\n        FONT, WHITE, 865, 35\n    )\n\n    pygame.draw.rect(screen, (60, 20, 20), (690, 55, 350, 28))\n    pygame.draw.rect(\n        screen, RED,\n        (\n            690 + 350 - int(350 * p2.health / 100),\n            55,\n            int(350 * p2.health / 100),\n            28\n        )\n    )\n\n    pygame.draw.rect(screen, WHITE, (690, 55, 350, 28), 2)\n\n\n# ==================================================\n# CHARACTER SELECTION\n# ==================================================\n\ndef draw_character_preview(hero, x, y, selected, player_num):\n\n    box = pygame.Rect(x - 100, y - 90, 200, 180)\n\n    border = GOLD if selected else (100, 100, 130)\n\n    pygame.draw.rect(screen, (30, 30, 48), box, border_radius=10)\n    pygame.draw.rect(screen, border, box, 4 if selected else 2, border_radius=10)\n\n    # Character preview\n    pygame.draw.circle(screen, (225, 180, 140), (x, y - 35), 22)\n\n    pygame.draw.rect(\n        screen,\n        hero["color"],\n        (x - 25, y - 10, 50, 65),\n        border_radius=7\n    )\n\n    pygame.draw.line(\n        screen, hero["color"],\n        (x - 15, y + 5), (x - 32, y + 35), 10\n    )\n\n    pygame.draw.line(\n        screen, hero["color"],\n        (x + 15, y + 5), (x + 32, y + 35), 10\n    )\n\n    pygame.draw.line(\n        screen, hero["color"],\n        (x - 10, y + 52), (x - 15, y + 78), 12\n    )\n\n    pygame.draw.line(\n        screen, hero["color"],\n        (x + 10, y + 52), (x + 15, y + 78), 12\n    )\n\n    draw_text(hero["name"], FONT, WHITE, x, y + 100)\n\n    draw_text(\n        f"POWER {hero[\'power\']}   SPEED {hero[\'speed\']}",\n        SMALL_FONT, YELLOW, x, y + 125\n    )\n\n\ndef draw_selection():\n\n    screen.fill((12, 12, 28))\n\n    # Decorative arena lights\n    for x in range(30, WIDTH, 100):\n        pygame.draw.circle(screen, (35, 40, 85), (x, 40), 20)\n\n    draw_text(\n        "ULTIMATE FIGHTERS",\n        BIG_FONT, GOLD, WIDTH // 2, 60\n    )\n\n    draw_text(\n        "2 PLAYER LOCAL BATTLE",\n        FONT, WHITE, WIDTH // 2, 105\n    )\n\n    draw_text(\n        "PLAYER 1: A / D TO SELECT",\n        FONT, (70, 180, 255), 270, 155\n    )\n\n    draw_text(\n        "PLAYER 2: LEFT / RIGHT TO SELECT",\n        FONT, (255, 100, 100), 820, 155\n    )\n\n    draw_character_preview(\n        HEROES[p1_choice], 270, 275, True, 1\n    )\n\n    draw_character_preview(\n        HEROES[p2_choice], 820, 275, True, 2\n    )\n\n    pygame.draw.line(\n        screen, (100, 100, 150),\n        (550, 165), (550, 430), 3\n    )\n\n    draw_text(\n        f"BACKGROUND: {BACKGROUNDS[bg_choice]}",\n        FONT, YELLOW, WIDTH // 2, 460\n    )\n\n    draw_text(\n        "UP / DOWN: CHANGE BACKGROUND",\n        SMALL_FONT, WHITE, WIDTH // 2, 493\n    )\n\n    draw_text(\n        "ENTER: START FIGHT",\n        FONT, GREEN, WIDTH // 2, 540\n    )\n\n    draw_text(\n        "P1: WASD + F PUNCH + G KICK + H BLOCK",\n        SMALL_FONT, WHITE, WIDTH // 2, 580\n    )\n\n    draw_text(\n        "P2: ARROWS + K PUNCH + L KICK + J BLOCK",\n        SMALL_FONT, WHITE, WIDTH // 2, 610\n    )\n\n\n# ==================================================\n# START BATTLE\n# ==================================================\n\ndef start_battle():\n    p1 = Fighter(300, p1_choice, 1)\n    p2 = Fighter(800, p2_choice, 2)\n\n    return p1, p2\n\n\np1, p2 = start_battle()\n\n# Controls\nP1_CONTROLS = {\n    "left": pygame.K_a,\n    "right": pygame.K_d,\n    "block": pygame.K_h,\n}\n\nP2_CONTROLS = {\n    "left": pygame.K_LEFT,\n    "right": pygame.K_RIGHT,\n    "block": pygame.K_j,\n}\n\n\n# ==================================================\n# GAME LOOP\n# ==================================================\n\nrunning = True\n\nwhile running:\n\n    clock.tick(FPS)\n\n    for event in pygame.event.get():\n\n        if event.type == pygame.QUIT:\n            running = False\n\n        if event.type == pygame.KEYDOWN:\n\n            if event.key == pygame.K_ESCAPE:\n                if game_state == "fight":\n                    game_state = "select"\n                else:\n                    running = False\n\n            # Selection screen\n            if game_state == "select":\n\n                if event.key == pygame.K_a:\n                    p1_choice = (p1_choice - 1) % len(HEROES)\n\n                if event.key == pygame.K_d:\n                    p1_choice = (p1_choice + 1) % len(HEROES)\n\n                if event.key == pygame.K_LEFT:\n                    p2_choice = (p2_choice - 1) % len(HEROES)\n\n                if event.key == pygame.K_RIGHT:\n                    p2_choice = (p2_choice + 1) % len(HEROES)\n\n                if event.key == pygame.K_UP:\n                    bg_choice = (bg_choice - 1) % len(BACKGROUNDS)\n\n                if event.key == pygame.K_DOWN:\n                    bg_choice = (bg_choice + 1) % len(BACKGROUNDS)\n\n                if event.key == pygame.K_RETURN:\n\n                    if p1_choice == p2_choice:\n                        p2_choice = (p2_choice + 1) % len(HEROES)\n\n                    p1, p2 = start_battle()\n                    game_state = "fight"\n                    winner_text = ""\n\n            # Fight controls\n            elif game_state == "fight":\n\n                if p1.health > 0 and p2.health > 0:\n\n                    if event.key == pygame.K_w:\n                        p1.jump()\n\n                    if event.key == pygame.K_f:\n                        p1.attack("punch")\n\n                    if event.key == pygame.K_g:\n                        p1.attack("kick")\n\n                    if event.key == pygame.K_UP:\n                        p2.jump()\n\n                    if event.key == pygame.K_k:\n                        p2.attack("punch")\n\n                    if event.key == pygame.K_l:\n                        p2.attack("kick")\n\n                # Restart after winner screen\n                elif event.key == pygame.K_RETURN:\n                    p1, p2 = start_battle()\n                    winner_text = ""\n\n    keys = pygame.key.get_pressed()\n\n    if game_state == "select":\n\n        draw_selection()\n\n    elif game_state == "fight":\n\n        draw_background()\n\n        if p1.health > 0 and p2.health > 0:\n\n            p1.move(keys, P1_CONTROLS, p2)\n            p2.move(keys, P2_CONTROLS, p1)\n\n            p1.try_hit(p2)\n            p2.try_hit(p1)\n\n            if p1.health <= 0:\n                winner_text = "PLAYER 2 WINS!"\n\n            elif p2.health <= 0:\n                winner_text = "PLAYER 1 WINS!"\n\n        # Draw fighters\n        p1.draw()\n        p2.draw()\n\n        # Health bars\n        draw_health_bars(p1, p2)\n\n        # Fight title\n        draw_text(\n            "ROUND 1",\n            FONT, GOLD, WIDTH // 2, 40\n        )\n\n        # Winner panel\n        if winner_text:\n\n            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)\n            overlay.fill((0, 0, 0, 175))\n            screen.blit(overlay, (0, 0))\n\n            draw_text(\n                winner_text,\n                BIG_FONT, GOLD,\n                WIDTH // 2, HEIGHT // 2 - 30\n            )\n\n            draw_text(\n                "PRESS ENTER TO REMATCH",\n                FONT, WHITE,\n                WIDTH // 2, HEIGHT // 2 + 35\n            )\n\n            draw_text(\n                "PRESS ESC FOR CHARACTER SELECT",\n                SMALL_FONT, WHITE,\n                WIDTH // 2, HEIGHT // 2 + 75\n            )\n\n    pygame.display.flip()\n\npygame.quit()\n'}

GAME_FILES = {
    "tictactoe": ("TIC TAC TOE", "TIC_TAC_TOE.py"),
    "ludo": ("LUDO", "LUDO.py"),
    "fighters": ("TWO PLAYER FIGHTING GAME", "NEELESH_FIGHTERS.py"),
}
_game_server = None

def _game_chooser_html(port):
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GAMES BY NEELESH BHATT</title>
<style>*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;background:radial-gradient(circle at top,#47230b,#100804 65%);color:#fff3dc;font-family:Segoe UI,Arial,sans-serif;display:grid;place-items:center;padding:24px}}main{{width:min(850px,100%)}}header{{text-align:center;margin-bottom:28px}}h1{{font-size:clamp(30px,6vw,54px);color:#ff8c00;margin:0;text-shadow:0 0 20px #ff8c0060}}header p{{color:#ffd7a1}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:18px}}button{{width:100%;min-height:170px;border:2px solid #ffad33;border-radius:18px;background:linear-gradient(145deg,#331809,#1a0c05);color:#fff3dc;font-size:22px;font-weight:800;cursor:pointer;padding:20px;transition:.18s}}button:hover{{transform:translateY(-4px);background:#572707;box-shadow:0 10px 28px #ff8c0030}}small{{display:block;color:#ffc477;font-size:13px;font-weight:500;margin-top:12px}}#status{{text-align:center;min-height:28px;color:#ffcf88;margin-top:22px}}footer{{text-align:center;color:#ba9977;margin-top:20px;font-size:13px}}</style></head><body><main><header><h1>GAMES BY NEELESH BHATT</h1><p>Choose a game — it opens in its own application window.</p></header><section class="grid"><button onclick="launch('tictactoe')">✕ TIC TAC TOE<small>Two-player or vs computer</small></button><button onclick="launch('ludo')">🎲 LUDO<small>Local pass-and-play board game</small></button><button onclick="launch('fighters')">⚔ FIGHTING GAME<small>Original two-player fighter</small></button></section><div id="status"></div><footer>Local launcher for SHIVA AI • © 2026 Neelesh Bhatt and Co.</footer></main><script>async function launch(game){{const s=document.getElementById('status');s.textContent='Starting game…';try{{const r=await fetch('http://127.0.0.1:{port}/launch/'+game,{{method:'POST'}});const j=await r.json();s.textContent=j.message||'Request finished.'}}catch(e){{s.textContent='Launcher not responding. Keep SHIVA running and reopen this page.'}}}}</script></body></html>'''

class _GameLaunchHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split('?', 1)[0] == '/images':
            payload = _image_creator_html(self.server.server_address[1]).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_response(404); self.send_header('Content-Length', '0'); self.end_headers()

    def do_POST(self):
        if self.path.split('?', 1)[0] == '/generate-image':
            self.send_json(410, {"ok": False, "message": "This version uses the free browser-based image creator and does not use API keys."})
            return
        key = self.path.rsplit('/', 1)[-1]
        if key not in GAME_FILES:
            self.send_json(404, {"ok": False, "message": "Unknown game."}); return
        label, filename = GAME_FILES[key]
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        try:
            # Create the selected game's script from the code embedded in this one file.
            source_key = {"TIC_TAC_TOE.py": "tictactoe", "LUDO.py": "ludo", "NEELESH_FIGHTERS.py": "fighters"}[filename]
            with open(script_path, "w", encoding="utf-8") as game_file:
                game_file.write(GAME_SOURCE[source_key])
            subprocess.Popen([sys.executable, script_path], cwd=os.path.dirname(script_path), close_fds=True)
            self.send_json(200, {"ok": True, "message": label + " launched in its own window."})
        except Exception as exc:
            self.send_json(500, {"ok": False, "message": "Launch error: " + str(exc)})
    def send_json(self, status, obj):
        payload = json.dumps(obj).encode('utf-8')
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Access-Control-Allow-Origin','*'); self.send_header('Content-Length',str(len(payload))); self.end_headers(); self.wfile.write(payload)
    def do_OPTIONS(self):
        self.send_response(204); self.send_header('Access-Control-Allow-Origin','*'); self.send_header('Access-Control-Allow-Methods','POST, OPTIONS'); self.send_header('Access-Control-Allow-Headers','Content-Type'); self.end_headers()
    def log_message(self, fmt, *args): pass

def open_games_page():
    global _game_server
    try:
        if _game_server is None:
            _game_server = HTTPServer(('127.0.0.1', 0), _GameLaunchHandler)
            threading.Thread(target=_game_server.serve_forever, daemon=True).start()
        page_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'SHIVA_Games_Chooser.html')
        with open(page_path, 'w', encoding='utf-8') as f: f.write(_game_chooser_html(_game_server.server_address[1]))
        webbrowser.open_new_tab('file:///' + page_path.replace(os.sep, '/').replace(' ', '%20'))
    except Exception as exc:
        add_chat('SHIVA', 'Could not open games chooser: ' + str(exc))

# =========================================================
# SHIVA THEME SWITCHER — changes only the SHIVA desktop UI
# =========================================================
THEME_PRESETS = [
    {
        "name": "MATRIX GREEN",
        "BLACK": "#020403", "DARK": "#050907", "PANEL": "#07100b", "PANEL2": "#0a160e",
        "GREEN": "#00ff66", "GREEN2": "#00cc55", "GREEN_DARK": "#075c2b", "GREEN_DIM": "#164d2d",
        "WHITE_GREEN": "#caffdc", "MUTED": "#4c8a63", "RED": "#ff304f", "accent": "#00ff66",
        "button_bg": "#00cc55", "button_fg": "#020403"
    },
    {
        "name": "MONEY HEIST // RED ALERT",
        "BLACK": "#080507", "DARK": "#13070b", "PANEL": "#1d0b12", "PANEL2": "#2a1019",
        "GREEN": "#ff304f", "GREEN2": "#d71936", "GREEN_DARK": "#7d1528", "GREEN_DIM": "#541222",
        "WHITE_GREEN": "#ffe9ed", "MUTED": "#d07b89", "RED": "#ff304f", "accent": "#ff304f",
        "button_bg": "#ff304f", "button_fg": "#080507"
    },
    {
        "name": "BREAKING BAD // DESERT TEAL",
        "BLACK": "#061014", "DARK": "#091b20", "PANEL": "#0c2529", "PANEL2": "#123238",
        "GREEN": "#75d6b1", "GREEN2": "#36bda0", "GREEN_DARK": "#24665e", "GREEN_DIM": "#1a4a48",
        "WHITE_GREEN": "#e0fff4", "MUTED": "#80b7ac", "RED": "#f26b5b", "accent": "#75d6b1",
        "button_bg": "#75d6b1", "button_fg": "#061014"
    },
    {
        "name": "BETTER CALL SAUL // GOLD",
        "BLACK": "#100c08", "DARK": "#19120a", "PANEL": "#261a0c", "PANEL2": "#35230e",
        "GREEN": "#ffc247", "GREEN2": "#e8a82d", "GREEN_DARK": "#80551a", "GREEN_DIM": "#604319",
        "WHITE_GREEN": "#fff2d5", "MUTED": "#c8a66d", "RED": "#ff684a", "accent": "#ffc247",
        "button_bg": "#ffc247", "button_fg": "#100c08"
    },
    {
        "name": "CYBER BLUE // NIGHT OPS",
        "BLACK": "#030712", "DARK": "#07111f", "PANEL": "#0a1b30", "PANEL2": "#102743",
        "GREEN": "#4dd9ff", "GREEN2": "#20b8e6", "GREEN_DARK": "#14517a", "GREEN_DIM": "#123b59",
        "WHITE_GREEN": "#e0f7ff", "MUTED": "#79a9c4", "RED": "#ff5577", "accent": "#4dd9ff",
        "button_bg": "#4dd9ff", "button_fg": "#030712"
    },
]
_active_theme_index = 0
_theme_button = None


def _walk_widgets(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk_widgets(child)


def apply_shiva_theme(index):
    """Apply a preset to SHIVA's Tkinter window without changing Heisenberg's page."""
    global _active_theme_index, BLACK, DARK, PANEL, PANEL2, GREEN, GREEN2
    global GREEN_DARK, GREEN_DIM, WHITE_GREEN, MUTED, RED
    index = index % len(THEME_PRESETS)
    new = THEME_PRESETS[index]
    old = THEME_PRESETS[_active_theme_index]
    color_keys = ("BLACK", "DARK", "PANEL", "PANEL2", "GREEN", "GREEN2", "GREEN_DARK", "GREEN_DIM", "WHITE_GREEN", "MUTED", "RED")
    color_map = {old[k].lower(): new[k] for k in color_keys}
    color_map.update({"#ffffff": new["WHITE_GREEN"], "white": new["WHITE_GREEN"], "#000000": new["BLACK"]})

    # Update globals used by the live animation renderers.
    for key in color_keys:
        globals()[key] = new[key]
    _active_theme_index = index

    for widget in _walk_widgets(root):
        try:
            options = widget.configure()
        except Exception:
            continue
        for option in ("bg", "background", "fg", "foreground", "insertbackground", "selectbackground",
                       "selectforeground", "activebackground", "activeforeground", "highlightbackground",
                       "highlightcolor", "troughcolor"):
            try:
                if option not in options:
                    continue
                current = str(widget.cget(option)).lower()
                if current in color_map:
                    widget.configure(**{option: color_map[current]})
            except Exception:
                pass
        try:
            if isinstance(widget, tk.Canvas):
                for item in widget.find_all():
                    for option in ("fill", "outline"):
                        try:
                            value = str(widget.itemcget(item, option)).lower()
                            if value in color_map:
                                widget.itemconfigure(item, **{option: color_map[value]})
                        except Exception:
                            pass
        except Exception:
            pass

    # Keep chat transcript tags in step with the active palette.
    try:
        chat_text.tag_config("YOU", foreground=GREEN)
        chat_text.tag_config("SHIVA", foreground=WHITE_GREEN)
    except Exception:
        pass
    try:
        status_label.configure(fg=GREEN, bg=BLACK)
    except Exception:
        pass
    try:
        _theme_button.configure(text="🎨 THEME: " + new["name"], bg=new["button_bg"], fg=new["button_fg"],
                                activebackground=new["accent"], activeforeground=new["button_fg"])
    except Exception:
        pass
    try:
        root.title("SHIVA // HACKER COMMAND CENTER — " + new["name"])
    except Exception:
        pass


def cycle_shiva_theme():
    apply_shiva_theme(_active_theme_index + 1)


_theme_button = tk.Button(
    left_panel, text="🎨 THEME: MATRIX GREEN", command=cycle_shiva_theme,
    font=("Consolas", 10, "bold"), fg=BLACK, bg="#00cc55",
    activeforeground=BLACK, activebackground=GREEN, relief="flat", bd=0,
    cursor="hand2", padx=7, pady=12, wraplength=220
)
_theme_button.pack(side="bottom", fill="x", padx=12, pady=(0, 10))


games_button = tk.Button(left_panel, text='GAMES BY NEELESH BHATT', command=open_games_page,
    font=('Consolas', 11, 'bold'), fg=BLACK, bg='#ffad33', activeforeground=BLACK,
    activebackground='#ffd080', relief='flat', bd=0, cursor='hand2', padx=7, pady=12, wraplength=220)
games_button.pack(side='bottom', fill='x', padx=12, pady=(0, 10))

images_by_button = tk.Button(left_panel, text="⚗ OPEN HEISENBERG AI IN CHROME", command=open_images_page,
    font=('Consolas', 11, 'bold'), fg=BLACK, bg='#ff8c00',
    activeforeground=BLACK, activebackground='#ffc266', relief='flat', bd=0,
    cursor='hand2', padx=7, pady=10, wraplength=220)
images_by_button.pack(side='bottom', fill='x', padx=12, pady=(0, 10))

copyright_button = tk.Button(
    left_panel,
    text="©  COPYRIGHT",
    command=open_copyright_page,
    font=("Consolas", 14, "bold"),
    fg=BLACK,
    bg=COPYRIGHT_ORANGE,
    activeforeground=BLACK,
    activebackground="#ffad33",
    relief="flat",
    bd=0,
    cursor="hand2",
    padx=12,
    pady=12
)

copyright_button.pack(
    side="bottom",
    fill="x",
    padx=12,
    pady=14
)


# =========================================================
# CENTER
# =========================================================

center = tk.Frame(
    main,
    bg=BLACK
)

center.pack(
    side="left",
    fill="both",
    expand=True
)


# =========================================================
# RADAR + MATRIX CANVAS
# =========================================================

visual_frame = tk.Frame(
    center,
    bg=BLACK
)

visual_frame.pack(
    fill="both",
    expand=True
)


canvas = tk.Canvas(
    visual_frame,
    bg=BLACK,
    highlightthickness=0
)

canvas.pack(
    fill="both",
    expand=True
)


# =========================================================
# MATRIX CODE
# =========================================================

code_columns = []

code_chars = "01ABCDEFGHIJKLMNOPQRSTUVWXYZ<>[]{}#$%@&"


def setup_code():

    code_columns.clear()

    width = canvas.winfo_width()

    if width < 100:
        width = 900

    count = max(
        10,
        width // 22
    )

    for i in range(count):

        code_columns.append({
            "x": i * 22 + random.randint(-4, 4),
            "y": random.randint(-500, 0),
            "speed": random.randint(2, 7),
            "length": random.randint(4, 14)
        })


setup_done = False
_theme_fx_frame = 0


def draw_theme_animation():
    """Draw lightweight theme-specific motion on SHIVA's existing visual canvas."""
    global _theme_fx_frame
    _theme_fx_frame += 1
    canvas.delete("theme_fx")
    width = max(canvas.winfo_width(), 320)
    height = max(canvas.winfo_height(), 240)
    phase = _theme_fx_frame
    theme_index = _active_theme_index

    # Theme decorations are drawn around the central radar.
    right_x = width - 125
    top_y = 80

    if theme_index == 1:  # Money Heist — animated cash and coins
        for i in range(3):
            x = 42 + i * 66 + math.sin((phase + i * 18) / 11) * 13
            y = 58 + ((phase * (1 + i % 2) + i * 73) % max(100, height - 110))
            canvas.create_rectangle(x, y, x + 48, y + 27, outline="#ff304f", width=2, tags="theme_fx")
            canvas.create_oval(x + 16, y + 5, x + 31, y + 22, outline="#ff8a9b", width=1, tags="theme_fx")
            canvas.create_text(x + 24, y + 13, text="$", fill="#ffe9ed", font=("Consolas", 11, "bold"), tags="theme_fx")
        for i in range(4):
            x = right_x + math.sin((phase + i * 21) / 9) * 22
            y = 45 + ((phase * 2 + i * 61) % max(120, height - 80))
            canvas.create_oval(x - 10, y - 10, x + 10, y + 10, outline="#ffc247", width=2, tags="theme_fx")
            canvas.create_text(x, y, text="$", fill="#ffc247", font=("Consolas", 9, "bold"), tags="theme_fx")

    elif theme_index == 2:  # Breaking Bad-inspired chemistry — labels and molecules
        chemicals = [("H₂O", "WATER"), ("NaCl", "SALT"), ("C₂H₆O", "ETHANOL"), ("CO₂", "CARBON DIOXIDE"), ("NH₃", "AMMONIA")]
        idx = (phase // 24) % len(chemicals)
        formula, name = chemicals[idx]
        box_x, box_y = right_x - 38, top_y + 18 + int(8 * math.sin(phase / 10))
        canvas.create_rectangle(box_x, box_y, box_x + 112, box_y + 66, outline="#75d6b1", width=2, tags="theme_fx")
        canvas.create_text(box_x + 56, box_y + 23, text=formula, fill="#e0fff4", font=("Consolas", 17, "bold"), tags="theme_fx")
        canvas.create_text(box_x + 56, box_y + 47, text=name, fill="#75d6b1", font=("Consolas", 7, "bold"), tags="theme_fx")
        nodes = [(width - 205, height - 120), (width - 155, height - 150), (width - 105, height - 120), (width - 155, height - 85)]
        for a, b in ((0, 1), (1, 2), (1, 3), (3, 0)):
            canvas.create_line(*nodes[a], *nodes[b], fill="#36bda0", width=2, tags="theme_fx")
        for i, (x, y) in enumerate(nodes):
            r = 8 + (2 if (phase // 8 + i) % 2 else 0)
            canvas.create_oval(x-r, y-r, x+r, y+r, outline="#e0fff4", width=2, tags="theme_fx")

    elif theme_index == 3:  # Better Call Saul-inspired legal graphics
        legal_words = ["CASE FILE  •  001", "OBJECTION!", "COURT IN SESSION", "LEGAL BRIEF", "VERDICT PENDING"]
        word = legal_words[(phase // 28) % len(legal_words)]
        banner_y = 72 + int(6 * math.sin(phase / 12))
        canvas.create_rectangle(right_x - 92, banner_y - 20, right_x + 92, banner_y + 20,
                                outline="#ffc247", width=2, tags="theme_fx")
        canvas.create_text(right_x, banner_y, text=word, fill="#fff2d5", font=("Consolas", 9, "bold"), tags="theme_fx")
        # Animated scales of justice (symbolic, no external assets).
        cx, cy = width - 125, height - 105
        swing = math.sin(phase / 12) * 9
        canvas.create_line(cx, cy - 40, cx, cy + 28, fill="#ffc247", width=3, tags="theme_fx")
        canvas.create_line(cx - 48, cy - 20 + swing, cx + 48, cy - 20 - swing, fill="#ffc247", width=3, tags="theme_fx")
        canvas.create_line(cx, cy - 40, cx - 18, cy - 20, fill="#e8a82d", width=2, tags="theme_fx")
        for side, tilt in ((-1, swing), (1, -swing)):
            px = cx + side * 38
            py = cy + 4 + tilt
            canvas.create_line(px, cy - 20 - tilt, px - 16, py + 12, fill="#ffc247", width=1, tags="theme_fx")
            canvas.create_line(px, cy - 20 - tilt, px + 16, py + 12, fill="#ffc247", width=1, tags="theme_fx")
            canvas.create_arc(px - 17, py, px + 17, py + 22, start=180, extent=180, style="arc", outline="#ffc247", width=2, tags="theme_fx")
        canvas.create_line(cx - 25, cy + 30, cx + 25, cy + 30, fill="#ffc247", width=3, tags="theme_fx")

    elif theme_index == 4:  # Cyberpunk HUD/circuit animation, without weapon imagery
        cx, cy = width - 130, height // 2
        radius = 28 + (phase % 36)
        canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius, outline="#4dd9ff", width=2, tags="theme_fx")
        canvas.create_oval(cx-25, cy-25, cx+25, cy+25, outline="#20b8e6", width=1, tags="theme_fx")
        canvas.create_line(cx-58, cy, cx-18, cy, fill="#e0f7ff", width=2, tags="theme_fx")
        canvas.create_line(cx+18, cy, cx+58, cy, fill="#e0f7ff", width=2, tags="theme_fx")
        canvas.create_line(cx, cy-58, cx, cy-18, fill="#e0f7ff", width=2, tags="theme_fx")
        canvas.create_line(cx, cy+18, cx, cy+58, fill="#e0f7ff", width=2, tags="theme_fx")
        circuit_y = 75 + (phase % max(80, height - 110))
        canvas.create_line(30, circuit_y, 70, circuit_y, 70, circuit_y + 20, 105, circuit_y + 20,
                           fill="#4dd9ff", width=2, tags="theme_fx")
        canvas.create_oval(99, circuit_y + 14, 111, circuit_y + 26, outline="#4dd9ff", width=2, tags="theme_fx")
        canvas.create_text(cx, cy + 72, text="SYSTEM // ONLINE", fill="#4dd9ff", font=("Consolas", 8, "bold"), tags="theme_fx")


def draw_matrix():

    global setup_done

    width = canvas.winfo_width()
    height = canvas.winfo_height()

    if width < 100 or height < 100:

        root.after(
            80,
            draw_matrix
        )

        return

    if not setup_done:

        setup_code()
        setup_done = True

    canvas.delete("matrix")

    for column in code_columns:

        x = column["x"]
        y = column["y"]

        # Keep the central display clear for the radar animation.
        if canvas.winfo_width() * 0.30 < x < canvas.winfo_width() * 0.70:
            column["y"] += column["speed"]
            if column["y"] - column["length"] * 17 > height:
                column["y"] = random.randint(-300, -20)
            continue

        for i in range(
            column["length"]
        ):

            char = random.choice(
                code_chars
            )

            yy = y - i * 17

            if yy < 0 or yy > height:
                continue

            if i == 0:
                brightness = GREEN

            elif i < 3:
                brightness = GREEN2

            else:
                brightness = GREEN_DIM

            canvas.create_text(
                x,
                yy,
                text=char,
                fill=brightness,
                font=("Consolas", 11, "bold"),
                tags="matrix"
            )

        column["y"] += column["speed"]

        if (
            column["y"]
            - column["length"] * 17
            > height
        ):

            column["y"] = random.randint(
                -300,
                -20
            )

            column["speed"] = random.randint(
                2,
                7
            )

    draw_theme_animation()

    root.after(
        65,
        draw_matrix
    )


# =========================================================
# LIGHTNING
# =========================================================

def lightning_points(
    x1,
    y1,
    x2,
    y2,
    segments=8
):

    points = [
        (x1, y1)
    ]

    dx = x2 - x1
    dy = y2 - y1

    length = math.sqrt(
        dx * dx + dy * dy
    )

    if length == 0:
        return points

    nx = -dy / length
    ny = dx / length

    for i in range(
        1,
        segments
    ):

        t = i / segments

        x = x1 + dx * t
        y = y1 + dy * t

        offset = random.randint(
            -14,
            14
        )

        x += nx * offset
        y += ny * offset

        points.append(
            (x, y)
        )

    points.append(
        (x2, y2)
    )

    return points


def draw_lightning(
    x1,
    y1,
    x2,
    y2
):

    points = lightning_points(
        x1,
        y1,
        x2,
        y2
    )

    canvas.create_line(
        points,
        fill=LIGHTNING_YELLOW,
        width=4,
        tags="sword"
    )

    canvas.create_line(
        points,
        fill=LIGHTNING_WHITE,
        width=1,
        tags="sword"
    )


# =========================================================
# ANIMATED RADAR CORE — replaces the central sword graphic
# =========================================================

def draw_radar():
    """Draw a large, continuously animated radar in the center instead of the sword."""
    canvas.delete("sword")
    canvas.delete("radar")

    width = canvas.winfo_width()
    height = canvas.winfo_height()
    if width < 200 or height < 200:
        root.after(100, draw_radar)
        return

    cx, cy = width * 0.50, height * 0.46
    radius = max(82, min(width * 0.235, height * 0.32, 220))
    phase = time.monotonic()
    theme = THEME_PRESETS[_active_theme_index]
    accent = theme.get("GREEN", "#00ff66")
    accent2 = theme.get("GREEN2", "#00cc55")
    faint = theme.get("GREEN_DARK", "#075c2b")

    # Dark translucent-looking center plate and bright rings for strong visibility.
    canvas.create_oval(cx-radius-8, cy-radius-8, cx+radius+8, cy+radius+8,
                       fill=BLACK, outline=accent, width=2, tags="radar")
    # Outer glow rings, inner range rings and crosshairs.
    for fraction, color, line_width in ((1.0, accent, 4), (0.78, accent2, 2),
                                         (0.55, faint, 2), (0.30, accent2, 2)):
        r = radius * fraction
        canvas.create_oval(cx-r, cy-r, cx+r, cy+r, outline=color,
                           width=line_width, tags="radar")
    canvas.create_line(cx-radius, cy, cx+radius, cy, fill=accent2, width=1, tags="radar")
    canvas.create_line(cx, cy-radius, cx, cy+radius, fill=accent2, width=1, tags="radar")

    # Rotating sweep line plus a short trailing arc to make motion obvious.
    angle = (phase * 1.5) % (2 * math.pi)
    sx, sy = cx + math.cos(angle) * radius, cy + math.sin(angle) * radius
    canvas.create_arc(cx-radius, cy-radius, cx+radius, cy+radius,
                      start=-math.degrees(angle), extent=38, style="arc",
                      outline=accent, width=5, tags="radar")
    canvas.create_line(cx, cy, sx, sy, fill=accent, width=5, tags="radar")

    # Fixed radar targets pulse as the sweep rotates.
    blips = [(0.18, -0.24, 0.2), (-0.48, 0.12, 1.1), (0.55, 0.38, 2.0),
             (-0.12, -0.62, 2.7), (0.72, -0.08, 3.5), (-0.63, -0.42, 4.2)]
    for bx, by, offset in blips:
        x, y = cx + bx * radius, cy + by * radius
        pulse = (math.sin(phase * 3.2 + offset) + 1) / 2
        r = 3 + pulse * 4
        canvas.create_oval(x-r-4, y-r-4, x+r+4, y+r+4,
                           outline=accent2, width=1, tags="radar")
        canvas.create_oval(x-r, y-r, x+r, y+r,
                           fill=accent if pulse > 0.35 else accent2,
                           outline=accent, tags="radar")

    canvas.create_oval(cx-6, cy-6, cx+6, cy+6, fill=accent, outline=accent, tags="radar")
    canvas.create_text(cx, cy-radius-23, text="SHIVA // RADAR CORE",
                       fill=accent, font=("Consolas", 14, "bold"), tags="radar")
    canvas.create_text(cx, cy+radius+23, text="SCANNING • SIGNALS ACTIVE",
                       fill=accent2, font=("Consolas", 10, "bold"), tags="radar")
    canvas.tag_raise("radar")
    root.after(40, draw_radar)


# =========================================================
# CHAT
# =========================================================

chat_frame = tk.Frame(
    center,
    bg=PANEL,
    height=290,
    highlightbackground=GREEN_DARK,
    highlightthickness=1
)

chat_frame.pack(
    fill="x",
    pady=(10, 0)
)

chat_frame.pack_propagate(False)


tk.Label(
    chat_frame,
    text="// SHIVA AI TERMINAL",
    font=("Consolas", 12, "bold"),
    fg=GREEN,
    bg=PANEL
).pack(
    anchor="w",
    padx=14,
    pady=(8, 3)
)


chat_text = tk.Text(
    chat_frame,
    bg=BLACK,
    fg=WHITE_GREEN,
    insertbackground=GREEN,
    font=("Consolas", 10),
    wrap="word",
    relief="flat",
    padx=12,
    pady=7
)

chat_text.pack(
    fill="both",
    expand=True,
    padx=8,
    pady=(0, 8)
)

chat_text.configure(
    state="disabled"
)


def add_chat(
    sender,
    message
):
    # Tkinter widgets must only be touched from the main UI thread.
    if threading.current_thread() is not threading.main_thread():
        root.after(0, add_chat, sender, message)
        return

    chat_text.configure(
        state="normal"
    )

    if sender == "YOU":
        color = GREEN
    else:
        color = WHITE_GREEN

    chat_text.tag_config(
        sender,
        foreground=color,
        font=("Consolas", 10, "bold")
    )

    chat_text.insert(
        "end",
        f"{sender} > ",
        sender
    )

    chat_text.insert(
        "end",
        message + "\n\n"
    )

    chat_text.see(
        "end"
    )

    chat_text.configure(
        state="disabled"
    )


# =========================================================
# STREAMING CHAT HELPERS
# SHIVA displays the answer as Ollama generates it.
# Tkinter widgets are only changed on the main UI thread.
# =========================================================

stream_response_open = False


def start_stream_response():
    global stream_response_open

    chat_text.configure(state="normal")
    chat_text.tag_config(
        "SHIVA",
        foreground=WHITE_GREEN,
        font=("Consolas", 10, "bold")
    )
    chat_text.insert("end", "SHIVA > ", "SHIVA")
    chat_text.see("end")
    chat_text.configure(state="disabled")
    stream_response_open = True


def append_stream_response(piece):
    chat_text.configure(state="normal")
    chat_text.insert("end", piece)
    chat_text.see("end")
    chat_text.configure(state="disabled")


def finish_stream_response():
    global stream_response_open

    if stream_response_open:
        chat_text.configure(state="normal")
        chat_text.insert("end", "\\n\\n")
        chat_text.see("end")
        chat_text.configure(state="disabled")
        stream_response_open = False


# =========================================================
# AI
# =========================================================

def ask_ai(prompt, on_chunk=None):

    try:

        memory_context = ""

        if memory:
            memory_context = (
                "\\nSaved memories:\\n"
                + "\\n".join(
                    "- " + item
                    for item in memory[-10:]
                )
            )

        system_prompt = """
You are SHIVA, a personal AI assistant.

Be helpful, intelligent, concise and friendly.
Answer naturally and clearly. Use saved memories when useful.
LANGUAGE RULE: Respond in English only. Use clear, natural English even if the user writes in another language.
"""

        # stream=True lets SHIVA show each generated piece immediately.
        response_stream = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt + memory_context
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            stream=True,
            keep_alive=-1,
            options={
                "num_predict": 500,
                "temperature": 0.5
            }
        )

        full_answer = []

        for chunk in response_stream:
            piece = chunk.get("message", {}).get("content", "")

            if piece:
                full_answer.append(piece)

                if on_chunk is not None:
                    # Invoke the stream callback immediately on the Ollama worker.
                    # The callback itself schedules UI updates with root.after(),
                    # while speech buffering/queueing happens synchronously.
                    # Scheduling the whole callback with root.after() caused a race:
                    # ask_ai() could enqueue the end marker before callbacks ran,
                    # so the TTS worker stopped before receiving the full answer.
                    on_chunk(piece)

        return "".join(full_answer)

    except Exception as e:
        error_message = "Ollama error: " + str(e)

        if on_chunk is not None:
            on_chunk(error_message)

        return error_message


def process_command(command):

    global memory

    text = command.strip()

    if not text:
        return

    add_chat(
        "YOU",
        text
    )

    lower = text.lower()

    # Remember

    if lower.startswith(
        "remember that "
    ):

        item = text[14:].strip()

        if item:

            memory.append(
                item
            )

            save_memory(
                memory
            )

            answer = (
                "Memory saved."
            )

            add_chat(
                "SHIVA",
                answer
            )

            speak(
                answer
            )

            return

    if lower.startswith(
        "remember "
    ):

        item = text[9:].strip()

        if item:

            memory.append(
                item
            )

            save_memory(
                memory
            )

            answer = (
                "I will remember that."
            )

            add_chat(
                "SHIVA",
                answer
            )

            speak(
                answer
            )

            return

    # Show memory

    if lower in [
        "what do you remember",
        "what do you remember?",
        "show my memories",
        "show memory"
    ]:

        if memory:

            answer = (
                "Saved memories:\n"
                + "\n".join(
                    "• " + item
                    for item in memory
                )
            )

        else:

            answer = (
                "No memories are saved."
            )

        add_chat(
            "SHIVA",
            answer
        )

        return

    # Clear memory

    if lower in [
        "forget everything",
        "clear memory",
        "clear all memories"
    ]:

        memory.clear()

        save_memory(
            memory
        )

        answer = (
            "All memories cleared."
        )

        add_chat(
            "SHIVA",
            answer
        )

        speak(
            answer
        )

        return

    # Forget specific

    if lower.startswith(
        "forget "
    ):

        target = (
            text[7:]
            .strip()
            .lower()
        )

        old_count = len(
            memory
        )

        memory = [
            item
            for item in memory
            if target not in item.lower()
        ]

        save_memory(
            memory
        )

        if len(memory) < old_count:

            answer = (
                "That memory has been forgotten."
            )

        else:

            answer = (
                "I could not find that memory."
            )

        add_chat(
            "SHIVA",
            answer
        )

        speak(
            answer
        )

        return

    # AI — show text as it arrives and speak each sentence while the
    # remaining answer is still being generated.
    root.after(
        0,
        lambda: system_state.config(
            text="● THINKING + SPEAKING",
            fg=LIGHTNING_YELLOW
        )
    )
    root.after(0, start_stream_response)

    speech_queue = queue.Queue()
    speech_done.clear()

    def streamed_speech_worker():
        """Keep one TTS engine and its event loop alive across all chunks."""
        engine = None
        loop_started = False
        finished_queuing = False
        try:
            # Reusing one engine/event loop avoids the long silence caused by
            # repeatedly initializing SAPI5 and calling runAndWait per chunk.
            try:
                engine = pyttsx3.init(driverName="sapi5") if os.name == "nt" else pyttsx3.init()
            except Exception:
                engine = pyttsx3.init()
            engine.setProperty("rate", 195)
            engine.setProperty("volume", 1.0)
            engine.startLoop(False)
            loop_started = True

            while True:
                # Pump the speech engine continuously while new text arrives.
                engine.iterate()
                if not finished_queuing:
                    try:
                        phrase = speech_queue.get(timeout=0.01)
                    except queue.Empty:
                        phrase = "__SHIVA_NO_CHUNK__"

                    if phrase is None:
                        finished_queuing = True
                        speech_queue.task_done()
                    elif phrase != "__SHIVA_NO_CHUNK__":
                        try:
                            phrase = str(phrase).strip()
                            if phrase:
                                engine.say(phrase)
                        finally:
                            speech_queue.task_done()

                # Do not exit until all text has been queued AND the engine
                # reports that the final words have finished playing.
                if finished_queuing and speech_queue.empty() and not engine.isBusy():
                    break
        except Exception as e:
            print("Streaming TTS worker error:", repr(e))
            try:
                root.after(0, add_chat, "SHIVA", "Voice playback error: " + str(e))
            except Exception:
                pass
        finally:
            try:
                if engine is not None:
                    if loop_started:
                        engine.endLoop()
                    engine.stop()
            except Exception:
                pass
            # This is set only after the final queued speech has completed.
            speech_done.set()

    tts_thread = threading.Thread(target=streamed_speech_worker, daemon=True)
    tts_thread.start()
    pending_speech = ""
    # Larger chunks reduce tiny pauses between speech segments while still
    # starting playback before Ollama has generated the complete answer.
    SPEECH_CHUNK_WORDS = 16
    SPEECH_CHUNK_CHARS = 115

    def handle_stream_chunk(piece):
        nonlocal pending_speech
        root.after(0, append_stream_response, piece)
        pending_speech += piece

        while True:
            word_count = len(pending_speech.split())
            if word_count < SPEECH_CHUNK_WORDS and len(pending_speech) < SPEECH_CHUNK_CHARS:
                break

            limit = min(len(pending_speech), SPEECH_CHUNK_CHARS)
            split_at = pending_speech.rfind(" ", 0, limit + 1)
            if split_at <= 0:
                if len(pending_speech) < SPEECH_CHUNK_CHARS * 2:
                    break
                split_at = pending_speech.find(" ", limit)
                if split_at == -1:
                    break

            phrase = pending_speech[:split_at].strip()
            if phrase:
                speech_queue.put(phrase)
            pending_speech = pending_speech[split_at:].lstrip()

    answer = ask_ai(text, on_chunk=handle_stream_chunk)

    # Always flush the tail, including short answers and the last few words.
    if pending_speech.strip():
        speech_queue.put(pending_speech.strip())
    speech_queue.put(None)
    speech_queue.join()

    root.after(0, finish_stream_response)
    root.after(
        0,
        lambda: system_state.config(
            text="● READY",
            fg=GREEN
        )
    )

    # Wait for speech playback to finish. Keep this guarded so a thread-state
    # issue cannot crash the voice-chat worker at this point.
    try:
        if tts_thread is not threading.current_thread() and tts_thread.is_alive():
            tts_thread.join(timeout=90)
    except (RuntimeError, AttributeError) as exc:
        print("TTS thread wait warning:", repr(exc))


# =========================================================
# INPUT
# =========================================================

input_frame = tk.Frame(
    center,
    bg=BLACK
)

input_frame.pack(
    fill="x",
    pady=(9, 0)
)


entry = tk.Entry(
    input_frame,
    bg=PANEL2,
    fg=WHITE_GREEN,
    insertbackground=GREEN,
    font=("Consolas", 12),
    relief="flat"
)

entry.pack(
    side="left",
    fill="x",
    expand=True,
    ipady=11,
    padx=(0, 7)
)


def send_message(
    event=None
):

    text = entry.get().strip()

    if not text:
        return

    entry.delete(
        0,
        "end"
    )

    threading.Thread(
        target=process_command,
        args=(text,),
        daemon=True
    ).start()


entry.bind(
    "<Return>",
    send_message
)


# =========================================================
# VOICE + CONTINUOUS VOICE CHAT
# =========================================================

voice_chat_running = False
voice_chat_thread = None
voice_chat_button_widget = None


def set_voice_chat_ui(active):
    """Update Tkinter controls safely from the main UI thread."""
    if active:
        voice_chat_button_widget.config(
            text="STOP CHAT",
            fg=RED
        )
        system_state.config(text="● VOICE CHAT ON", fg=SWORD_BLUE2)
    else:
        voice_chat_button_widget.config(
            text="VOICE CHAT",
            fg=LIGHTNING_YELLOW
        )
        system_state.config(text="● READY", fg=GREEN)


def continuous_voice_chat():
    """Listen, answer aloud, then listen again until toggled off."""
    global voice_chat_running
    recognizer = sr.Recognizer()

    try:
        with sr.Microphone() as source:
            root.after(0, lambda: system_state.config(
                text="● CALIBRATING MIC", fg=SWORD_BLUE2
            ))
            recognizer.adjust_for_ambient_noise(source, duration=0.5)

            while voice_chat_running:
                try:
                    root.after(0, lambda: system_state.config(
                        text="● LISTENING — SPEAK NOW", fg=SWORD_BLUE2
                    ))
                    audio = recognizer.listen(
                        source,
                        timeout=1,
                        phrase_time_limit=8
                    )
                except sr.WaitTimeoutError:
                    continue

                if not voice_chat_running:
                    break

                try:
                    recognized_text = recognizer.recognize_google(audio).strip()
                except sr.UnknownValueError:
                    root.after(0, lambda: add_chat(
                        "SHIVA", "I couldn't understand that. Please try again."
                    ))
                    continue
                except sr.RequestError as e:
                    root.after(0, lambda err=str(e): add_chat(
                        "SHIVA", "Speech recognition service error: " + err
                    ))
                    continue

                if recognized_text and voice_chat_running:
                    # process_command generates and speaks SHIVA's reply.
                    process_command(recognized_text)
                    # Do not reopen the microphone while SHIVA is speaking.
                    while voice_chat_running and not speech_done.wait(timeout=0.1):
                        pass

    except Exception as e:
        root.after(0, lambda err=str(e): add_chat(
            "SHIVA", "Voice chat microphone error: " + err
        ))
    finally:
        voice_chat_running = False
        root.after(0, lambda: set_voice_chat_ui(False))


def toggle_voice_chat():
    """Start continuous voice chat, or stop it when pressed again."""
    global voice_chat_running, voice_chat_thread

    if voice_chat_running:
        voice_chat_running = False
        root.after(0, lambda: set_voice_chat_ui(False))
        return

    voice_chat_running = True
    set_voice_chat_ui(True)
    voice_chat_thread = threading.Thread(
        target=continuous_voice_chat,
        daemon=True
    )
    voice_chat_thread.start()


def listen_to_voice():

    recognizer = sr.Recognizer()

    try:

        system_state.config(
            text="● LISTENING",
            fg=SWORD_BLUE2
        )

        with sr.Microphone() as source:

            recognizer.adjust_for_ambient_noise(
                source,
                duration=0.4
            )

            audio = recognizer.listen(
                source,
                timeout=5,
                phrase_time_limit=10
            )

        text = recognizer.recognize_google(
            audio
        )

        entry.delete(
            0,
            "end"
        )

        entry.insert(
            0,
            text
        )

        send_message()

    except sr.WaitTimeoutError:

        add_chat(
            "SHIVA",
            "I didn't hear anything."
        )

    except sr.UnknownValueError:

        add_chat(
            "SHIVA",
            "I couldn't understand that."
        )

    except Exception as e:

        add_chat(
            "SHIVA",
            "Microphone error: " + str(e)
        )

    finally:

        system_state.config(
            text="● READY",
            fg=GREEN
        )


def voice_button():

    threading.Thread(
        target=listen_to_voice,
        daemon=True
    ).start()


# =========================================================
# BUTTON
# =========================================================

def make_button(
    text,
    command,
    foreground=GREEN
):

    return tk.Button(
        input_frame,
        text=text,
        command=command,
        bg=PANEL2,
        fg=foreground,
        activebackground=GREEN_DARK,
        activeforeground=WHITE_GREEN,
        font=("Consolas", 10, "bold"),
        relief="flat",
        padx=15,
        pady=8
    )


make_button(
    "EXECUTE",
    send_message
).pack(
    side="left",
    padx=3
)


make_button(
    "VOICE",
    voice_button,
    SWORD_BLUE2
).pack(
    side="left",
    padx=3
)


voice_chat_button_widget = make_button(
    "VOICE CHAT",
    toggle_voice_chat,
    LIGHTNING_YELLOW
)
voice_chat_button_widget.pack(
    side="left",
    padx=3
)

# =========================================================
# MEMORY WINDOW
# =========================================================

def show_memory():

    win = tk.Toplevel(
        root
    )

    win.title(
        "SHIVA // MEMORY"
    )

    win.geometry(
        "550x450"
    )

    win.configure(
        bg=BLACK
    )

    tk.Label(
        win,
        text="// MEMORY DATABASE",
        font=("Consolas", 14, "bold"),
        fg=GREEN,
        bg=BLACK
    ).pack(
        pady=15
    )

    box = tk.Text(
        win,
        bg=PANEL,
        fg=WHITE_GREEN,
        font=("Consolas", 11),
        relief="flat",
        wrap="word"
    )

    box.pack(
        fill="both",
        expand=True,
        padx=20,
        pady=10
    )

    if memory:

        for i, item in enumerate(
            memory,
            1
        ):

            box.insert(
                "end",
                f"{i}. {item}\n\n"
            )

    else:

        box.insert(
            "end",
            "No saved memories."
        )

    box.configure(
        state="disabled"
    )


make_button(
    "MEMORY",
    show_memory,
    LIGHTNING_YELLOW
).pack(
    side="left",
    padx=3
)


# =========================================================
# CLEAR CHAT
# =========================================================

def clear_chat():

    chat_text.configure(
        state="normal"
    )

    chat_text.delete(
        "1.0",
        "end"
    )

    chat_text.configure(
        state="disabled"
    )

    add_chat(
        "SHIVA",
        "Terminal cleared. SHIVA is ready."
    )


make_button(
    "CLEAR",
    clear_chat,
    RED
).pack(
    side="left",
    padx=3
)


# =========================================================
# WAKE WORD
# =========================================================

def wake_listener():

    global wake_running

    if wake_model is None:
        return

    wake_running = True

    try:

        with sd.RawInputStream(
            samplerate=16000,
            blocksize=1280,
            dtype="int16",
            channels=1
        ) as stream:

            while wake_running:

                data, overflowed = stream.read(
                    1280
                )

                if overflowed:
                    continue

                try:

                    predictions = wake_model.predict(
                        data.tobytes()
                    )

                    score = predictions.get(
                        WAKE_WORD,
                        0
                    )

                    if score >= WAKE_THRESHOLD:

                        root.after(
                            0,
                            voice_button
                        )

                        threading.Event().wait(
                            2
                        )

                except Exception:
                    pass

    except Exception as e:

        print(
            "Wake listener:",
            e
        )


def start_wake_listener():

    if wake_model is None:
        return

    threading.Thread(
        target=wake_listener,
        daemon=True
    ).start()


# =========================================================
# STARTUP CHAT
# =========================================================

add_chat(
    "SHIVA",
    "Hacker interface initialized."
)

add_chat(
    "SHIVA",
    "AI CORE: LLAMA 3.2 ONLINE"
)

add_chat(
    "SHIVA",
    "MEMORY DATABASE: ONLINE"
)

add_chat(
    "SHIVA",
    "VOICE SYSTEM: READY"
)

add_chat(
    "SHIVA",
    "WAKE WORD: HEY JARVIS"
)

add_chat(
    "SHIVA",
    "RADAR CORE: ONLINE — SCANNING."
)


# =========================================================
# CLOSE
# =========================================================

def close_app():

    global wake_running, voice_chat_running, _game_server

    wake_running = False
    voice_chat_running = False
    try:
        if _game_server is not None:
            _game_server.shutdown()
            _game_server.server_close()
    except Exception:
        pass

    try:
        tts.stop()
    except Exception:
        pass

    root.destroy()


root.protocol(
    "WM_DELETE_WINDOW",
    close_app
)


# =========================================================
# START ANIMATIONS
# =========================================================

root.after(
    100,
    draw_matrix
)

root.after(
    120,
    draw_radar
)

root.after(
    500,
    animate_inventors
)


# =========================================================
# START WAKE WORD
# ========================================================

threading.Thread(
    target=initialize_wake_word,
    daemon=True
).start()


# =========================================================
# RUN
# =========================================================

root.mainloop()