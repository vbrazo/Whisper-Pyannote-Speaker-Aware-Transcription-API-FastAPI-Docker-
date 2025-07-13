try:
    from pyannote.audio import Pipeline
    PYANNOTE_AVAILABLE = True
except ImportError:
    print("Warning: pyannote.audio not available. Creating mock.")
    PYANNOTE_AVAILABLE = False
    
    class MockPipeline:
        def __init__(self, *args, **kwargs):
            pass
        
        def __call__(self, audio_path):
            return MockDiarization()
    
    class MockDiarization:
        def itertracks(self, yield_label=True):
            return []
    
    Pipeline = MockPipeline

from fastapi import HTTPException
from typing import Dict, Any

from app.core.config import settings

# Global diarization pipeline
diarization_pipeline = None

def load_diarization_pipeline():
    """Load Pyannote diarization pipeline"""
    global diarization_pipeline
    print("Loading Pyannote diarization pipeline...")
    
    if not PYANNOTE_AVAILABLE:
        print("Warning: pyannote.audio not available. Using mock.")
        diarization_pipeline = Pipeline()
        return
    
    hf_token = settings.HF_TOKEN
    if not hf_token:
        print("Warning: HF_TOKEN not set. Diarization will not work.")
        diarization_pipeline = None
    else:
        diarization_pipeline = Pipeline.from_pretrained(
            settings.PYANNOTE_MODEL,
            use_auth_token=hf_token
        )
        print(f"✅ Pyannote model '{settings.PYANNOTE_MODEL}' loaded")

def get_diarization_pipeline():
    """Get the loaded diarization pipeline"""
    global diarization_pipeline
    if diarization_pipeline is None:
        load_diarization_pipeline()
    return diarization_pipeline

async def diarize_speakers(audio_path: str) -> Dict[str, Any]:
    """Diarize speakers using pyannote.audio"""
    pipeline = get_diarization_pipeline()
    if pipeline is None:
        raise HTTPException(
            status_code=500, 
            detail="Diarization pipeline not loaded. Set HF_TOKEN environment variable."
        )
    
    try:
        print("Running speaker diarization...")
        diarization = pipeline(audio_path)
        
        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append({
                "start": turn.start,
                "end": turn.end,
                "speaker": speaker
            })
        
        return {"segments": segments}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Diarization failed: {str(e)}") 