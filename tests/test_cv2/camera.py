import cv2

def list_cameras(max_tested=10):
    available_cameras = []
    for i in range(max_tested):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)  # Try to open the camera
        if cap.isOpened():  # Check whether the camera opened successfully
            available_cameras.append(i)
            cap.release()  # Release the camera
        else:
            break  # If one camera index cannot be opened, assume the following ones are unavailable too
    return available_cameras

def capture_image(camera_index=0):
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    
    if not cap.isOpened():
        print(f"Cannot open camera {camera_index}")
        return None

    ret, frame = cap.read()  # Read one image frame
    if not ret:
        print("Can't receive frame (stream end?). Exiting ...")
        return None
    cap.release()  # Release the camera
    return frame

# List all cameras
cameras = list_cameras()
print("Available cameras:", cameras)

# If a camera is available, capture a screenshot from the first one
if cameras:
    frame = capture_image(cameras[0])
    if frame is not None:
        cv2.imshow('Capture', frame)
        cv2.waitKey(0)  # Wait for a key press
        cv2.destroyAllWindows()
