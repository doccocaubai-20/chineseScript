import os
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from dotenv import load_dotenv

from app.transcription import FasterWhisperProvider

load_dotenv()

app = FastAPI(title="Remote Whisper Transcriber")
provider = FasterWhisperProvider()
token = os.getenv("TRANSCRIBE_TOKEN", "").strip()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/transcribe-upload")
async def transcribe_upload(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
) -> dict:
    if token and authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="Invalid transcription token")
    if file.content_type not in {"audio/wav", "audio/x-wav", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="Only WAV audio is supported")

    with tempfile.TemporaryDirectory(prefix="remote-whisper-") as directory:
        audio_path = Path(directory) / "input.wav"
        with audio_path.open("wb") as output:
            shutil.copyfileobj(file.file, output)
        chunks = provider.transcribe(str(audio_path))
    return {"audio_path": "remote-upload", "language": "zh", "chunks": chunks}
