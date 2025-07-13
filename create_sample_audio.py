#!/usr/bin/env python3
"""
Script to create a sample audio file for testing the Whisper + Pyannote API.
This creates a simple WAV file with some speech-like content.
"""

import numpy as np
import soundfile as sf
import os

def create_sample_audio():
    """Create a sample audio file with multiple speakers"""
    
    # Audio parameters
    sample_rate = 16000  # 16kHz sample rate
    duration = 10  # 10 seconds
    num_samples = sample_rate * duration
    
    # Create time array
    t = np.linspace(0, duration, num_samples, False)
    
    # Create a simple speech-like signal with multiple "speakers"
    # This is a simplified version - real speech would be more complex
    
    # Speaker 1 (first 3 seconds)
    speaker1 = np.sin(2 * np.pi * 200 * t[:int(3 * sample_rate)]) * 0.3
    speaker1 += np.sin(2 * np.pi * 400 * t[:int(3 * sample_rate)]) * 0.2
    
    # Silence (1 second)
    silence = np.zeros(int(1 * sample_rate))
    
    # Speaker 2 (next 3 seconds)
    speaker2 = np.sin(2 * np.pi * 300 * t[:int(3 * sample_rate)]) * 0.3
    speaker2 += np.sin(2 * np.pi * 500 * t[:int(3 * sample_rate)]) * 0.2
    
    # Silence (1 second)
    silence2 = np.zeros(int(1 * sample_rate))
    
    # Speaker 1 again (last 2 seconds)
    speaker1_again = np.sin(2 * np.pi * 250 * t[:int(2 * sample_rate)]) * 0.3
    speaker1_again += np.sin(2 * np.pi * 450 * t[:int(2 * sample_rate)]) * 0.2
    
    # Combine all segments
    audio = np.concatenate([speaker1, silence, speaker2, silence2, speaker1_again])
    
    # Add some noise to make it more realistic
    noise = np.random.normal(0, 0.01, len(audio))
    audio += noise
    
    # Normalize audio
    audio = audio / np.max(np.abs(audio)) * 0.8
    
    # Save as WAV file
    output_file = "sample.wav"
    sf.write(output_file, audio, sample_rate)
    
    print(f"✅ Created sample audio file: {output_file}")
    print(f"📊 Audio details:")
    print(f"   - Duration: {duration} seconds")
    print(f"   - Sample rate: {sample_rate} Hz")
    print(f"   - Format: WAV")
    print(f"   - Size: {os.path.getsize(output_file) / 1024:.1f} KB")
    print(f"\n🎤 Audio structure:")
    print(f"   - 0-3s: Speaker 1 (200Hz + 400Hz)")
    print(f"   - 3-4s: Silence")
    print(f"   - 4-7s: Speaker 2 (300Hz + 500Hz)")
    print(f"   - 7-8s: Silence")
    print(f"   - 8-10s: Speaker 1 again (250Hz + 450Hz)")

if __name__ == "__main__":
    create_sample_audio() 