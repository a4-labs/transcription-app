import os
import shutil
import tempfile
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from faster_whisper import WhisperModel

app = FastAPI(title="Transcription App")

# Mount the static directory for CSS, JS, and Images
app.mount("/static", StaticFiles(directory="static"), name="static")

# Load the faster-whisper model
# We use "small" for better Polish accuracy, compute_type "int8" for memory efficiency
MODEL_SIZE = "small"
print(f"Loading Whisper model: {MODEL_SIZE}...")
# Note: running on CPU because Koyeb standard instances don't have GPUs
model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
print("Model loaded successfully.")

@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = Form("pl")
):
    """
    Endpoint to transcribe an uploaded audio file.
    """
    # Create a temporary file to store the uploaded audio
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_audio:
        shutil.copyfileobj(file.file, temp_audio)
        temp_audio_path = temp_audio.name

    try:
        print(f"Processing file: {file.filename} in language: {language}")
        # Transcribe the audio
        segments, info = model.transcribe(
            temp_audio_path,
            language=language,
            beam_size=5
        )

        # Gather all text segments
        text_result = ""
        for segment in segments:
            text_result += segment.text + " "
        
        return {
            "success": True,
            "text": text_result.strip(),
            "language_detected": info.language,
            "language_probability": info.language_probability
        }
    except Exception as e:
        print(f"Error during transcription: {e}")
        return {"success": False, "error": str(e)}
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
