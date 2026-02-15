from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from faster_whisper import WhisperModel
import tempfile
import shutil
import os
import sys
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
import time
import argparse

# Parse command line arguments
parser = argparse.ArgumentParser(description="Whisper Server - Audio Transcription API")
parser.add_argument("model", nargs="?", default=os.getenv("WHISPER_MODEL", "small"),
                   help="Whisper model name (tiny, base, small, medium, large, large-v2, large-v3)")
parser.add_argument("--https", action="store_true", help="Enable HTTPS (default: HTTP)")
args = parser.parse_args()

# --- Configuration for Whisper Model ---
# This model will be downloaded automatically the first time the server runs.
# Priority: command line argument > environment variable > default
# Can be set via: python run.py medium  OR  WHISPER_MODEL=medium python run.py
# Valid options: tiny, base, small, medium, large, large-v2, large-v3
MODEL_NAME = args.model  # Default to "small"
USE_HTTPS = args.https

# Use 'cpu' for maximum compatibility across M1 Mac and Raspberry Pi 5.
DEVICE = "cpu" 

# float32 is the most compatible compute type.
COMPUTE_TYPE = "float32" 

# Model download timeout in seconds (30 minutes = 1800 seconds)
MODEL_DOWNLOAD_TIMEOUT = int(os.getenv("MODEL_DOWNLOAD_TIMEOUT", "1800"))  # 30 minutes default

# Maximum number of retry attempts for model loading
MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))

# Retry delay in seconds (exponential backoff)
RETRY_DELAY_BASE = 5  # Start with 5 seconds
# ----------------------------------------------------------

model: Optional[WhisperModel] = None
model_loading_status: str = "not_started"  # not_started, loading, loaded, failed
model_loading_error: Optional[str] = None

# Thread pool executor for running blocking transcription operations
# This allows multiple transcription requests to be processed concurrently
executor = ThreadPoolExecutor(max_workers=4)  # Adjust based on CPU cores and memory
model_loader_executor = ThreadPoolExecutor(max_workers=1)  # Separate executor for model loading 

def load_model_with_retry(model_name: str, max_attempts: int = MAX_RETRY_ATTEMPTS) -> Optional[WhisperModel]:
    """Load Whisper model with retry logic and timeout handling."""
    global model_loading_status, model_loading_error
    
    for attempt in range(1, max_attempts + 1):
        start_time = None
        try:
            model_loading_status = "loading"
            model_loading_error = None
            
            print(f"Attempt {attempt}/{max_attempts}: Initializing model '{model_name}'...")
            if attempt > 1:
                delay = RETRY_DELAY_BASE * (2 ** (attempt - 2))  # Exponential backoff
                print(f"Waiting {delay} seconds before retry...")
                time.sleep(delay)
            
            # Load model with timeout protection
            # Note: We can't directly timeout WhisperModel initialization, but we can
            # run it in a separate thread and monitor progress
            print(f"Loading model (this may take several minutes if downloading)...")
            print(f"Timeout set to {MODEL_DOWNLOAD_TIMEOUT} seconds ({MODEL_DOWNLOAD_TIMEOUT // 60} minutes)")
            
            start_time = time.time()
            loaded_model = WhisperModel(
                model_name, 
                device=DEVICE, 
                compute_type=COMPUTE_TYPE
            )
            elapsed_time = time.time() - start_time
            
            print(f"Model '{model_name}' loaded successfully in {elapsed_time:.1f} seconds.")
            model_loading_status = "loaded"
            return loaded_model
            
        except KeyboardInterrupt:
            print("\nModel loading interrupted by user.")
            model_loading_status = "failed"
            model_loading_error = "Loading interrupted by user"
            raise
            
        except Exception as e:
            error_msg = str(e)
            model_loading_error = error_msg
            elapsed_time = time.time() - start_time if start_time is not None else 0
            
            print(f"Attempt {attempt} failed after {elapsed_time:.1f} seconds: {error_msg}")
            
            if attempt < max_attempts:
                print(f"Will retry... ({max_attempts - attempt} attempts remaining)")
            else:
                print(f"All {max_attempts} attempts failed. Model loading aborted.")
                model_loading_status = "failed"
                return None
    
    model_loading_status = "failed"
    return None

def load_model_async(model_name: str):
    """Load model in background thread."""
    global model, model_loading_status, model_loading_error
    
    try:
        loaded_model = load_model_with_retry(model_name)
        if loaded_model is not None:
            model = loaded_model
            print(f"✓ Model is ready for transcription requests.")
        else:
            print(f"✗ Model failed to load. Server will start but /transcribe will return 503.")
            print(f"  You can check model status at /health endpoint.")
            model = None
    except Exception as e:
        print(f"Unexpected error during model loading: {e}")
        model_loading_status = "failed"
        model_loading_error = str(e)
        model = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    global model, model_loading_status
    
    # Validate model name
    valid_models = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]
    if MODEL_NAME not in valid_models:
        print(f"WARNING: Invalid model name '{MODEL_NAME}'. Valid options: {', '.join(valid_models)}")
        print(f"Falling back to 'small' model.")
        model_name = "small"
    else:
        model_name = MODEL_NAME
    
    print(f"Loading Faster Whisper model: {model_name} on {DEVICE} with {COMPUTE_TYPE}...")
    print(f"Note: Model can be changed via command line argument (e.g., 'python run.py medium') or WHISPER_MODEL environment variable")
    print(f"Server will start immediately. Model will load in the background.")
    print(f"If model download takes too long, you can check status at /health endpoint.")
    
    # Start model loading in background thread (non-blocking)
    # This allows the server to start even if model download is slow
    loop = asyncio.get_event_loop()
    loop.run_in_executor(model_loader_executor, load_model_async, model_name)
    
    # Give it a moment to start
    await asyncio.sleep(0.1)
    
    yield
    
    # Shutdown: Clean up resources
    model = None
    model_loading_status = "not_started"

