# 🎤 Whisper + Pyannote Audio Processing API

A fully-featured microservice for audio transcription and speaker diarization using OpenAI Whisper and pyannote.audio.

## ✨ Features

- **🎤 Audio Transcription**: OpenAI Whisper for high-quality speech-to-text
- **👥 Speaker Diarization**: pyannote.audio for speaker identification
- **🔗 Webhook Support**: Optional callback notifications with delivery tracking
- **🔐 OAuth Authentication**: Google and GitHub OAuth support
- **🔐 Session Management**: Secure session-based authentication
- **🧑‍💼 Admin Dashboard**: Comprehensive job management interface
- **📊 Database Storage**: SQLite/PostgreSQL job tracking and metadata
- **📁 File Storage**: Organized user-specific file storage
- **🌐 Web UI**: Beautiful upload interface with user management
- **🐳 Docker Ready**: Containerized deployment
- **📊 Processing Timeline**: Detailed step-by-step tracking

## 🚀 Quick Start

### Using Docker (Recommended)

1. **Build the Docker image:**
   ```bash
   docker build -t whisper-diarization-app .
   ```

2. **Run the container:**
   ```bash
   docker run -p 8000:8000 whisper-diarization-app
   ```

3. **Access the web interface:**
   ```
   http://localhost:8000
   ```

### Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up HuggingFace token (for diarization):**
   ```bash
   export HF_TOKEN="your_huggingface_token_here"
   ```

3. **Run the application:**
   ```bash
   python app.py
   ```

## 🔧 Setup Requirements

### Environment Variables

#### Required:
- **HF_TOKEN**: HuggingFace token for pyannote.audio diarization
  - Go to [HuggingFace](https://huggingface.co/pyannote/speaker-diarization)
  - Accept the model terms
  - Create a token at [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
  - Set: `export HF_TOKEN="your_token"`

#### Optional (for OAuth):
- **GOOGLE_CLIENT_ID** & **GOOGLE_CLIENT_SECRET**: Google OAuth credentials
- **GITHUB_CLIENT_ID** & **GITHUB_CLIENT_SECRET**: GitHub OAuth credentials
- **SECRET_KEY**: Session secret key (auto-generated if not set)
- **DATABASE_URL**: Database connection string (defaults to SQLite)

### System Requirements

- Python 3.10+
- FFmpeg (for audio processing)
- At least 4GB RAM (for model loading)
- GPU recommended for faster processing

## 📡 API Endpoints

### POST `/process`

Process an audio file with transcription and diarization.

**Headers:**
```
Authorization: Basic <base64_encoded_credentials>
```

**Form Data:**
- `file`: Audio file (WAV, MP3, M4A, M4V, FLAC, OGG)
- `language`: Language code (default: "en")
- `webhook_url`: Optional webhook URL

**Response:**
```json
{
  "status": "success",
  "processing_steps": {
    "upload": "2024-01-01T12:00:00",
    "transcription": "2024-01-01T12:01:00",
    "diarization": "2024-01-01T12:02:00",
    "merge": "2024-01-01T12:02:30",
    "webhook": "2024-01-01T12:03:00"
  },
  "transcript_file": {
    "text": "Hello world",
    "segments": [...]
  },
  "diarization_file": {
    "segments": [
      {
        "start": 0.0,
        "end": 2.5,
        "speaker": "SPEAKER_00"
      }
    ]
  },
  "merged_file": {
    "language": "en",
    "segments": [
      {
        "start": 0.0,
        "end": 2.5,
        "text": "Hello world",
        "speaker": "SPEAKER_00"
      }
    ]
  },
  "webhook_sent": true,
  "file_info": {
    "original_name": "sample.wav",
    "size": 123456,
    "content_type": "audio/wav"
  }
}
```

### GET `/`

Web interface for file upload and processing (requires authentication).

### GET `/login`

Login page with OAuth and username/password options.

### GET `/admin`

Admin dashboard (requires admin privileges).

### GET `/admin/jobs`

Get jobs with filtering and pagination (admin only).

### GET `/admin/stats`

Get admin statistics (admin only).

### GET `/admin/download/{job_id}/{file_type}`

Download job files (admin only).

### DELETE `/admin/jobs/{job_id}`

Delete a job and its files (admin only).

### GET `/health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "models_loaded": {
    "whisper": true,
    "pyannote": true
  }
}
```

## 🔐 Authentication

### Test Credentials:
- **Email**: `admin@example.com`
- **Password**: `password123`

### OAuth Support:
- **Google OAuth**: Configure with Google Cloud Console
- **GitHub OAuth**: Configure with GitHub Developer Settings

### Session Management:
- Secure session cookies with configurable expiration
- Automatic session cleanup
- CSRF protection enabled

## 📁 Project Structure

```
whisper_pyannote_api_ui/
├── app.py                 # Main FastAPI application
├── auth.py               # Authentication and OAuth logic
├── models.py             # SQLAlchemy database models
├── database.py           # Database utilities and queries
├── requirements.txt      # Python dependencies
├── Dockerfile           # Docker configuration
├── docker-compose.yml   # Docker Compose setup
├── setup.sh             # Automated setup script
├── create_sample_audio.py # Script to generate test audio
├── test_api.py          # API testing script
├── sample.wav           # Sample audio file (generated)
├── templates/
│   ├── index.html       # Main upload interface
│   ├── login.html       # Login page with OAuth
│   └── admin.html       # Admin dashboard
├── output/              # User file storage (created automatically)
└── README.md           # This file
```

## 🧪 Testing

### Generate Sample Audio

```bash
python create_sample_audio.py
```

This creates a `sample.wav` file with multiple speakers for testing.

### Test with curl

```bash
# Test the API endpoint
curl -X POST "http://localhost:8000/process" \
  -H "Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=" \
  -F "file=@sample.wav" \
  -F "language=en"
```

### Test Webhook

```bash
# Start a webhook receiver (in another terminal)
python -m http.server 8080

# Test with webhook
curl -X POST "http://localhost:8000/process" \
  -H "Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=" \
  -F "file=@sample.wav" \
  -F "language=en" \
  -F "webhook_url=http://localhost:8080/webhook"
```

## 🔧 Configuration

### Environment Variables

- `HF_TOKEN`: HuggingFace token for pyannote.audio
- `VALID_USERNAME`: Basic auth username (default: admin)
- `VALID_PASSWORD`: Basic auth password (default: password123)

### Model Configuration

The application uses:
- **Whisper Model**: `base` (can be changed to `tiny`, `small`, `medium`, `large`)
- **Pyannote Model**: `pyannote/speaker-diarization@2.1`

## 🐛 Troubleshooting

### Common Issues

1. **"Diarization pipeline not loaded"**
   - Set the `HF_TOKEN` environment variable
   - Accept the model terms on HuggingFace

2. **"CUDA out of memory"**
   - Use CPU-only processing by setting `CUDA_VISIBLE_DEVICES=""`
   - Reduce batch size or use smaller models

3. **"FFmpeg not found"**
   - Install FFmpeg: `apt-get install ffmpeg` (Ubuntu/Debian)
   - Or use the Docker image which includes FFmpeg

4. **Slow processing**
   - Use GPU acceleration if available
   - Consider using smaller Whisper models for faster processing

### Logs

The application provides detailed logging:
- Model loading progress
- Processing step timestamps
- Error details with stack traces

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🙏 Acknowledgments

- [OpenAI Whisper](https://github.com/openai/whisper) for transcription
- [pyannote.audio](https://github.com/pyannote/pyannote-audio) for speaker diarization
- [FastAPI](https://fastapi.tiangolo.com/) for the web framework
