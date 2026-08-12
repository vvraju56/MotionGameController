import ctypes
import math
import sys
import time

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision

_user32 = ctypes.windll.user32
_prev_sens_keys = set()

_debug_handle = None


def init_log(path):
    global _debug_handle
    if path and _debug_handle is None:
        _debug_handle = open(path, "a", buffering=1)


def dbg(msg):
    print(msg, flush=True)
    if _debug_handle is not None:
        _debug_handle.write(msg + "\n")


def adjust_sensitivity_from_keys():
    global mouse_sens_x, mouse_sens_y, _prev_sens_keys
    keys = {
        "xp": (0xBB, 0x6B),
        "xm": (0xBD, 0x6A),
        "yp": (0xDD,),
        "ym": (0xDB,),
    }
    pressed = set()
    for name, vks in keys.items():
        for vk in vks:
            if _user32.GetAsyncKeyState(vk) & 0x8000:
                pressed.add(name)
                break
    for name in pressed - _prev_sens_keys:
        if name == "xp":
            mouse_sens_x = min(200, mouse_sens_x + 5)
        elif name == "xm":
            mouse_sens_x = max(1, mouse_sens_x - 5)
        elif name == "yp":
            mouse_sens_y = min(200, mouse_sens_y + 5)
        else:
            mouse_sens_y = max(1, mouse_sens_y - 5)
        dbg(f"SENS X={mouse_sens_x} Y={mouse_sens_y}")
    _prev_sens_keys = pressed

CAMERA_INDEX = 1
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
MODEL_PATH = "pose_landmarker.task"

WALK_SPEED = 0.010
RUN_SPEED = 0.030
MOVE_ALPHA = 0.35
MOVE_HYSTERESIS = 0.004

HAND_RAISE_MARGIN = 0.06
HAND_LOWER_MARGIN = -0.03
HAND_HOLD = 4

MOUSE_SENSITIVITY = 35
MOUSE_SENSITIVITY_Y = 30
MAX_MOUSE_SPEED = 60
DEAD_ZONE = 0.025
SMOOTHING = 0.35
ACCEL_POWER = 1.7
RECENTER_HOLD = 1.0

SITTING_ANGLE = 120.0
SIT_HOLD = 0.4
STAND_HOLD = 0.3

JUMP_VELOCITY = 0.3
JUMP_ALPHA = 0.6
JUMP_COOLDOWN = 0.5
JUMP_BASELINE_ALPHA = 0.1
JUMP_SUPPRESS = 1.0
SIT_EXIT_SUPPRESS = 0.8
AIR_RISE_GATE = 0.04

BASE_OPTIONS = mp_tasks.BaseOptions(model_asset_path=MODEL_PATH)
OPTIONS = vision.PoseLandmarkerOptions(
    base_options=BASE_OPTIONS,
    running_mode=vision.RunningMode.VIDEO,
    num_poses=1,
    min_pose_detection_confidence=0.5,
    min_pose_presence_confidence=0.5,
    min_tracking_confidence=0.5,
)

from game_controller import GameController
from hud import overlay_hud

pose_landmarker = vision.PoseLandmarker.create_from_options(OPTIONS)
CONNECTIONS = vision.PoseLandmarksConnections.POSE_LANDMARKS

game = GameController()

prev_center = None
jump_suppress_until = 0.0
last_space_time = 0.0

prev_hip_y = None
smooth_hip_vy = 0.0
hip_baseline = None
last_jump_time = 0.0

hand_up = False
raise_count = 0
lower_count = 0

smooth_speed = 0.0
movement_action = None

right_center = None
in_dead_zone_since = 0.0
mouse_cum_x = 0.0
mouse_cum_y = 0.0
mouse_active = False
smooth_mouse_x = 0.0
smooth_mouse_y = 0.0
mouse_sens_x = MOUSE_SENSITIVITY
mouse_sens_y = MOUSE_SENSITIVITY_Y

last_frame_time = 0.0
sitting_state = False
sit_candidate = False
sit_candidate_at = 0.0
stand_candidate = False
stand_candidate_at = 0.0
sit_exit_at = 0.0

dbg_speed = 0.0
dbg_hand_offset = 0.0
dbg_hip_vy = 0.0
dbg_air_rise = 0.0
dbg_mouse_force = (0.0, 0.0)
dbg_wrist = (0.0, 0.0)
dbg_delta = (0.0, 0.0)


