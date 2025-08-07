# app.py  (Python 3.11+)
from fasthtml.common import *
import base64, io, os, re, json, httpx
from pathlib import Path
from PIL import Image
import pytesseract, PyPDF2, speech_recognition as sr
from pptx import Presentation
from openai import OpenAI

# ------------- CONFIG -------------
SAVE_DIR = Path("uploads")
SAVE_DIR.mkdir(exist_ok=True)
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
    http_client=httpx.Client(transport=httpx.HTTPTransport(verify=False)),
)

# ------------- UTILS (same as desktop) -------------
def extract_pdf(path): ...
def extract_ppt(path): ...
def extract_audio(path): ...
def ocr_image(img, lang): return pytesseract.image_to_string(img, lang=lang)
def clean_text(t): return re.sub(r"\s+", " ", t).strip()

# ------------- GENERATORS (unchanged logic) -------------
def generate_summary(text, lang, max_len, prompt, role): ...
def generate_response(text, direction, lang, role): ...
def generate_analysis(original, summary, extra, lang): ...

# ------------- FASTHTML APP -------------
app, rt = fast_app(live=os.getenv("DEV"))

@rt("/")
def get():
    return Titled("📲 Mobile Summary Tool",
        Form(hx_post="/summarise", hx_target="#out", hx_swap="innerHTML",
            enctype="multipart/form-data")(
            Select(name="lang")(
                *[Option(v["name"], value=k) for k, v in SUPPORTED_LANGUAGES.items()]
            ),
            Select(name="template")(
                *[Option(v["name"], value=k) for k, v in CUSTOM_PROMPT_TEMPLATES.items()]
            ),
            Select(name="role")(
                *[Option(v, value=k) for k, v in DEEPSEEK_ROLES.items()]
            ),
            Input(name="max_len", type="range", min=50, max=2000, value=300),
            Textarea(name="text", placeholder="Paste text here…", rows=4),
            Input(name="file", type="file", accept="image/*,audio/*,.pdf,.pptx,.txt"),
            Button("Summarise", cls="primary"),
        ),
        Div(id="out"),
        # JavaScript for TTS
        Script("""
        function speak(text){
          if(!text) return;
          const ut = new SpeechSynthesisUtterance(text);
          speechSynthesis.speak(ut);
        }
        """)
    )

@rt("/summarise")
async def post(lang:int, template:int, role:int, max_len:int, text:str=None, file: UploadFile=None):
    content = text or ""
    if file:
        path = SAVE_DIR/file.filename
        await file.save(path)
        if path.suffix.lower()==".pdf":
            content += extract_pdf(path)
        elif path.suffix.lower()==".pptx":
            content += extract_ppt(path)
        elif path.suffix.lower() in (".png",".jpg",".jpeg"):
            img = Image.open(path)
            content += ocr_image(img, SUPPORTED_LANGUAGES[lang]["tesseract_lang"])
        elif path.suffix.lower() in (".wav",".mp3",".flac"):
            content += extract_audio(path)
        else:
            content += path.read_text(encoding="utf-8")

    summary = generate_summary(clean_text(content), lang, max_len, template, role)
    return Div(
        H3("Summary"),
        Pre(summary),
        Button("🔊 Speak", onclick=f"speak({json.dumps(summary)})"),
        Form(hx_post="/response", hx_target="#resp")(
            Textarea(name="direction", placeholder="Direction for reply…", rows=2),
            Hidden(name="summary", value=summary),
            Hidden(name="lang", value=lang),
            Hidden(name="role", value=role),
            Button("Generate Response")
        ),
        Div(id="resp")
    )

@rt("/response")
async def post(summary:str, direction:str, lang:int, role:int):
    resp = generate_response(summary, direction, lang, role)
    return Div(
        H4("Response"),
        Pre(resp),
        Form(hx_post="/analysis", hx_target="#analysis")(
            Textarea(name="extra", placeholder="Additional context (optional)…", rows=2),
            Hidden(name="original", value=clean_text(summary)),
            Hidden(name="summary", value=summary),
            Hidden(name="lang", value=lang),
            Button("Generate Analysis")
        ),
        Div(id="analysis")
    )

@rt("/analysis")
async def post(original:str, summary:str, extra:str, lang:int):
    ana = generate_analysis(original, summary, extra, lang)
    return Div(H4("Business Analysis"), Pre(ana))

@rt("/balance")
async def get():
    headers = {"Authorization": f"Bearer {os.getenv('DEEPSEEK_API_KEY')}"}
    r = httpx.get("https://api.deepseek.com/user/balance", headers=headers, verify=False, timeout=10)
    return Pre(r.text if r.status_code==200 else r.text)

serve()