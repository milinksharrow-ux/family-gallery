# Family Gallery

A simple website to share life photos with your family:

- **Public gallery**: anyone with the link can browse.
- **Private uploads**: upload page requires a password.
- **Auto thumbnails**: fast grid + click to view full image.

## Run locally

```bash
cd family-gallery
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open `http://localhost:3000`.

## Configure

Edit `.env`:

- `ADMIN_PASSWORD`: password required to upload
- `SESSION_SECRET`: random string for cookies

## Deploy

This is a standard Python web app (Flask). Any host that supports Python works (Render, Fly.io, Railway, a VPS, etc.).

Important: uploads are stored on disk in `data/uploads/` and `data/thumbs/`. If your host uses ephemeral disks, you’ll want to mount a persistent volume.

# family-gallery
