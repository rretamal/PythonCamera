import cv2
import mediapipe as mp
from onvif import ONVIFCamera
from imutils.video import VideoStream
import time

# Setup ONVIF camera
cam = object()
ptz_service = object()

def check_onvif_support():
    global cam
    global ptz_service
    
    try:
        cam = ONVIFCamera('192.168.100.25', 554, '', '')
        ptz_service = cam.create_ptz_service()
    except Exception as ex:
         print(f"Failed to perform PTZ operation: {ex}")

    pass

onvif_supported = False #check_onvif_support()



# Setup OpenCV and MediaPipe
url = 'rtsp://192.168.100.25:554/onvif1?transport=tcp'
cap = cv2.VideoCapture('rtsp://192.168.100.25:554/onvif1?transport=tcp', cv2.CAP_FFMPEG)

time.sleep(10.0)

mp_hands = mp.solutions.hands
hands = mp_hands.Hands()

def perform_ptz(pan, tilt, zoom):    

    # Create an ONVIF PTZ request object
    request = ptz_service.create_type('AbsoluteMove')
    
    # Assign the provided PTZ values to the request object.
    # The actual field names and structure may vary based on your camera's ONVIF API.
    request.Position.PanTilt.x = pan
    request.Position.PanTilt.y = tilt
    request.Position.Zoom.x = zoom
    
    # Obtain the media profile token of your camera.
    # This is required to identify which camera configuration you are controlling.
    request.ProfileToken = cam.media_profile.token
    
    # Send the PTZ command to the camera.
    ptz_service.AbsoluteMove(request)

def calculate_hand_center(hand_landmarks):
    total_x, total_y = 0, 0
    num_landmarks = len(hand_landmarks.landmark)
    for landmark in hand_landmarks.landmark:
        total_x += landmark.x
        total_y += landmark.y
    return total_x / num_landmarks, total_y / num_landmarks  # Return average x, y coordinates

ptz_scale_factor = 0.1  # You may need to adjust this value based on experimentation

while cap.isOpened():
    try: 
        ret, frame = cap.read()
        if not ret:
            print('Failed to grab frame.')
            break
        
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb_frame)
        
        cv2.imshow('Camera Frame', frame)  # Display the frame in a window named 'Camera Frame'
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        if result.multi_hand_landmarks and onvif_supported:
            hand_landmarks = result.multi_hand_landmarks[0]
            hand_center_x, hand_center_y = calculate_hand_center(hand_landmarks)
            
            frame_height, frame_width, _ = frame.shape
            frame_center_x = frame_width // 2
            frame_center_y = frame_height // 2
            
            delta_x = hand_center_x - frame_center_x
            delta_y = hand_center_y - frame_center_y
            
            pan_value = delta_x * ptz_scale_factor
            tilt_value = delta_y * ptz_scale_factor
            
            perform_ptz(pan_value, tilt_value, 0)  # Assuming no zoom change
    except Exception as ex:
         print(f"Problem processing frame: {ex}")

cap.release()  # Release the camera resource
cv2.destroyAllWindows()  # Destroy all OpenCV windows