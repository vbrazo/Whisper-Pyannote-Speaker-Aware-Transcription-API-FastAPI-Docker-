from typing import Dict, Any

def merge_transcript_and_diarization(transcript: Dict[str, Any], diarization: Dict[str, Any]) -> Dict[str, Any]:
    """Merge transcript segments with speaker diarization"""
    transcript_segments = transcript.get("segments", [])
    diarization_segments = diarization.get("segments", [])
    
    merged_segments = []
    
    for ts in transcript_segments:
        segment_start = ts["start"]
        segment_end = ts["end"]
        text = ts["text"]
        
        speakers = []
        for ds in diarization_segments:
            if (ds["start"] <= segment_end and ds["end"] >= segment_start):
                overlap_start = max(ds["start"], segment_start)
                overlap_end = min(ds["end"], segment_end)
                overlap_duration = overlap_end - overlap_start
                
                speakers.append({
                    "speaker": ds["speaker"],
                    "overlap_duration": overlap_duration
                })
        
        if speakers:
            primary_speaker = max(speakers, key=lambda x: x["overlap_duration"])
            speaker = primary_speaker["speaker"]
        else:
            speaker = "unknown"
        
        merged_segments.append({
            "start": segment_start,
            "end": segment_end,
            "text": text,
            "speaker": speaker
        })
    
    return {
        "language": transcript.get("language", "unknown"),
        "segments": merged_segments
    } 