def body_center(landmarks):
    l_shoulder = landmarks[vision.PoseLandmark.LEFT_SHOULDER.value]
    r_shoulder = landmarks[vision.PoseLandmark.RIGHT_SHOULDER.value]
    l_hip = landmarks[vision.PoseLandmark.LEFT_HIP.value]
    r_hip = landmarks[vision.PoseLandmark.RIGHT_HIP.value]
    cx = (l_shoulder.x + r_shoulder.x + l_hip.x + r_hip.x) / 4
    cy = (l_shoulder.y + r_shoulder.y + l_hip.y + r_hip.y) / 4
    return cx, cy


def movement_speed(cx, cy):
    global prev_center
    if prev_center is None:
        prev_center = (cx, cy)
        return 0.0
    dx = cx - prev_center[0]
    dy = cy - prev_center[1]
    prev_center = (cx, cy)
    return (dx * dx + dy * dy) ** 0.5


def detect_hand(landmarks):
    global hand_up, raise_count, lower_count, dbg_hand_offset
    wrist = landmarks[vision.PoseLandmark.LEFT_WRIST.value]
    shoulder = landmarks[vision.PoseLandmark.LEFT_SHOULDER.value]
    if min(wrist.visibility, shoulder.visibility) < 0.5:
        return hand_up
    offset = shoulder.y - wrist.y
    dbg_hand_offset = offset
    if offset > HAND_RAISE_MARGIN:
        raise_count += 1
        lower_count = 0
        if raise_count >= HAND_HOLD:
            hand_up = True
    elif offset < HAND_LOWER_MARGIN:
        raise_count = 0
        lower_count += 1
        if lower_count >= HAND_HOLD:
            hand_up = False
    else:
        raise_count = 0
        lower_count = 0
    return hand_up


def classify_move():
    global movement_action
    if movement_action == "run":
        if smooth_speed < WALK_SPEED + MOVE_HYSTERESIS:
            movement_action = None
        elif smooth_speed < RUN_SPEED * 0.7:
            movement_action = "walk"
    elif movement_action == "walk":
        if smooth_speed < WALK_SPEED - MOVE_HYSTERESIS:
            movement_action = None
        elif smooth_speed >= RUN_SPEED:
            movement_action = "run"
    else:
        if smooth_speed >= RUN_SPEED:
            movement_action = "run"
        elif smooth_speed >= WALK_SPEED:
            movement_action = "walk"
    return movement_action


def apply_mouse(landmarks, w, h, now):
    global right_center, in_dead_zone_since
    global mouse_cum_x, mouse_cum_y, mouse_active, dbg_mouse_force
    global dbg_wrist, dbg_delta, smooth_mouse_x, smooth_mouse_y

    rw = landmarks[vision.PoseLandmark.RIGHT_WRIST.value]
    ls = landmarks[vision.PoseLandmark.LEFT_SHOULDER.value]
    rs = landmarks[vision.PoseLandmark.RIGHT_SHOULDER.value]
    if min(rw.visibility, ls.visibility, rs.visibility) < 0.5 or dbg_air_rise > AIR_RISE_GATE:
        mouse_active = False
        dbg_mouse_force = (0.0, 0.0)
        dbg_delta = (0.0, 0.0)
        smooth_mouse_x = smooth_mouse_y = 0.0
        return

    s_mid = ((ls.x + rs.x) / 2, (ls.y + rs.y) / 2)
    norm_x = rw.x - s_mid[0]
    norm_y = rw.y - s_mid[1]
    dbg_wrist = (norm_x * w, norm_y * h)

    if right_center is None:
        right_center = (norm_x, norm_y)
        in_dead_zone_since = 0.0
        mouse_active = False
        dbg_mouse_force = (0.0, 0.0)
        dbg_delta = (0.0, 0.0)
        smooth_mouse_x = smooth_mouse_y = 0.0
        return

    dnx = norm_x - right_center[0]
    dny = norm_y - right_center[1]
    dbg_delta = (dnx * w, dny * h)
    dist = math.hypot(dnx, dny)

    if dist <= DEAD_ZONE:
        mouse_active = False
        dbg_mouse_force = (0.0, 0.0)
        smooth_mouse_x = smooth_mouse_y = 0.0
        if in_dead_zone_since == 0.0:
            in_dead_zone_since = now
        elif now - in_dead_zone_since > RECENTER_HOLD:
            right_center = (norm_x, norm_y)
            in_dead_zone_since = 0.0
        return

    in_dead_zone_since = 0.0
    excess = dist - DEAD_ZONE
    accel = excess ** ACCEL_POWER
    ux = dnx / dist
    uy = dny / dist

    def limit_signed(v, cap):
        return cap if v > cap else (-cap if v < -cap else v)

    speed_x = limit_signed(accel * ux * mouse_sens_x, MAX_MOUSE_SPEED)
    speed_y = limit_signed(accel * uy * mouse_sens_y, MAX_MOUSE_SPEED)

    smooth_mouse_x = SMOOTHING * speed_x + (1 - SMOOTHING) * smooth_mouse_x
    smooth_mouse_y = SMOOTHING * speed_y + (1 - SMOOTHING) * smooth_mouse_y
    mouse_active = True
    dbg_mouse_force = (smooth_mouse_x, smooth_mouse_y)

    mouse_cum_x += smooth_mouse_x
    mouse_cum_y += smooth_mouse_y
    mx = int(mouse_cum_x)
    my = int(mouse_cum_y)
    mouse_cum_x -= mx
    mouse_cum_y -= my
    if mx or my:
        game.move_mouse(mx, my)


