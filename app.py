import os
import shutil
import tempfile
import asyncio
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from faster_whisper import WhisperModel

app = FastAPI(title="Transcription App")

# Mount the static directory for CSS, JS, and Images
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global variables to cache the current loaded model
current_model = None
current_model_name = None
model_lock = asyncio.Lock()

async def get_or_load_model(model_size: str):
    global current_model, current_model_name
    async with model_lock:
        if current_model_name != model_size:
            print(f"Switching model: Unloading '{current_model_name}' and loading '{model_size}'...")
            current_model = None  # Free memory
            # Load the new model
            current_model = WhisperModel(model_size, device="cpu", compute_type="int8")
            current_model_name = model_size
            print("Model loaded successfully.")
        return current_model

@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = Form("pl"),
    model_size: str = Form("medium")
):
    """
    Endpoint to transcribe an uploaded audio file using a specific model.
    """
    # Create a temporary file to store the uploaded audio
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_audio:
        shutil.copyfileobj(file.file, temp_audio)
        temp_audio_path = temp_audio.name

    try:
        print(f"Processing file: {file.filename} in language: {language} with model: {model_size}")
        
        # Get the appropriate model (loading it if necessary)
        model = await get_or_load_model(model_size)

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

