import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    redirect,
    render_template_string,
    request,
    send_from_directory,
    session,
    url_for,
)
from PIL import Image, ImageOps


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
THUMBS_DIR = DATA_DIR / "thumbs"
META_PATH = DATA_DIR / "photos.json"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    if not META_PATH.exists():
        META_PATH.write_text(json.dumps({"photos": []}, indent=2), encoding="utf-8")


def read_meta() -> dict:
    try:
        raw = META_PATH.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict) or not isinstance(parsed.get("photos"), list):
            return {"photos": []}
        return parsed
    except Exception:
        return {"photos": []}


def write_meta(meta: dict) -> None:
    META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug_safe_filename(original: str) -> str:
    original = (original or "photo").strip()
    stem = Path(original).stem.lower()
    stem = "".join(ch if ch.isalnum() else "-" for ch in stem)
    while "--" in stem:
        stem = stem.replace("--", "-")
    stem = stem.strip("-")[:60] or "photo"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    rand = secrets.token_hex(3)
    return f"{stamp}-{rand}-{stem}.jpg"


ensure_dirs()

app = Flask(__name__, static_folder="public", static_url_path="/static")

app.secret_key = os.environ.get("SESSION_SECRET") or secrets.token_hex(32)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-me")
PORT = int(os.environ.get("PORT", "3000"))
DEFAULT_SECTION = os.environ.get("DEFAULT_SECTION", "Unsorted")

SECTIONS = [
    "Family",
    "Chicago",
    "Indian Crew",
    "Jew Crew",
    "Everyone Else",
]
SECTION_CANON = {s.lower(): s for s in SECTIONS}


def is_admin() -> bool:
    return bool(session.get("is_admin"))


def require_admin():
    if not is_admin():
        return redirect(url_for("login"))
    return None


