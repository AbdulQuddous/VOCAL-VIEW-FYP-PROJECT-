import cv2
import mediapipe as mp
import numpy as np
import logging
from collections import deque
from django.conf import settings

logger = logging.getLogger(__name__)


class MediaPipeFacialService:
    def __init__(self):
        """Initialize MediaPipe face mesh with iris refinement"""
        self.mp_face_mesh = mp.solutions.face_mesh
        self.mp_drawing = mp.solutions.drawing_utils
        self.face_mesh = None
        
        # MediaPipe configuration
        self.min_detection_confidence = settings.AI_MODELS['MEDIAPIPE']['MIN_DETECTION_CONFIDENCE']
        self.min_tracking_confidence = settings.AI_MODELS['MEDIAPIPE']['MIN_TRACKING_CONFIDENCE']
        
        # Temporal smoothing buffers
        self.smoothing_window = 5  
        self.confidence_buffer = deque(maxlen=self.smoothing_window)
        self.stress_buffer = deque(maxlen=self.smoothing_window)
        self.eye_contact_buffer = deque(maxlen=self.smoothing_window)
    
    def _load_model(self):
        """Lazy load MediaPipe face mesh with iris landmarks"""
        if self.face_mesh is None:
            logger.info("Loading MediaPipe Face Mesh model")
            try:
                self.face_mesh = self.mp_face_mesh.FaceMesh(
                    static_image_mode=False,
                    max_num_faces=1,
                    refine_landmarks=True,  
                    min_detection_confidence=self.min_detection_confidence,
                    min_tracking_confidence=self.min_tracking_confidence
                )
                logger.info("MediaPipe model loaded successfully (with iris refinement)")
            except Exception as e:
                logger.error(f"Failed to load MediaPipe model: {str(e)}")
                raise
    
    def analyze_video(self, video_path):
        self._load_model()
        # Reset smoothing buffers
        self.confidence_buffer.clear()
        self.stress_buffer.clear()
        self.eye_contact_buffer.clear()
        
        try:
            logger.info(f"Analyzing video: {video_path}")
            
            cap = cv2.VideoCapture(str(video_path))
            
            if not cap.isOpened():
                raise ValueError(f"Cannot open video file: {video_path}")
            
            # Get video properties
            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            logger.info(f"Video properties: {frame_width}x{frame_height} @ {fps}fps")
            
            # Analysis storage
            frame_analyses = []
            frame_count = 0
            
            # OPTIMIZED: Sample every 4th frame (balanced)
            sample_rate = 4
            
            logger.info(f"Frame sampling: every {sample_rate} frames (~{fps/sample_rate:.1f} samples/sec)")
            
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                
                frame_count += 1
                
                # Sample frames
                if frame_count % sample_rate != 0:
                    continue
                
                # Analyze frame with temporal smoothing
                frame_analysis = self._analyze_frame(frame, frame_width, frame_height)
                if frame_analysis:
                    timestamp = int(frame_count / fps)
                    frame_analysis['timestamp'] = timestamp
                    frame_analyses.append(frame_analysis)
            
            cap.release()
            
            if not frame_analyses:
                logger.warning("No faces detected in video")
                return self._get_default_analysis()
            
            # Aggregate results
            aggregated_analysis = self._aggregate_frame_analyses(frame_analyses)
            
            logger.info(f"Video analysis completed: {len(frame_analyses)} frames analyzed")
            logger.info(f"Average confidence: {aggregated_analysis['confidence_score']:.1f}%, "
                       f"Average stress: {aggregated_analysis['stress_score']:.1f}%, "
                       f"Eye contact: {aggregated_analysis['eye_contact_score']:.1f}%")
            
            return aggregated_analysis
            
        except Exception as e:
            logger.error(f"Video analysis failed: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    def _analyze_frame(self, frame, frame_width, frame_height):
        """
        Analyze a single frame with improved calculations
        """
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Process frame
        results = self.face_mesh.process(rgb_frame)
        
        if not results.multi_face_landmarks:
            return None
        
        # Get first face
        face_landmarks = results.multi_face_landmarks[0]
        
        # Calculate scores with temporal smoothing
        confidence_score = self._calculate_confidence_from_landmarks(face_landmarks, frame_width, frame_height)
        stress_score = self._calculate_stress_from_landmarks(face_landmarks, frame_width, frame_height)
        
        # eye contact using iris landmarks
        eye_contact = self._calculate_eye_contact_from_landmarks(face_landmarks, frame_width, frame_height)
        
        # Apply temporal smoothing
        smoothed_confidence = self._apply_smoothing(confidence_score, self.confidence_buffer)
        smoothed_stress = self._apply_smoothing(stress_score, self.stress_buffer)
        smoothed_eye_contact = self._apply_smoothing(eye_contact, self.eye_contact_buffer)
        
        emotion = self._classify_emotion_from_scores(smoothed_confidence, smoothed_stress)
        
        analysis = {
            'confidence_score': smoothed_confidence,
            'stress_score': smoothed_stress,
            'eye_contact_score': smoothed_eye_contact,
            'emotion': emotion,
        }
        
        return analysis
    
    def _apply_smoothing(self, value: float, buffer: deque) -> float:
        buffer.append(value)
        return float(np.mean(buffer))
    
    def _calculate_eye_contact_from_landmarks(self, face_landmarks, w, h):
        try:
            left_eye_left_corner = face_landmarks.landmark[33]   # Outer corner
            left_eye_right_corner = face_landmarks.landmark[133]  # Inner corner
            
            left_iris_center = face_landmarks.landmark[468]
            
            left_eye_width = abs(left_eye_right_corner.x - left_eye_left_corner.x)
            
            left_iris_x_norm = (left_iris_center.x - left_eye_left_corner.x) / (left_eye_width + 0.001)
            
            right_eye_left_corner = face_landmarks.landmark[362]  # Inner corner
            right_eye_right_corner = face_landmarks.landmark[263]  # Outer corner
            
            right_iris_center = face_landmarks.landmark[473]
            
            right_eye_width = abs(right_eye_right_corner.x - right_eye_left_corner.x)
            
            right_iris_x_norm = (right_iris_center.x - right_eye_left_corner.x) / (right_eye_width + 0.001)
            
            # GAZE DIRECTION 
            # Average normalized iris position
            avg_iris_position = (left_iris_x_norm + right_iris_x_norm) / 2
            
            # Centered gaze: iris position around 0.4-0.6 (ideal: 0.5)
            # Looking left: < 0.4
            # Looking right: > 0.6
            
            # Calculate deviation from center (0.5 = perfect center)
            center_deviation = abs(avg_iris_position - 0.5)
            
            # Perfect center (deviation < 0.05): 95-100 points
            # Good center (deviation < 0.10): 80-95 points
            # Slightly off (deviation < 0.15): 65-80 points
            # Looking away (deviation < 0.20): 45-65 points
            # Clearly away (deviation >= 0.20): 20-45 points
            
            if center_deviation < 0.05:
                score = 95 + (1 - center_deviation / 0.05) * 5  # 95-100
            elif center_deviation < 0.10:
                score = 80 + (1 - (center_deviation - 0.05) / 0.05) * 15  # 80-95
            elif center_deviation < 0.15:
                score = 65 + (1 - (center_deviation - 0.10) / 0.05) * 15  # 65-80
            elif center_deviation < 0.20:
                score = 45 + (1 - (center_deviation - 0.15) / 0.05) * 20  # 45-65
            else:
                score = max(20, 45 - (center_deviation - 0.20) * 50)  # 20-45
            
            #EDGE CASE: BLINKING DETECTION
            # Check if eyes are closed (avoid penalizing blinks)
            left_eye_top = face_landmarks.landmark[159].y
            left_eye_bottom = face_landmarks.landmark[145].y
            eye_opening = abs(left_eye_top - left_eye_bottom)
            
            # If eyes nearly closed (blinking), maintain previous score
            if eye_opening < 0.01:
                # Return current buffer average if available
                if len(self.eye_contact_buffer) > 0:
                    return float(np.mean(self.eye_contact_buffer))
                else:
                    return 70.0  # Neutral default during blink
            
            # HEAD TILT COMPENSATION 
            # If head is significantly tilted, slightly reduce confidence
            # (iris detection is less accurate at extreme angles)
            nose_tip = face_landmarks.landmark[1].x
            head_center_deviation = abs(nose_tip - 0.5)
            
            if head_center_deviation > 0.25:
                score *= 0.9  # 10% reduction for extreme head angles
            
            return round(max(20, min(100, score)), 2)
            
        except Exception as e:
            logger.warning(f"Error calculating eye contact (iris method): {e}")
            # Fallback to nose-based method
            return self._calculate_eye_contact_fallback(face_landmarks)
    
    def _calculate_eye_contact_fallback(self, face_landmarks):
        #Fallback method if iris detection fails use nose position
        
        try:
            nose_x = face_landmarks.landmark[1].x
            deviation = abs(nose_x - 0.5)
            
            if deviation < 0.08:
                return 85.0
            elif deviation < 0.15:
                return 70.0
            elif deviation < 0.25:
                return 50.0
            else:
                return 30.0
        except:
            return 50.0
    
    def _calculate_confidence_from_landmarks(self, face_landmarks, w, h):
        """Calculate confidence score from facial landmarks"""
        try:
            score = 50.0  # Base score
            
            # Eye Aspect Ratio (EAR) - measures eye openness
            left_eye_top = face_landmarks.landmark[159].y
            left_eye_bottom = face_landmarks.landmark[145].y
            left_eye_left = face_landmarks.landmark[33].x
            left_eye_right = face_landmarks.landmark[133].x
            
            left_ear = abs(left_eye_top - left_eye_bottom) / (abs(left_eye_left - left_eye_right) + 0.001)
            
            right_eye_top = face_landmarks.landmark[386].y
            right_eye_bottom = face_landmarks.landmark[374].y
            right_eye_left = face_landmarks.landmark[362].x
            right_eye_right = face_landmarks.landmark[263].x
            
            right_ear = abs(right_eye_top - right_eye_bottom) / (abs(right_eye_left - right_eye_right) + 0.001)
            
            avg_ear = (left_ear + right_ear) / 2
            
            # Well-opened eyes indicate confidence
            if avg_ear > 0.25:
                score += 20
            elif avg_ear > 0.20:
                score += 10
            elif avg_ear < 0.15:
                score -= 15
            
            # Mouth corners - smile detection
            left_mouth = face_landmarks.landmark[61].y
            right_mouth = face_landmarks.landmark[291].y
            mouth_center = face_landmarks.landmark[13].y
            
            mouth_curve = ((left_mouth + right_mouth) / 2) - mouth_center
            
            if mouth_curve < -0.01:  # Smile
                score += 15
            elif mouth_curve > 0.01:  # Frown
                score -= 10
            
            # Head pose - looking straight indicates confidence
            nose_tip = face_landmarks.landmark[1].x
            head_deviation = abs(nose_tip - 0.5)
            
            if head_deviation < 0.1:
                score += 10
            elif head_deviation > 0.2:
                score -= 10
            
            # Eyebrow position
            left_brow = face_landmarks.landmark[70].y
            left_eye_top_ref = face_landmarks.landmark[159].y
            brow_distance = left_eye_top_ref - left_brow
            
            if brow_distance > 0.03:  # Raised eyebrows
                score += 5
            
            # FIXED: Allow scores up to 100 (was 95)
            return round(max(20, min(100, score)), 2)
            
        except Exception as e:
            logger.warning(f"Error calculating confidence: {e}")
            return 50.0
    
    def _calculate_stress_from_landmarks(self, face_landmarks, w, h):
        """Calculate stress score from facial tension - FIXED VERSION (lower sensitivity)"""
        try:
            score = 15.0  # Lower base stress (was 20)
            
            # 1. Squinting detection (relaxed eyes = open)
            left_eye_top = face_landmarks.landmark[159].y
            left_eye_bottom = face_landmarks.landmark[145].y
            eye_opening = abs(left_eye_top - left_eye_bottom)
            
            # FIXED: More reasonable thresholds
            if eye_opening < 0.010:      # Extremely squinted (rare)
                score += 25
            elif eye_opening < 0.013:    # Very squinted
                score += 15
            elif eye_opening < 0.016:    # Slightly squinted
                score += 5
            # Normal eye opening (0.016+) gets no penalty
            
            # 2. Mouth tension (relaxed mouth is good)
            mouth_left = face_landmarks.landmark[61].x
            mouth_right = face_landmarks.landmark[291].x
            mouth_width = abs(mouth_right - mouth_left)
            
            # FIXED: Normal mouth width is 0.10-0.25
            if mouth_width < 0.08:       # Extremely tight (unusual)
                score += 20
            elif mouth_width < 0.10:     # Very tight
                score += 10
            elif mouth_width < 0.12:     # Slightly tight
                score += 3
            # Normal mouth width (0.12+) gets no penalty
            
            # 3. Furrowed brows (worry indicator)
            left_brow_inner = face_landmarks.landmark[70].x
            right_brow_inner = face_landmarks.landmark[300].x
            brow_distance = abs(right_brow_inner - left_brow_inner)
            
            # FIXED: Normal brow distance is 0.10-0.25
            if brow_distance < 0.08:     # Brows very close (furrowed)
                score += 15
            elif brow_distance < 0.11:   # Brows slightly close
                score += 5
            # Normal brow position gets no penalty
            
            # 4. Jaw tension (clenched teeth)
            upper_lip = face_landmarks.landmark[13].y
            lower_lip = face_landmarks.landmark[14].y
            mouth_openness = abs(upper_lip - lower_lip)
            
            # FIXED: Normal mouth openness is 0.005-0.030
            if mouth_openness < 0.003:   # Extremely tight (clenched)
                score += 15
            elif mouth_openness < 0.005: # Very tight
                score += 8
            elif mouth_openness < 0.007: # Slightly tight
                score += 3
            # Normal mouth openness gets no penalty
            
            # 5. ADDED: Smile detection (reduces stress)
            left_mouth_corner = face_landmarks.landmark[61].y
            right_mouth_corner = face_landmarks.landmark[291].y
            mouth_center = face_landmarks.landmark[13].y
            smile_curve = ((left_mouth_corner + right_mouth_corner) / 2) - mouth_center
            
            if smile_curve < -0.005:     # Smiling
                score -= 10              # Reduce stress score for smiling
            elif smile_curve < -0.010:   # Big smile
                score -= 15
            
            # Ensure score stays in valid range (10-80, not 90)
            return round(max(10, min(80, score)), 2)
            
        except Exception as e:
            logger.warning(f"Error calculating stress: {e}")
            return 25.0  # Default to low stress on error
    
    def _classify_emotion_from_scores(self, confidence, stress):
        """Classify emotion based on scores """
        
        # FIXED: Lower stress threshold for confident classification
        if confidence > 70 and stress < 45:      # Was stress < 40
            return 'confident'
        elif confidence > 60 and stress < 55:    # Was stress < 50
            return 'happy'
        elif stress > 70:                        # Was stress > 60
            return 'stressed'
        elif confidence < 50:                    # Was confidence < 45
            return 'tired'
        else:
            return 'neutral'
    
    def _aggregate_frame_analyses(self, frame_analyses):
        """Aggregate analyses from multiple frames"""
        if not frame_analyses:
            return self._get_default_analysis()
        
        # Calculate averages
        avg_confidence = float(np.mean([f['confidence_score'] for f in frame_analyses]))
        avg_stress = float(np.mean([f['stress_score'] for f in frame_analyses]))
        avg_eye_contact = float(np.mean([f['eye_contact_score'] for f in frame_analyses]))
        
        # Get dominant emotion
        emotions = [f['emotion'] for f in frame_analyses]
        emotion_counts = {}
        for emotion in emotions:
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
        dominant_emotion = max(emotion_counts, key=emotion_counts.get)
        
        # Calculate emotion percentages
        total_frames = len(frame_analyses)
        emotion_percentages = {
            emotion: round((count / total_frames) * 100, 1)
            for emotion, count in emotion_counts.items()
        }
        
        # Calculate confidence trend
        confidence_values = [f['confidence_score'] for f in frame_analyses]
        if len(confidence_values) > 10:
            first_half = np.mean(confidence_values[:len(confidence_values)//2])
            second_half = np.mean(confidence_values[len(confidence_values)//2:])
            confidence_trend = 'improving' if second_half > first_half + 5 else 'declining' if second_half < first_half - 5 else 'stable'
        else:
            confidence_trend = 'stable'
        
        # Create timeline (array format)
        emotion_timeline = []
        for frame in frame_analyses:
            emotion_timeline.append({
                'timestamp': int(frame.get('timestamp', 0)),
                'emotion': frame.get('emotion', 'neutral'),
                'confidence_score': float(frame.get('confidence_score', 50)),
                'stress_score': float(frame.get('stress_score', 50))
            })
        
        return {
            'confidence_score': round(avg_confidence, 2),
            'stress_score': round(avg_stress, 2),
            'eye_contact_score': round(avg_eye_contact, 2),
            'dominant_emotion': dominant_emotion,
            'emotion_timeline': emotion_timeline,
            'emotion_distribution': emotion_counts,
            'emotion_percentages': emotion_percentages,
            'confidence_trend': confidence_trend,
            'total_frames_analyzed': total_frames,
        }
    
    def _get_default_analysis(self):
        """Default analysis when no face detected"""
        return {
            'confidence_score': 50.0,
            'stress_score': 25.0,  # Changed from 50 to 25 (lower default)
            'eye_contact_score': 50.0,
            'dominant_emotion': 'neutral',
            'emotion_timeline': [],
            'emotion_distribution': {'neutral': 1},
            'emotion_percentages': {'neutral': 100},
            'confidence_trend': 'stable',
            'total_frames_analyzed': 0,
        }


# Singleton instance
_mediapipe_service = None

def get_mediapipe_service():
    """Get singleton instance"""
    global _mediapipe_service
    if _mediapipe_service is None:
        _mediapipe_service = MediaPipeFacialService()
    return _mediapipe_service