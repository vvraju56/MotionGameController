# Motion Game Controller

Control your PC games with your body using only a webcam — no extra hardware.
MediaPipe pose landmarks turn hand gestures, body motion, sitting and jumping
into keyboard + mouse input.

## How it works

| Your action | Game control |
| --- | --- |
| ✋ Raise left hand | Enable movement |
| ✋ Left hand raised + normal body movement | `W` (walk) |
| ✋ Left hand raised + fast body movement | `SHIFT + W` (run) |
| 🪑 Sit / squat | `CTRL` |
| 🦘 Jump | `SPACE` |
| ✋ Lower left hand | Stop movement |
| 🤚 Move right hand off center | Move mouse cursor (camera look) |

> The left hand is only an **enable/disable switch** for movement. Walking vs
> running is decided by your smoothed body-center speed, not the hand. The right
> hand is a **touchpad-style joystick** for the mouse: distance from the
> calibrated center sets speed, with a dead zone in the middle.

## Requirements

- Windows
- Python 3.9+
- A webcam

## Installation

```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Run it:

```cmd
python main.py
```

> If you use a different camera than index `1`, change `CAMERA_INDEX` at the top
> of `main.py`.

## Live HUD

The camera window shows a live status panel (hand state, current action, and
which keys are pressed) plus a "HOW TO CONTROL" guide. Run in **test mode** to
verify every control before risking it in a real game:

```cmd
python main.py --test
```

Test mode shows a dedicated panel with per-key `DOWN`/`UP` indicators and a
`RIGHT HAND` readout (`RIGHT X/Y`, `DX/DY` in px, direction) so you can confirm
detection before giving it control of the game.

## Tuning

The right-hand mouse uses a nonlinear acceleration curve from the hand's
distance past a dead zone. Defaults live at the top of `main.py`:

| Constant | Default | Meaning |
| --- | --- | --- |
| `MOUSE_SENSITIVITY` / `MOUSE_SENSITIVITY_Y` | `35` / `30` | gain for X / Y |
| `MAX_MOUSE_SPEED` | `60` | cap, px/frame |
| `DEAD_ZONE` | `0.025` | normalized dead zone around center |
| `SMOOTHING` | `0.35` | velocity smoothing (0–1) |
| `ACCEL_POWER` | `1.7` | acceleration curve exponent |
| `WALK_SPEED` / `RUN_SPEED` | `0.010` / `0.030` | smoothed speed thresholds |

Adjust sensitivity **live** while the app runs (works even when the camera
window does not have focus):

| Key | Effect |
| --- | --- |
| `-` / `=` | X sensitivity down / up |
| `[` / `]` | Y sensitivity down / up |
| `q` | quit |

Press `q` in the camera window to exit.

## Project structure

```text
MotionGameController/
├── main.py             # camera loop, pose detection, control logic
├── hud.py              # Pillow-rendered status/test panels
├── game_controller.py  # pyautogui keyboard + mouse output
├── config.py           # optional config (legacy)
├── pose_tracker.py     # legacy MediaPipe wrapper
├── pose_landmarker.task # MediaPipe pose landmarker model
└── requirements.txt
```