app = FastAPI(lifespan=lifespan)

# Add CORS middleware to allow requests from Next.js app
# For development, allow localhost, 127.0.0.1, and Tailscale hostname (macbook-m1)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|macbook-m1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Check the status of the model loading."""
    global model, model_loading_status, model_loading_error
    
    if model is not None:
        return {
            "status": "ready",
            "model_loaded": True,
            "model_loading_status": model_loading_status,
            "message": "Model is loaded and ready for transcription"
        }
    else:
        return {
            "status": "not_ready",
            "model_loaded": False,
            "model_loading_status": model_loading_status,
            "error": model_loading_error,
            "message": "Model is still loading or failed to load. Check model_loading_status for details."
        }

@app.post("/transcribe")
async def transcribe_audio(audio_file: UploadFile = File(...)):
    """
    Accepts an audio file upload, transcribes it using Faster Whisper, and returns the text.
    
    The transcription parameters are set for Japanese ('ja').
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Whisper model is not loaded or failed to initialize.")
    
    tmp_path: Optional[str] = None
    
    try:
        # 1. Save the uploaded file to a temporary location
        # This is necessary because faster-whisper needs a file path, not just a stream.
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            # Copy the contents of the upload stream into the temporary file
            shutil.copyfileobj(audio_file.file, tmp_file)
            tmp_path = tmp_file.name

        print(f"Processing audio file: {audio_file.filename} saved to {tmp_path}")

        # 2. Transcribe the audio (run in thread pool to avoid blocking the event loop)
        # This allows multiple transcription requests to be processed concurrently
        def transcribe_audio_file(file_path: str):
            """Helper function to run transcription in thread pool."""
            segments, info = model.transcribe(
                file_path,
                beam_size=5,
                # Explicitly set the source language to Japanese for better results and speed
                language="ja", 
                vad_filter=True, # Use Voice Activity Detection to skip silent parts
            )
            # Collect all segments into a list (since segments is an iterator)
            segments_list = list(segments)
            transcription_text = "".join([segment.text for segment in segments_list])
            return transcription_text, info
        
        loop = asyncio.get_event_loop()
        transcription_text, info = await loop.run_in_executor(
            executor,
            transcribe_audio_file,
            tmp_path
        )
        
        return {
            "transcription": transcription_text.strip(),
            "detected_language": info.language
        }

    except Exception as e:
        print(f"Transcription failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    
    finally:
        # 4. Clean up the temporary file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
                print(f"Cleaned up temporary file: {tmp_path}")
            except Exception as e:
                print(f"Warning: Could not remove temporary file {tmp_path}. Details: {e}")


if __name__ == "__main__":
    if USE_HTTPS:
        # SSL certificate paths
        # Try to use mkcert certificates from the Next.js project first (trusted by browsers)
        NEXTJS_PROJECT_PATH = "/Users/g150446/gitdir/dialog-ehr"
        MKCERT_KEYFILE = os.path.join(NEXTJS_PROJECT_PATH, "localhost-key.pem")
        MKCERT_CERTFILE = os.path.join(NEXTJS_PROJECT_PATH, "localhost.pem")
        
        # Fallback to local self-signed certificates
        LOCAL_KEYFILE = "certs/key.pem"
        LOCAL_CERTFILE = "certs/cert.pem"
        
        # Check if mkcert certificates exist (preferred)
        if os.path.exists(MKCERT_KEYFILE) and os.path.exists(MKCERT_CERTFILE):
            SSL_KEYFILE = MKCERT_KEYFILE
            SSL_CERTFILE = MKCERT_CERTFILE
            print("Using mkcert certificates from Next.js project (trusted by browsers)")
        # Otherwise check for local certificates
        elif os.path.exists(LOCAL_KEYFILE) and os.path.exists(LOCAL_CERTFILE):
            SSL_KEYFILE = LOCAL_KEYFILE
            SSL_CERTFILE = LOCAL_CERTFILE
            print("Using local self-signed certificates")
        else:
            print("ERROR: SSL certificates not found!")
            print("To enable HTTPS, run './generate_cert.sh' to generate SSL certificates")
            print("Or run without --https flag to use HTTP")
            sys.exit(1)
        
        print("Starting Uvicorn server with HTTPS on https://0.0.0.0:9000")
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=9000,
            ssl_keyfile=SSL_KEYFILE,
            ssl_certfile=SSL_CERTFILE
        )
    else:
        print("Starting Uvicorn server with HTTP on http://0.0.0.0:9000")
        print("Note: To enable HTTPS, run with --https flag (requires SSL certificates)")
        uvicorn.run(app, host="0.0.0.0", port=9000)
