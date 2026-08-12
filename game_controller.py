import pyautogui

pyautogui.PAUSE = 0.01


class GameController:
    def __init__(self):
        self.held = set()

    def hold(self, name):
        if name not in self.held:
            self.held.add(name)
            pyautogui.keyDown(name)

    def release(self, name):
        if name in self.held:
            self.held.discard(name)
            pyautogui.keyUp(name)

    def tap(self, name, interval=0.05):
        pyautogui.keyDown(name)
        pyautogui.sleep(interval)
        pyautogui.keyUp(name)
        self.held.discard(name)

    def move_mouse(self, dx, dy):
        if dx or dy:
            pyautogui.moveRel(dx, dy)

    def release_all(self):
        for name in list(self.held):
            self.release(name)