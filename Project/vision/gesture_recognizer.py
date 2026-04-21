from utils.smoothing import EMASmoother
import math


class GestureRecognizer:

    def __init__(self):
        self.finger_smoother_x = EMASmoother(alpha=0.5)
        self.finger_smoother_y = EMASmoother(alpha=0.5)
        self.last_action = "IDLE"

    def predict(self, landmarks):
        if landmarks is None:
            self.last_action = "IDLE"
            return "IDLE"

        l = landmarks.landmark

        # Wrist (0) and index fingertip (8)
        wrist_x = l[0].x
        wrist_y = l[0].y
        fingertip_x = l[8].x
        fingertip_y = l[8].y

        # Vector from wrist to fingertip
        dx = fingertip_x - wrist_x
        dy = fingertip_y - wrist_y

        # Smooth the differences
        smoothed_dx = self.finger_smoother_x.update(dx)
        smoothed_dy = self.finger_smoother_y.update(dy)

        # Calculate angle (in degrees)
        angle = math.atan2(-smoothed_dy, smoothed_dx) * 180 / math.pi

        # Minimum vector length to trigger (fist = idle)
        vector_length = math.sqrt(smoothed_dx ** 2 + smoothed_dy ** 2)
        if vector_length < 0.1:
            self.last_action = "IDLE"
            return "IDLE"

        # Determine action based on angle: LEFT / RIGHT / JUMP / IDLE
        new_action = "IDLE"
        if abs(angle) <= 45:
            new_action = "RIGHT"
        elif 45 < angle <= 135:
            new_action = "JUMP"
        elif -135 <= angle < -45:
            new_action = "IDLE"
        else:
            new_action = "LEFT"

        if new_action != self.last_action:
            self.last_action = new_action
            return new_action
        return self.last_action