def detect_jump(hip_y, now, dt, sitting_state):
    global prev_hip_y, smooth_hip_vy, hip_baseline, last_jump_time
    global dbg_hip_vy, dbg_air_rise

    if prev_hip_y is None:
        prev_hip_y = hip_y
        hip_baseline = hip_y
        return False

    vy = (prev_hip_y - hip_y) / dt
    prev_hip_y = hip_y
    smooth_hip_vy = JUMP_ALPHA * vy + (1 - JUMP_ALPHA) * smooth_hip_vy
    dbg_hip_vy = smooth_hip_vy

    air_rise = hip_baseline - hip_y
    dbg_air_rise = air_rise

    if sitting_state or now - sit_exit_at < SIT_EXIT_SUPPRESS:
        return False

    if smooth_hip_vy > JUMP_VELOCITY and now - last_jump_time > JUMP_COOLDOWN:
        last_jump_time = now
        print("JUMP")
        return True

    if air_rise < AIR_RISE_GATE:
        hip_baseline += JUMP_BASELINE_ALPHA * (hip_y - hip_baseline)

    return False


def angle_between(a, b, c):
    v1 = (a.x - b.x, a.y - b.y)
    v2 = (c.x - b.x, c.y - b.y)
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    m1 = math.sqrt(v1[0] ** 2 + v1[1] ** 2)
    m2 = math.sqrt(v2[0] ** 2 + v2[1] ** 2)
    if m1 == 0 or m2 == 0:
        return 180.0
    cos = max(-1.0, min(1.0, dot / (m1 * m2)))
    return math.degrees(math.acos(cos))


def detect_sitting(landmarks, now):
    global sitting_state, sit_candidate, sit_candidate_at
    global stand_candidate, stand_candidate_at, sit_exit_at

    knee_angles = []
    for side in ("LEFT", "RIGHT"):
        hip = landmarks[vision.PoseLandmark[f"{side}_HIP"].value]
        knee = landmarks[vision.PoseLandmark[f"{side}_KNEE"].value]
        ankle = landmarks[vision.PoseLandmark[f"{side}_ANKLE"].value]
        if min(hip.visibility, knee.visibility, ankle.visibility) < 0.5:
            continue
        knee_angles.append(angle_between(hip, knee, ankle))
    avg = sum(knee_angles) / len(knee_angles) if knee_angles else 180.0
    bent = avg < SITTING_ANGLE

    if bent:
        stand_candidate = False
        if not sit_candidate:
            sit_candidate = True
            sit_candidate_at = now
        elif not sitting_state and now - sit_candidate_at > SIT_HOLD:
            sitting_state = True
            print("SITTING")
    else:
        sit_candidate = False
        if not stand_candidate:
            stand_candidate = True
            stand_candidate_at = now
        elif sitting_state and now - stand_candidate_at > STAND_HOLD:
            sitting_state = False
            sit_exit_at = now
            print("STANDING")

    return sitting_state, avg


