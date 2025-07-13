#!/bin/bash

# Whisper + Pyannote API Setup Script
# This script helps you set up and run the audio processing API

set -e

echo "🎤 Whisper + Pyannote API Setup"
echo "================================"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "   Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    echo "   Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"

# Create sample audio file if it doesn't exist
if [ ! -f "sample.wav" ]; then
    echo "🎵 Creating sample audio file..."
    if command -v python3 &> /dev/null; then
        python3 create_sample_audio.py
    else
        echo "⚠️  Python3 not found. Please create sample.wav manually or install Python3."
        echo "   You can run: python3 create_sample_audio.py"
    fi
else
    echo "✅ Sample audio file exists"
fi

# Check for HF_TOKEN
if [ -z "$HF_TOKEN" ]; then
    echo ""
    echo "⚠️  IMPORTANT: HuggingFace Token Required"
    echo "=========================================="
    echo "For speaker diarization to work, you need a HuggingFace token:"
    echo ""
    echo "1. Go to: https://huggingface.co/pyannote/speaker-diarization"
    echo "2. Accept the model terms"
    echo "3. Create a token at: https://huggingface.co/settings/tokens"
    echo "4. Set the environment variable:"
    echo ""
    echo "   export HF_TOKEN='your_token_here'"
    echo ""
    echo "Or create a .env file with:"
    echo "   HF_TOKEN=your_token_here"
    echo ""
    echo "Without the token, diarization will not work, but transcription will still function."
    echo ""
fi

# Build and run with Docker Compose
echo "🐳 Building and starting the application..."
docker-compose up --build -d

echo ""
echo "✅ Setup complete!"
echo "=================="
echo ""
echo "🌐 Web Interface: http://localhost:8000"
echo "🔐 Username: admin"
echo "🔐 Password: password123"
echo ""
echo "📡 API Endpoint: http://localhost:8000/process"
echo "🏥 Health Check: http://localhost:8000/health"
echo ""
echo "🧪 Test the API:"
echo "   python3 test_api.py"
echo ""
echo "📋 View logs:"
echo "   docker-compose logs -f"
echo ""
echo "🛑 Stop the application:"
echo "   docker-compose down"
echo ""
echo "📚 For more information, see README.md" 