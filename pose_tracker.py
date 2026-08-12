import cv2
import mediapipe as mp


class PoseTracker:
    def __init__(self, config):
        self.config = config
        self.mp_pose = mp.solutions.pose
        self.mp_draw = mp.solutions.drawing_utils
        self.pose = self.mp_pose.Pose(
            model_complexity=config["POSE_MODEL_COMPLEXITY"],
            min_detection_confidence=config["MIN_DETECTION_CONFIDENCE"],
            min_tracking_confidence=config["MIN_TRACKING_CONFIDENCE"],
        )

    def process(self, frame):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(frame_rgb)
        landmarks = results.pose_landmarks
        return landmarks, results

    def draw(self, frame, results):
        if results.pose_landmarks:
            self.mp_draw.draw_landmarks(
                frame,
                results.pose_landmarks,
                self.mp_pose.POSE_CONNECTIONS,
            )
        return frame

    def get_landmark(self, landmarks, name):
        index = self.mp_pose.PoseLandmark[name].value
        return landmarks.landmark[index]