def escape_html(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


BASE_TEMPLATE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>{{ title }}</title>
    <link rel="stylesheet" href="/static/styles.css" />
  </head>
  <body>
    <header class="topbar">
      <div class="brand">
        <div class="brand__dot" aria-hidden="true"></div>
        <div>
          <div class="brand__title">Happy Birthday Mom! We love you!</div>
          <div class="brand__subtitle">All your favorite people, in one place</div>
        </div>
      </div>
      <nav class="nav">
        <a class="nav__link" href="/">Gallery</a>
        {% if admin %}
          <a class="nav__link" href="/upload">Upload</a>
          <form class="nav__form" action="/logout" method="post">
            <button class="nav__link nav__button" type="submit">Log out</button>
          </form>
        {% else %}
          <a class="nav__link" href="/login">Admin</a>
        {% endif %}
      </nav>
    </header>
    <main class="container">
      {{ body|safe }}
    </main>
    <script src="/static/app.js" defer></script>
  </body>
</html>
"""


@app.get("/uploads/<path:filename>")
def uploads(filename: str):
    return send_from_directory(UPLOADS_DIR, filename, conditional=True)


@app.get("/thumbs/<path:filename>")
def thumbs(filename: str):
    return send_from_directory(THUMBS_DIR, filename, conditional=True)


@app.get("/")
def index():
    meta = read_meta()
    photos = list(meta.get("photos", []))
    photos.sort(key=lambda p: (p.get("takenAt") or p.get("createdAt") or ""), reverse=True)

    # Back-compat: older photos may not have a section.
    counts = {s: 0 for s in SECTIONS}
    by_section: dict[str, list[dict]] = {s: [] for s in SECTIONS}
    for p in photos:
        if not p.get("section"):
            p["section"] = "Everyone Else"
        sec = normalize_section(p.get("section"))
        p["section"] = sec
        if sec not in by_section:
            sec = "Everyone Else"
            p["section"] = sec
        by_section.setdefault(sec, []).append(p)
        if sec in counts:
            counts[sec] += 1

    # Road markers along the “trip”.
    markers = []
    for s in SECTIONS:
        markers.append(
            """
      <button class="roadtrip__marker" data-section="%s">
        <span class="roadtrip__marker-dot" data-s="%s"></span>
        <span class="roadtrip__marker-label">%s</span>
        <span class="roadtrip__marker-count">%d</span>
      </button>
            """
            % (
                escape_html(s),
                escape_html(s),
                escape_html(s),
                int(counts.get(s, 0)),
            )
        )
    markers_html = "\n".join(markers)

    # A little tagline for each stop on the road.
    taglines = {
        "Family": "Home base. Everyone who loves you most.",
        "Chicago": "Windy City memories and skyline nights.",
        "Indian Crew": "The desi squad and all the chaos.",
        "Jew Crew": "Shabbats, simchas, and inside jokes.",
        "Everyone Else": "Friends, surprises, and the in‑between.",
    }

    stops = []
    for s in SECTIONS:
        section_photos = by_section.get(s, [])
        cards = []
        for p in section_photos:
            cards.append(
                f"""
        <button class="card" data-full="{escape_html(p.get("url",""))}" data-caption="{escape_html(p.get("caption",""))}">
          <img class="card__img" src="{escape_html(p.get("thumbUrl",""))}" alt="{escape_html(p.get("caption") or "Photo")}" loading="lazy" />
          <div class="card__meta">
            <div class="card__caption">{escape_html(p.get("caption") or " ")}</div>
            <div class="card__date">{escape_html(format_date(p.get("takenAt") or p.get("createdAt") or ""))}</div>
          </div>
        </button>
                """.strip()
            )
        cards_html = "\n".join(cards) if cards else '<div class="empty">No photos in this stop yet.</div>'
        stops.append(
            f"""
    <section class="stop" data-section="{escape_html(s)}">
      <header class="stop__header">
        <h2 class="stop__title">{escape_html(s)}</h2>
        <p class="stop__tagline">{escape_html(taglines.get(s, ""))}</p>
      </header>
      <div class="grid stop__grid" aria-label="{escape_html(s)} photos">
        {cards_html}
      </div>
    </section>
            """.rstrip()
        )
    stops_html = "\n".join(stops)

    body = f"""
    <section class="hero">
      <div class="hero__copy">
        <h1>Happy Birthday Mom! We love you!</h1>
        <p>Scroll down the road to drive past each part of your life.</p>
      </div>
    </section>
    <section class="roadtrip" aria-label="Life road trip">
      <div class="roadtrip__track" id="roadtrip">
        <div class="roadtrip__road"></div>
        <div class="roadtrip__car" id="roadtrip-car" aria-hidden="true"></div>
        <div class="roadtrip__markers">
          {markers_html}
        </div>
      </div>
    </section>
    <section class="stops" id="stops">
      {stops_html}
    </section>
    <dialog class="viewer" id="viewer">
      <form method="dialog" class="viewer__backdrop">
        <button class="viewer__close" aria-label="Close">×</button>
        <figure class="viewer__figure">
          <img class="viewer__img" alt="" />
          <figcaption class="viewer__caption"></figcaption>
        </figure>
      </form>
    </dialog>
    """

    return render_template_string(BASE_TEMPLATE, title="Happy Birthday Mom! We love you!", body=body, admin=is_admin())


@app.get("/api/photos")
def api_photos():
    meta = read_meta()
    photos = list(meta.get("photos", []))
    for p in photos:
        if not p.get("section"):
            p["section"] = "Everyone Else"
        p["section"] = normalize_section(p.get("section"))
    return {"sections": SECTIONS, "photos": photos}

def format_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y")
    except Exception:
        return ""

def normalize_section(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return DEFAULT_SECTION
    s = " ".join(s.split())
    s = (s[:40] or DEFAULT_SECTION).strip()
    lowered = s.lower()
    if lowered in SECTION_CANON:
        return SECTION_CANON[lowered]
    # Friendly aliases
    if lowered in {"jewish crew", "jewish"}:
        return "Jew Crew"
    if lowered in {"indian", "desi", "desi crew"}:
        return "Indian Crew"
    if lowered in {"chi", "chitown"}:
        return "Chicago"
    if lowered in {"fam"}:
        return "Family"
    if lowered in {"other", "others", "everyone", "everyone-else"}:
        return "Everyone Else"
    return "Everyone Else"


@app.get("/login")
def login():
    if is_admin():
        return redirect(url_for("upload_page"))
    body = """
    <section class="panel">
      <h1>Admin sign-in</h1>
      <p class="muted">This page is only for uploading photos.</p>
      <form class="form" action="/login" method="post">
        <label class="label">
          Password
          <input class="input" type="password" name="password" autocomplete="current-password" required />
        </label>
        <button class="button" type="submit">Sign in</button>
      </form>
    </section>
    """
    return render_template_string(BASE_TEMPLATE, title="Admin sign-in", body=body, admin=False)


@app.post("/login")
def login_post():
    password = (request.form.get("password") or "").strip()
    if password and secrets.compare_digest(password, ADMIN_PASSWORD):
        session["is_admin"] = True
        return redirect(url_for("upload_page"))

    body = """
    <section class="panel">
      <h1>Admin sign-in</h1>
      <p class="error">Wrong password.</p>
      <form class="form" action="/login" method="post">
        <label class="label">
          Password
          <input class="input" type="password" name="password" autocomplete="current-password" required />
        </label>
        <button class="button" type="submit">Try again</button>
      </form>
    </section>
    """
    return render_template_string(BASE_TEMPLATE, title="Admin sign-in", body=body, admin=False), 401


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.get("/upload")
def upload_page():
    maybe = require_admin()
    if maybe is not None:
        return maybe
    options = "\n".join([f'<option value="{escape_html(s)}">{escape_html(s)}</option>' for s in SECTIONS])
    body = """
    <section class="panel">
      <h1>Upload photos</h1>
      <p class="muted">Add a caption and pick one or more photos. They’ll appear at the top of the gallery.</p>
      <form class="form" action="/upload" method="post" enctype="multipart/form-data">
        <label class="label">
          Section (album)
          <select class="input" name="section" required>
            """ + options + """
          </select>
        </label>
        <label class="label">
          Caption (optional)
          <input class="input" type="text" name="caption" maxlength="140" placeholder="e.g., Summer at the lake" />
        </label>
        <label class="label">
          Photos
          <input class="input" type="file" name="photos" accept="image/*" multiple required />
        </label>
        <button class="button" type="submit">Upload</button>
      </form>
      <div class="hint">
        Tip: Large images will be resized for fast viewing.
      </div>
    </section>
    """
    return render_template_string(BASE_TEMPLATE, title="Upload photos", body=body, admin=True)


def normalize_full_image(img: Image.Image) -> Image.Image:
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    img.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
    return img


def make_thumb(img: Image.Image) -> Image.Image:
    img = img.copy()
    img = ImageOps.fit(img, (520, 520), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    return img


@app.post("/upload")
def upload_post():
    maybe = require_admin()
    if maybe is not None:
        return maybe

    section = normalize_section(request.form.get("section") or "")
    caption = (request.form.get("caption") or "").strip()[:140]
    files = request.files.getlist("photos")
    if not files:
        abort(400, "No files uploaded.")

    meta = read_meta()
    meta.setdefault("photos", [])

    for f in files[:50]:
        if not f or not getattr(f, "filename", ""):
            continue
        filename = slug_safe_filename(f.filename)
        full_path = UPLOADS_DIR / filename
        thumb_name = filename.replace(".jpg", "-thumb.jpg")
        thumb_path = THUMBS_DIR / thumb_name

        with Image.open(f.stream) as img:
            full = normalize_full_image(img)
            full.save(full_path, format="JPEG", quality=85, optimize=True, progressive=True)

            thumb = make_thumb(full)
            thumb.save(thumb_path, format="JPEG", quality=75, optimize=True, progressive=True)

        created = now_iso()
        meta["photos"].append(
            {
                "id": filename,
                "createdAt": created,
                "takenAt": created,
                "section": section,
                "caption": caption,
                "url": f"/uploads/{filename}",
                "thumbUrl": f"/thumbs/{thumb_name}",
            }
        )

    write_meta(meta)
    return redirect(url_for("index"))


@app.get("/health")
def health():
    return {"ok": True}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)

