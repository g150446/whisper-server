# Whisper Server

A FastAPI-based server for audio transcription using Faster Whisper. This server provides a REST API endpoint to transcribe audio files, with automatic language detection supporting English and Japanese.

## Features

- Fast audio transcription using Faster Whisper
- Automatic language detection (English and Japanese)
- Voice Activity Detection (VAD) to skip silent parts
- CORS enabled for frontend integration
- Automatic model downloading on first run
- HTTPS support with automatic SSL certificate detection

## Prerequisites

- Python 3.11 or 3.12 (recommended)
- ffmpeg (for audio processing)
- Homebrew (macOS)

## Installation

### 1. Install System Dependencies

```bash
brew install ffmpeg
```

### 2. Set Up Python Environment

If you're using pyenv:

```bash
pyenv install 3.11.8  # or 3.12.x
pyenv local 3.11.8
```

### 3. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate
```

### 4. Install Python Dependencies

```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

Alternatively, use the provided setup script:

```bash
chmod +x setup.sh
./setup.sh
```

## Usage

### Start the Server

**Default (HTTP):**
```bash
python run.py
```

The server will start on `http://0.0.0.0:9000`

**With HTTPS (Optional):**
```bash
# First, generate SSL certificates if you don't have them
./generate_cert.sh

# Then start the server with HTTPS
python run.py --https
```

The server will start on `https://0.0.0.0:9000`

**Note:** Self-signed certificates will trigger browser security warnings. For production, use certificates from a trusted CA (Let's Encrypt, etc.).

### Test the Server

Test the server using the microphone test script:

**Use remote server URL from .env (default):**
```bash
python test_microphone.py
```

**Use local server (localhost):**
```bash
python test_microphone.py --local
```

**Use local server with HTTPS:**
```bash
python test_microphone.py --local --https
```

The script will:
1. Start recording from your microphone
2. Stop when you press Enter
3. Send the audio to the server for transcription
4. Display the transcribed text

**Configuration:**
- Set the remote server URL in `.env` file:
  ```
  whisper-url="https://your-server-url.com"
  ```
- When using `--local` flag, the script connects to `http://localhost:9000/transcribe` or `https://localhost:9000/transcribe`

### API Endpoint

#### POST `/transcribe`

Transcribe an audio file.

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body: `audio_file` (file upload)

**Response:**
```json
{
  "transcription": "transcribed text here",
  "detected_language": "ja"
}
```

**Example using curl (HTTP):**
```bash
curl -X POST http://localhost:9000/transcribe \
  -F "audio_file=@path/to/your/audio.wav"
```

**Example using curl (HTTPS with self-signed cert):**
```bash
curl -k -X POST https://localhost:9000/transcribe \
  -F "audio_file=@path/to/your/audio.wav"
```

**Example using JavaScript (fetch) - HTTP:**
```javascript
const formData = new FormData();
formData.append('audio_file', audioFile);

const response = await fetch('http://localhost:9000/transcribe', {
  method: 'POST',
  body: formData
});

const result = await response.json();
console.log(result.transcription);
```

**Example using JavaScript (fetch) - HTTPS:**
```javascript
const formData = new FormData();
formData.append('audio_file', audioFile);

// Note: For self-signed certificates, browsers will require user to accept the certificate
const response = await fetch('https://localhost:9000/transcribe', {
  method: 'POST',
  body: formData
});

const result = await response.json();
console.log(result.transcription);
```

## Configuration

### Model Selection

You can switch between Whisper models using a command line argument (recommended) or the `WHISPER_MODEL` environment variable:

```bash
# Use Small model (default, faster, less accurate)
python run.py

# Use Medium model via command line argument (slower, more accurate)
python run.py medium

# Use Large model via command line argument
python run.py large

# Alternative: Use environment variable
WHISPER_MODEL=medium python run.py

# Or export it for the session
export WHISPER_MODEL=medium
python run.py
```

**Priority:** Command line argument > Environment variable > Default (`small`)

**Available models:** `tiny`, `base`, `small`, `medium`, `large`, `large-v2`, `large-v3`

**Model comparison:**
- **Small**: Fast, good accuracy, ~244 MB download
- **Medium**: Slower, better accuracy, ~769 MB download
- **Large**: Slowest, best accuracy, ~1550 MB download

### Other Settings

You can modify the following settings in `run.py`:

- `DEVICE`: Device to use (`cpu` or `cuda`)
- `COMPUTE_TYPE`: Compute type (`float32`, `float16`, `int8`)

Default configuration:
- Model: `small` (can be overridden with `WHISPER_MODEL` env var)
- Device: `cpu`
- Compute Type: `float32`

## Model Download

The Whisper model will be automatically downloaded on first run. The model files are cached locally and won't be re-downloaded on subsequent runs.

## Troubleshooting

### Build Errors with `av` Package

If you encounter build errors when installing `av` (PyAV):

1. Ensure you're using Python 3.11 or 3.12 (not 3.14+)
2. Make sure ffmpeg is installed: `brew install ffmpeg`
3. Install Cython first: `pip install Cython`
4. Set environment variables:
   ```bash
   export PKG_CONFIG_PATH="/opt/homebrew/lib/pkgconfig:$PKG_CONFIG_PATH"
   export LDFLAGS="-L/opt/homebrew/lib"
   export CPPFLAGS="-I/opt/homebrew/include"
   ```

### Port Already in Use

If port 9000 is already in use, modify the port in `run.py`:

**For HTTP:**
```python
uvicorn.run(app, host="0.0.0.0", port=9001)  # Change port number
```

**For HTTPS:**
```python
uvicorn.run(
    app,
    host="0.0.0.0",
    port=9001,
    ssl_keyfile=SSL_KEYFILE,
    ssl_certfile=SSL_CERTFILE
)
```

## License

This project uses Faster Whisper, which is licensed under the MIT License.