def draw_part(frame, landmarks, name, h, w):
    lm = landmarks[vision.PoseLandmark[name].value]
    x, y = int(lm.x * w), int(lm.y * h)
    cv2.circle(frame, (x, y), 6, (0, 255, 0), -1)
    cv2.putText(frame, name, (x + 8, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)


def draw_skeleton(frame, landmarks, h, w):
    for connection in CONNECTIONS:
        a = landmarks[connection.start]
        b = landmarks[connection.end]
        cv2.line(
            frame,
            (int(a.x * w), int(a.y * h)),
            (int(b.x * w), int(b.y * h)),
            (0, 255, 255),
            2,
        )


def main():
    global jump_suppress_until, last_frame_time, hand_up
    global movement_action, smooth_speed, last_space_time
    global right_center, in_dead_zone_since, mouse_active, dbg_mouse_force
    global dbg_wrist, dbg_delta, mouse_sens_x, mouse_sens_y, smooth_mouse_x, smooth_mouse_y

    test_mode = "--test" in sys.argv
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--log" and i + 1 < len(sys.argv[1:]):
            init_log(sys.argv[i + 2])
    dbg(f"=== MOTION GAME CONTROLLER START (test_mode={test_mode}) ===")

    camera = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

    for _ in range(10):
        camera.read()

    if not camera.isOpened():
        print("Camera not found")
        return

    start_time = time.time()
    last_frame_time = time.time()

    while True:
        adjust_sensitivity_from_keys()

        success, frame = camera.read()
        if not success:
            print("Camera not found")
            break

        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        timestamp = int((time.time() - start_time) * 1000)
        result = pose_landmarker.detect_for_video(mp_image, timestamp)

        if result.pose_landmarks:
            landmarks = result.pose_landmarks[0]

            draw_skeleton(frame, landmarks, h, w)

            for name in [
                "NOSE",
                "LEFT_SHOULDER",
                "RIGHT_SHOULDER",
                "LEFT_ELBOW",
                "RIGHT_ELBOW",
                "LEFT_WRIST",
                "RIGHT_WRIST",
                "LEFT_HIP",
                "RIGHT_HIP",
                "LEFT_KNEE",
                "RIGHT_KNEE",
                "LEFT_ANKLE",
                "RIGHT_ANKLE",
            ]:
                draw_part(frame, landmarks, name, h, w)

            cx, cy = body_center(landmarks)
            speed = movement_speed(cx, cy)

            now = time.time()
            dt = now - last_frame_time
            last_frame_time = now
            if dt <= 0.0 or dt > 0.25:
                dt = 1.0 / 30.0

            hand_up = detect_hand(landmarks)

            if hand_up:
                smooth_speed = MOVE_ALPHA * speed + (1 - MOVE_ALPHA) * smooth_speed
            else:
                smooth_speed = 0.0
                movement_action = None
            dbg_speed = smooth_speed

            action = classify_move() if hand_up else None

            dbg(f"LeftHand={hand_up} | Movement={smooth_speed:.3f} | Raw={speed:.3f} | Action={action or 'NONE'}")

            if action == "walk":
                game.hold("w")
                game.release("shift")
            elif action == "run":
                game.hold("w")
                game.hold("shift")
            else:
                game.release("w")
                game.release("shift")

            l_hip = landmarks[vision.PoseLandmark.LEFT_HIP.value].y
            r_hip = landmarks[vision.PoseLandmark.RIGHT_HIP.value].y
            hip_y = (l_hip + r_hip) / 2

            jumping = detect_jump(hip_y, now, dt, sitting_state)
            if jumping:
                jump_suppress_until = now + JUMP_SUPPRESS
                last_space_time = now
                game.tap("space")

            sitting, knee_angle = detect_sitting(landmarks, now)
            if sitting:
                game.hold("ctrl")
            else:
                game.release("ctrl")

            apply_mouse(landmarks, w, h, now)

            dpx, dpy = dbg_delta
            if mouse_active:
                if abs(dpx) >= abs(dpy):
                    direction = "-> RIGHT" if dpx > 0 else "<- LEFT"
                else:
                    direction = "^ UP" if dpy < 0 else "v DOWN"
            else:
                direction = "CENTER"

            cv2.putText(
                frame,
                f"body center x: {cx*100:.1f}%  y: {cy*100:.1f}%",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 0, 0),
                2,
            )
            cv2.putText(
                frame,
                f"left hand: {('RAISED' if hand_up else 'LOWERED'):<8} offset:{dbg_hand_offset:+.2f}",
                (10, 55),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 255) if hand_up else (255, 0, 0),
                1,
            )
            cv2.putText(
                frame,
                f"action: {action or 'IDLE':<10} smooth speed:{dbg_speed:.3f}",
                (10, 75),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 255) if action else (255, 0, 0),
                1,
            )
            cv2.putText(
                frame,
                f"(walk>{WALK_SPEED} run>{RUN_SPEED})",
                (10, 95),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (160, 160, 160),
                1,
            )
            cv2.putText(
                frame,
                f"knee angle: {knee_angle:.0f} deg  hip vy:{dbg_hip_vy:.2f}/s  air:{dbg_air_rise:.3f}",
                (10, 115),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 0, 0),
                1,
            )
            if sitting:
                cv2.putText(
                    frame,
                    "SITTING",
                    (10, 140),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (0, 0, 255),
                    2,
                )
            cv2.putText(
                frame,
                f"mouse fx:{dbg_mouse_force[0]:+5.1f} fy:{dbg_mouse_force[1]:+5.1f} dx:{dpx:+.0f} dy:{dpy:+.0f} {direction}",
                (10, 165),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 200, 0) if mouse_active else (255, 0, 0),
                1,
            )
            cv2.putText(
                frame,
                f"SENS X: {mouse_sens_x}  Y: {mouse_sens_y}  (keys: -= X | [] Y)",
                (10, 185),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (160, 160, 160),
                1,
            )

            center_x = int(cx * w)
            center_y = int(cy * h)
            cv2.circle(frame, (center_x, center_y), 5, (0, 0, 255), -1)
            cv2.line(frame, (center_x, 0), (center_x, h), (0, 0, 255), 1)
            cv2.line(frame, (0, center_y), (w, center_y), (0, 0, 255), 1)
            hud_state = {
                "camera": True,
                "tracking": True,
                "left_hand": hand_up,
                "action": action,
                "wrist": dbg_wrist,
                "delta": dbg_delta,
                "direction": direction,
                "sensitivity": mouse_sens_x,
                "sensitivity_y": mouse_sens_y,
                "keys": {
                    "w": action in ("walk", "run"),
                    "shift": action == "run",
                    "ctrl": sitting,
                    "space": (now - last_space_time) < 0.25,
                    "mouse": mouse_active,
                },
            }
        else:
            game.release_all()
            hand_up = False
            movement_action = None
            smooth_speed = 0.0
            right_center = None
            in_dead_zone_since = 0.0
            mouse_active = False
            dbg_mouse_force = (0.0, 0.0)
            dbg_wrist = (0.0, 0.0)
            dbg_delta = (0.0, 0.0)
            smooth_mouse_x = smooth_mouse_y = 0.0
            hud_state = {
                "camera": True,
                "tracking": False,
                "left_hand": False,
                "action": None,
                "wrist": (0.0, 0.0),
                "delta": (0.0, 0.0),
                "direction": "CENTER",
                "sensitivity": mouse_sens_x,
                "sensitivity_y": mouse_sens_y,
                "keys": {
                    "w": False,
                    "shift": False,
                    "ctrl": False,
                    "space": False,
                    "mouse": False,
                },
            }
            cv2.putText(
                frame,
                "No body detected",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2,
            )

        frame = overlay_hud(frame, hud_state, test_mode)

        cv2.imshow("Motion Controller Camera", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("-") or key == ord("_"):
            mouse_sens_x = max(1, mouse_sens_x - 5)
            dbg(f"SENS X = {mouse_sens_x} | Y = {mouse_sens_y}")
        elif key == ord("=") or key == ord("+"):
            mouse_sens_x = min(200, mouse_sens_x + 5)
            dbg(f"SENS X = {mouse_sens_x} | Y = {mouse_sens_y}")
        elif key == ord("["):
            mouse_sens_y = max(1, mouse_sens_y - 5)
            dbg(f"SENS X = {mouse_sens_x} | Y = {mouse_sens_y}")
        elif key == ord("]"):
            mouse_sens_y = min(200, mouse_sens_y + 5)
            dbg(f"SENS X = {mouse_sens_x} | Y = {mouse_sens_y}")

    camera.release()
    game.release_all()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()