import cv2


class Camera:

    def __init__(self, camera_id=0):

        self.cap = cv2.VideoCapture(camera_id)

        if not self.cap.isOpened():
            raise RuntimeError("Cannot open camera")

        # Set lower resolution for faster processing
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

    def read(self):

        ret, frame = self.cap.read()

        if not ret:
            return None

        frame = cv2.flip(frame, 1)

        return frame

    def release(self):

        self.cap.release()