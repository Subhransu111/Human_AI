import webrtcvad

def detect_voice_activity(audio_data: bytes, sample_rate: int = 16000) -> bool:
    """Detect if audio contains voice"""
    vad = webrtcvad.Vad(2)
    
    try:
        frame_duration = 20
        samples_per_frame = (sample_rate * frame_duration) // 1000
        
        has_voice = False
        for i in range(0, len(audio_data), samples_per_frame * 2):
            frame = audio_data[i:i + samples_per_frame * 2]
            if len(frame) == samples_per_frame * 2:
                if vad.is_speech(frame, sample_rate):
                    has_voice = True
                    break
        
        return has_voice
    except Exception as e:
        print(f"VAD error: {e}")
        return False