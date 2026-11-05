# main.py
"""
FastAPI backend for embroidery travel optimisation.
Install:  pip install fastapi uvicorn python-multipart pyembroidery
Run:      uvicorn main:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware

from embroidery_optimizer import optimize_embroidery_file  # your existing module

# ------------------------------------------------------------------
# Config  (put secrets in environment / .env, NOT in code)
# ------------------------------------------------------------------
SHARED_SECRET  = os.environ.get("EMBROIDERY_API_SECRET", "")
MAX_FILE_SIZE  = 20 * 1024 * 1024                       # 20 MB

# Yahan .emb aur baaki saare formats allowed hain
ALLOWED_EXTS   = {".dst", ".emb", ".pes", ".exp", ".jef", ".vp3",
                  ".pec", ".u01", ".xxx", ".hus", ".sew"}

app = FastAPI(title="Embroidery Optimizer API")

# CORS middleware taaki WordPress se requests smoothly chal sakein
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# Endpoint: upload → optimized file returned as binary
# ------------------------------------------------------------------
@app.post("/optimize-and-download/")
async def optimize_and_download(
    file: UploadFile = File(...),
    long_jump_threshold: float = Form(50.0),
    enable_sequencing: bool = Form(True),
    x_api_secret: str | None = Header(default=None, alias="X-API-Secret"),
):
    # 1. Auth (Agar SHARED_SECRET set nahi hai toh skip ho jayega)
    if SHARED_SECRET and x_api_secret != SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Invalid API secret")

    # 2. Validate extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {ext}")

    # 3. Read & size-check
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB)")

    # 4. Process via temp files, then return bytes
    in_path = out_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f_in:
            f_in.write(data)
            in_path = f_in.name

        out_path = in_path + ".opt" + ext
        optimize_embroidery_file(
            in_path, out_path,
            long_jump_threshold=long_jump_threshold,
            enable_sequencing=enable_sequencing,
        )

        with open(out_path, "rb") as f_out:
            optimized_bytes = f_out.read()

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Optimisation failed: {exc}")
    finally:
        for p in (in_path, out_path):
            if p and os.path.exists(p):
                try: os.unlink(p)
                except OSError: pass

    # 5. Stream back
    return Response(
        content=optimized_bytes,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition":
                f'attachment; filename="optimized{ext}"'
        },
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
