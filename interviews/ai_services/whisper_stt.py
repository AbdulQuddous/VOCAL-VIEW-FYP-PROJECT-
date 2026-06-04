import whisper
import logging
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)


class WhisperSTTService: 
    def __init__(self):
        """Initialize Whisper model"""
        self.model = None
        self.device = settings.AI_MODELS['WHISPER']['DEVICE']
        self.model_size = settings.AI_MODELS['WHISPER']['MODEL_SIZE']
        self.language = settings.AI_MODELS['WHISPER']['LANGUAGE']
        
    def _load_model(self):
        """Lazy load the Whisper model"""
        if self.model is None:
            logger.info(f"Loading Whisper model: {self.model_size}")
            try:
                self.model = whisper.load_model(
                    self.model_size,
                    device=self.device
                )
                logger.info("Whisper model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {str(e)}")
                raise
    
    def transcribe_audio(self, audio_file_path, language='en'):
        self._load_model()
        
        try:
            import os
            from pathlib import Path
            import tempfile
            
            # Convert to Path object
            audio_path = Path(audio_file_path).resolve()
            
            # Check if file exists
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
            file_size = audio_path.stat().st_size
            logger.info(f"Transcribing audio file: {audio_path} (size: {file_size} bytes)")
            
            # For WebM files, convert to WAV using pydub
            audio_to_transcribe = str(audio_path)
            temp_wav_path = None
            
            if audio_path.suffix.lower() == '.webm':
                try:
                    from pydub import AudioSegment
                    
                    logger.info("Converting WebM to WAV using pydub...")
                    
                    # Load WebM file
                    audio = AudioSegment.from_file(str(audio_path), format="webm")
                    
                    # Create temp WAV file
                    temp_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                    temp_wav_path = temp_wav.name
                    temp_wav.close()
                    
                    # Export as WAV (16kHz, mono for Whisper optimization)
                    audio = audio.set_frame_rate(16000).set_channels(1)
                    audio.export(temp_wav_path, format="wav")
                    
                    audio_to_transcribe = temp_wav_path
                    logger.info(f"Converted to WAV: {temp_wav_path}")
                    
                except ImportError:
                    logger.error("pydub not installed. Install with: pip install pydub")
                    raise ImportError("pydub is required for WebM conversion. Install: pip install pydub")
                except Exception as e:
                    logger.warning(f"WebM conversion failed: {e}, trying original file")
                    audio_to_transcribe = str(audio_path)
            
            # Transcribe audio
            result = self.model.transcribe(
                audio_to_transcribe,
                language=language,
                task='transcribe',
                verbose=False,
                fp16=False  # CPU doesn't support FP16
            )
            
            # Clean up temp file
            if temp_wav_path and os.path.exists(temp_wav_path):
                try:
                    os.unlink(temp_wav_path)
                    logger.info("Cleaned up temporary WAV file")
                except Exception as e:
                    logger.warning(f"Could not delete temp file: {e}")
            
            transcription_data = {
                'text': result['text'].strip(),
                'language': result.get('language', language),
                'segments': result.get('segments', []),
                'duration': self._get_audio_duration(result),
            }
            
            logger.info(f"Transcription completed: {len(transcription_data['text'])} characters")
            return transcription_data
            
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            raise
    
    def transcribe_audio_chunk(self, audio_chunk_path):
        result = self.transcribe_audio(audio_chunk_path)
        return result['text']
    
    def _get_audio_duration(self, result):
        if 'segments' in result and len(result['segments']) > 0:
            return result['segments'][-1]['end']
        return 0.0
    
    def get_word_timestamps(self, audio_file_path):
        self._load_model()
        
        try:
            # Convert WebM if needed
            audio_path = Path(audio_file_path)
            if audio_path.suffix.lower() == '.webm':
                # Use transcribe_audio which handles conversion
                result = self.model.transcribe(
                    str(audio_path),
                    word_timestamps=True,
                    language=self.language,
                    fp16=False
                )
            else:
                result = self.model.transcribe(
                    str(audio_file_path),
                    word_timestamps=True,
                    language=self.language,
                    fp16=False
                )
            
            word_timestamps = []
            for segment in result.get('segments', []):
                for word in segment.get('words', []):
                    word_timestamps.append({
                        'word': word['word'].strip(),
                        'start': word['start'],
                        'end': word['end'],
                    })
            
            return word_timestamps
            
        except Exception as e:
            logger.error(f"Failed to get word timestamps: {str(e)}")
            return []
    
    def calculate_speaking_pace(self, audio_file_path):
        result = self.transcribe_audio(audio_file_path)
        
        text = result['text']
        duration = result['duration']
        
        if duration == 0:
            return 0
        
        word_count = len(text.split())
        words_per_minute = (word_count / duration) * 60
        
        return round(words_per_minute, 2)
    
    def detect_pauses(self, audio_file_path, min_pause_duration=0.5):
        word_timestamps = self.get_word_timestamps(audio_file_path)
        
        pauses = []
        for i in range(len(word_timestamps) - 1):
            gap = word_timestamps[i + 1]['start'] - word_timestamps[i]['end']
            if gap >= min_pause_duration:
                pauses.append({
                    'start': word_timestamps[i]['end'],
                    'end': word_timestamps[i + 1]['start'],
                    'duration': gap
                })
        
        return pauses

# Singleton instance
_whisper_service = None

def get_whisper_service():
    global _whisper_service
    if _whisper_service is None:
        _whisper_service = WhisperSTTService()
    return _whisper_service