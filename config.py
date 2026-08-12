CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30

FULLSCREEN = False
FPS_LIMIT = 30

POSE_MODEL_COMPLEXITY = 1
MIN_DETECTION_CONFIDENCE = 0.5
MIN_TRACKING_CONFIDENCE = 0.5

GESTURE_COOLDOWN = 0.5
SWIPE_THRESHOLD = 0.3
SWIPE_TIME = 0.5

CONTROLS = {
    "walk": {
        "type": "hold",
        "keys": ["w"],
        "enabled": True,
    },
    "run": {
        "type": "hold",
        "keys": ["shift", "w"],
        "enabled": True,
    },
    "sit": {
        "type": "hold",
        "keys": ["ctrl"],
        "enabled": True,
    },
    "jump": {
        "type": "tap",
        "keys": ["space"],
        "enabled": True,
    },
}

DEBUG = True
