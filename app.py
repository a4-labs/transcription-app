import os
import shutil
import tempfile
import asyncio
import uuid
from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks
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

# Global dictionary to store task statuses
# In a real production app, this would be a database or Redis
tasks = {}

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

def run_transcription_sync(model, audio_path, lang, task_id):
    """Synchronous function to run CPU-bound transcription and update progress."""
    segments, info = model.transcribe(audio_path, language=lang, beam_size=5)
    
    text = ""
    for segment in segments:
        text += segment.text + " "
        
        # Calculate and update progress
        if info.duration > 0:
            progress = min(100, int((segment.end / info.duration) * 100))
            tasks[task_id]["progress"] = progress

    return text.strip(), info

async def process_audio(task_id: str, temp_audio_path: str, language: str, model_size: str):
    try:
        tasks[task_id]["status"] = "processing"
        
        # Get the appropriate model (loading it if necessary)
        model = await get_or_load_model(model_size)

        print(f"[{task_id}] Transcribing audio with language: {language} and model: {model_size}")
        
        # Run the heavy CPU-bound generator entirely in a thread
        text_result, info = await asyncio.to_thread(
            run_transcription_sync, model, temp_audio_path, language, task_id
        )

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["text"] = text_result
        tasks[task_id]["language_detected"] = info.language
        tasks[task_id]["language_probability"] = info.language_probability
        print(f"[{task_id}] Transcription completed successfully.")

    except Exception as e:
        print(f"[{task_id}] Error during transcription: {e}")
        tasks[task_id]["status"] = "error"
        tasks[task_id]["error"] = str(e)
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

@app.post("/transcribe")
async def start_transcription(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: str = Form("pl"),
    model_size: str = Form("medium")
):
    """
    Endpoint to receive an audio file and start transcription in the background.
    """
    task_id = str(uuid.uuid4())
    
    # Create a temporary file to store the uploaded audio
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_audio:
        shutil.copyfileobj(file.file, temp_audio)
        temp_audio_path = temp_audio.name

    # Initialize task status
    tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "text": None,
        "error": None
    }

    # Add processing function to background tasks
    background_tasks.add_task(process_audio, task_id, temp_audio_path, language, model_size)

    return {"success": True, "task_id": task_id}

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    """
    Endpoint to check the status of a transcription task.
    """
    if task_id not in tasks:
        return {"success": False, "error": "Zadanie nie zostało znalezione."}
    
    task = tasks[task_id]
    return {
        "success": True,
        "status": task["status"],
        "progress": task.get("progress", 0),
        "text": task.get("text"),
        "error": task.get("error")
    }
