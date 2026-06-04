import librosa
import numpy as np
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class LibrosaProsodyService:

    def __init__(self):

        self.sample_rate = settings.AI_MODELS['LIBROSA']['SAMPLE_RATE']
        self.hop_length = 512

        # REDUCED for better pause detection
        self.min_pause_duration = 0.25  # Was 0.30 - now detects shorter pauses
        
        self.frame_duration = self.hop_length / self.sample_rate

        logger.info("Advanced Prosody Service Initialized")

    def analyze_audio(self, audio_path, transcription_text=""):

        try:

            logger.info(f"Analyzing audio: {audio_path}")

            y, sr = librosa.load(
                str(audio_path),
                sr=self.sample_rate
            )

            if y is None or len(y) == 0:
                return self._get_default_analysis()

            # REMOVED aggressive trimming - was cutting off pauses
            # y_trimmed, _ = librosa.effects.trim(y, top_db=30, frame_length=2048, hop_length=self.hop_length)
            # y = y_trimmed

            audio_duration = len(y) / sr

            if audio_duration < 1.5:
                logger.warning("Audio too short")
                return self._get_default_analysis()

            # Detect pauses with lower threshold
            pause_data = self._detect_pauses(y, sr)

            total_pause_duration = pause_data['total_pause_duration']

            speech_duration = max(
                1.0,
                audio_duration - total_pause_duration
            )

            speaking_pace = self._calculate_speaking_pace(
                speech_duration,
                transcription_text
            )

            pitch_features = self._calculate_pitch_features(
                y,
                sr
            )

            energy_features = self._calculate_energy_features(
                y
            )

            # FIXED: Volume calculation - now returns actual percentage
            volume_features = self._calculate_volume_features(
                y
            )
            
            vocal_confidence = self._calculate_vocal_confidence(
                speaking_pace,
                pitch_features,
                energy_features,
                pause_data
            )

            pace_timeline = self._generate_real_pace_timeline(
                y,
                sr,
                transcription_text
            )

            pitch_timeline = self._generate_pitch_timeline(
                y,
                sr
            )

            energy_timeline = self._generate_energy_timeline(
                y
            )

            # Log pause summary for debugging
            logger.info(f"Pause detection results: total={pause_data['pause_count']}, "
                       f"natural={pause_data['natural_pauses']}, "
                       f"hesitation={pause_data['hesitation_pauses']}, "
                       f"long={pause_data['long_pauses']}")

            return {

                'speaking_pace_wpm': speaking_pace,

                'average_pitch_hz': pitch_features['mean_pitch'],

                'pitch_variation': pitch_features['pitch_std'],

                'volume_consistency': volume_features['consistency'],

                'energy_stability': energy_features['stability'],

                'vocal_confidence': vocal_confidence,

                'pause_count': pause_data['pause_count'],

                'natural_pauses': pause_data['natural_pauses'],

                'hesitation_pauses': pause_data['hesitation_pauses'],

                'long_pauses': pause_data['long_pauses'],

                'average_pause_duration': pause_data['average_pause_duration'],

                'total_pause_duration': total_pause_duration,

                'speech_duration': round(speech_duration, 2),

                'audio_duration': round(audio_duration, 2),

                'pace_timeline': pace_timeline,

                'pitch_timeline': pitch_timeline,

                'energy_timeline': energy_timeline
            }

        except Exception as e:

            logger.error(f"Prosody analysis failed: {e}", exc_info=True)

            return self._get_default_analysis()

    def _detect_pauses(self, y, sr):
        """
        Detect and classify pauses in audio.
        
        Fixed:
        - Lowered top_db to detect quieter pauses
        - Added debug logging
        - Better pause classification
        """
        # LOWERED top_db from 30 to 20 for better pause detection
        intervals = librosa.effects.split(
            y,
            top_db=20,  # Was 30 - more sensitive to silence
            frame_length=2048,
            hop_length=self.hop_length
        )

        logger.debug(f"Detected {len(intervals)} speech intervals")

        pause_durations = []
        natural_pauses = 0
        hesitation_pauses = 0
        long_pauses = 0

        for i in range(len(intervals) - 1):
            gap = (intervals[i + 1][0] - intervals[i][1]) / sr
            
            # Debug logging for each gap
            if gap >= 0.1:  # Log any gap > 0.1s
                logger.debug(f"Gap {i}: {gap:.3f}s between {intervals[i]} and {intervals[i+1]}")

            if gap >= self.min_pause_duration:
                pause_durations.append(gap)
                
                if gap < 1.0:
                    natural_pauses += 1
                    logger.debug(f"  → Natural pause: {gap:.3f}s")
                elif gap < 2.0:
                    hesitation_pauses += 1
                    logger.debug(f"  → HESITATION pause: {gap:.3f}s")
                else:
                    long_pauses += 1
                    logger.debug(f"  → LONG pause: {gap:.3f}s")

        logger.info(f"Pause summary: total={len(pause_durations)}, "
                   f"natural={natural_pauses}, hesitation={hesitation_pauses}, long={long_pauses}")

        return {
            'pause_count': len(pause_durations),
            'natural_pauses': natural_pauses,
            'hesitation_pauses': hesitation_pauses,
            'long_pauses': long_pauses,
            'average_pause_duration': round(
                float(np.mean(pause_durations)), 2
            ) if pause_durations else 0.0,
            'total_pause_duration': round(
                float(np.sum(pause_durations)), 2
            ) if pause_durations else 0.0
        }

    def _calculate_speaking_pace(
        self,
        speech_duration_seconds,
        transcription_text
    ):

        if not transcription_text:
            return 120.0

        words = transcription_text.split()
        word_count = len(words)
        speech_minutes = speech_duration_seconds / 60.0

        if speech_minutes <= 0:
            return 120.0

        wpm = word_count / speech_minutes
        return round(wpm, 1)

    def _calculate_pitch_features(self, y, sr):

        try:
            f0 = librosa.yin(
                y,
                fmin=75,
                fmax=400,
                sr=sr
            )

            f0 = f0[~np.isnan(f0)]

            if len(f0) == 0:
                return {
                    'mean_pitch': 150.0,
                    'pitch_std': 20.0
                }

            return {
                'mean_pitch': round(float(np.mean(f0)), 1),
                'pitch_std': round(float(np.std(f0)), 1)
            }

        except Exception:
            return {
                'mean_pitch': 150.0,
                'pitch_std': 20.0
            }

    def _calculate_energy_features(self, y):

        rms = librosa.feature.rms(
            y=y,
            hop_length=self.hop_length
        )[0]

        energy_diff = np.diff(rms)

        stability = max(
            0,
            min(
                100,
                100 - (np.std(energy_diff) * 1000)
            )
        )

        return {
            'stability': round(float(stability), 1)
        }

    def _calculate_volume_features(self, y):
        """
        Calculate volume consistency (0-100).
        
        IMPROVED: Better scaling for low-volume audio
        """
        rms = librosa.feature.rms(
            y=y,
            hop_length=self.hop_length
        )[0]
        
        # IMPROVED: Better normalization for typical interview audio
        # Most interview audio has RMS between 0.01 and 0.3
        max_expected_rms = 0.3  # Was 0.5 - more sensitive
        
        # Apply non-linear scaling to boost low volumes
        normalized_rms = np.clip(rms / max_expected_rms, 0, 1) * 100
        
        # Apply exponential scaling to make low volumes more visible
        # This boosts values below 30% significantly
        boosted_rms = np.power(normalized_rms / 100, 0.7) * 100
        
        mean_rms = np.mean(boosted_rms)
        std_rms = np.std(boosted_rms)
        
        # Calculate consistency: lower std = higher consistency
        if mean_rms > 0:
            cv = std_rms / mean_rms
        else:
            cv = 1.0
        
        # Convert to consistency score (0-100)
        consistency = max(0, min(100, (1 - min(cv, 1)) * 100))
        
        # IMPROVED: Boost consistency for low-volume but stable audio
        # If volume is consistently low but stable, give a better score
        if std_rms < 5:  # Very stable volume
            consistency = max(consistency, 50)
        
        # Minimum floor for any detected audio
        if mean_rms > 0:
            consistency = max(consistency, 35)
        
        logger.debug(f"Volume analysis: raw_mean={np.mean(rms):.4f}, "
                    f"boosted_mean={mean_rms:.1f}%, std={std_rms:.1f}, "
                    f"consistency={consistency:.1f}%")
        
        return {
            'consistency': round(float(consistency), 1)
        }

    def _calculate_vocal_confidence(
        self,
        pace,
        pitch_features,
        energy_features,
        pause_data
    ):
        """
        Calculate vocal confidence score (0-100).
        
        Updated to use hesitation_pauses and long_pauses correctly.
        """
        score = 70

        # Pace scoring
        if 110 <= pace <= 160:
            score += 10
        elif 90 <= pace <= 180:
            score += 5
        else:
            score -= 10

        # Pitch variation scoring
        pitch_std = pitch_features['pitch_std']
        if 15 <= pitch_std <= 45:
            score += 10
        elif pitch_std < 8:
            score -= 10

        # Energy stability contribution
        score += (energy_features['stability'] - 50) * 0.2

        # FIXED: Penalize hesitation and long pauses properly
        hesitation_penalty = pause_data['hesitation_pauses'] * 3
        long_pause_penalty = pause_data['long_pauses'] * 8
        
        score -= hesitation_penalty
        score -= long_pause_penalty
        
        logger.debug(f"Confidence calculation: base=70, pace={pace}, pitch_std={pitch_std}, "
                    f"hesitation_penalty={hesitation_penalty}, long_pause_penalty={long_pause_penalty}, "
                    f"final={round(max(20, min(100, score)), 1)}")

        return round(max(20, min(100, score)), 1)

    def _generate_real_pace_timeline(
        self,
        y,
        sr,
        transcription_text
    ):
        """
        Generate pace timeline.
        FIXED: Now uses word count per segment instead of random values.
        """
        timeline = {}
        
        if not transcription_text:
            return timeline
        
        words = transcription_text.split()
        duration = len(y) / sr
        segment_duration = 5  # 5-second segments
        
        num_segments = int(duration / segment_duration) + 1
        
        for i in range(num_segments):
            start_idx = i * segment_duration
            end_idx = min((i + 1) * segment_duration, duration)
            
            # Calculate approximate words in this segment
            word_positions = np.linspace(0, len(words), num_segments + 1)
            segment_words = int(word_positions[i + 1] - word_positions[i]) if i < len(word_positions) - 1 else 0
            
            if segment_words > 0 and (end_idx - start_idx) > 0:
                pace = (segment_words / ((end_idx - start_idx) / 60))
            else:
                pace = 120
            
            timeline[str(int(start_idx))] = round(max(60, min(200, pace)), 1)
        
        return timeline

    def _generate_pitch_timeline(self, y, sr):
        """
        Generate pitch timeline using actual pitch detection.
        FIXED: Now uses real pitch values instead of random.
        """
        timeline = {}
        
        try:
            # Calculate pitch for each second
            duration = len(y) / sr
            hop_length_sec = int(sr * 0.5)  # Every 0.5 seconds
            hop_length_samples = int(sr * 0.5)
            
            # Use librosa to get pitch
            f0 = librosa.yin(y, fmin=75, fmax=400, sr=sr)
            
            # Resample to 1-second intervals
            samples_per_second = len(f0) / duration
            
            for second in range(int(duration)):
                idx = int(second * samples_per_second)
                if idx < len(f0) and not np.isnan(f0[idx]):
                    pitch = round(float(f0[idx]), 1)
                else:
                    pitch = 150.0
                
                timeline[str(second)] = pitch
            
        except Exception as e:
            logger.warning(f"Error generating pitch timeline: {e}")
            # Fallback to default
            duration = len(y) / sr
            for second in range(int(duration)):
                timeline[str(second)] = 150.0
        
        return timeline

    def _generate_energy_timeline(self, y):
        """
        Generate energy timeline.
        FIXED: Now includes timestamp keys.
        """
        rms = librosa.feature.rms(
            y=y,
            hop_length=self.hop_length
        )[0]
        
        timeline = {}
        
        # Calculate time for each frame
        duration = len(y) / self.sample_rate
        num_frames = len(rms)
        
        for i, energy in enumerate(rms):
            timestamp = (i * self.hop_length) / self.sample_rate
            timeline[str(round(timestamp, 1))] = round(float(energy * 100), 2)  # Scale to 0-100
        
        return timeline

    def _get_default_analysis(self):

        return {
            'speaking_pace_wpm': 120.0,
            'average_pitch_hz': 150.0,
            'pitch_variation': 20.0,
            'volume_consistency': 70.0,
            'energy_stability': 70.0,
            'vocal_confidence': 70.0,
            'pause_count': 0,
            'natural_pauses': 0,
            'hesitation_pauses': 0,
            'long_pauses': 0,
            'average_pause_duration': 0.0,
            'total_pause_duration': 0.0,
            'speech_duration': 0.0,
            'audio_duration': 0.0,
            'pace_timeline': {},
            'pitch_timeline': {},
            'energy_timeline': {}
        }


_librosa_service = None


def get_librosa_service():

    global _librosa_service

    if _librosa_service is None:
        _librosa_service = LibrosaProsodyService()

    return _librosa_service