import matplotlib.pyplot as plt
from scipy.signal import find_peaks, savgol_filter
import cv2
import numpy as np

# 1. Open the video file
video = cv2.VideoCapture("worm_video.MOV")  # replace with your video file

# 2. This will store the worm head's angle to its own body in every frame
angles = []

# Remembers where the head was in the last frame so we don't lose track of it when the worm reverses
previous_head = None

frame_number = 0

def get_end_points(contour):
    """Find the two points farthest apart, using only the outer hull for speed."""
    hull = cv2.convexHull(contour)
    points = hull.reshape(-1, 2)

    max_dist = 0
    end1, end2 = points[0], points[0]

    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            dist = np.linalg.norm(points[i] - points[j])
            if dist > max_dist:
                max_dist = dist
                end1, end2 = points[i], points[j]

    return end1, end2

def touches_edge(contour, frame_shape, margin=5):
    """True if any part of the contour is near the frame's border."""
    x, y, w, h = cv2.boundingRect(contour)
    height, width = frame_shape[:2]
    return (x <= margin or y <= margin or
            x + w >= width - margin or y + h >= height - margin)

# 3. Go through the video one frame at a time
while True:
    success, frame = video.read()
    if not success:
        break  # no more frames — video is over
    frame = frame[3:1070, 463:1492]
    
    # Turn the frame black-and-white (easier to work with)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (25, 25), 0)

    # Turn it into pure black/white so the worm stands out from the background
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, blockSize=51, C=5)
  
    # Find the outline (contour) of the worm blob
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    possible_worms = [c for c in contours if 200 < cv2.contourArea(c) < 5000]

    if possible_worms:
        worm = max(possible_worms, key=cv2.contourArea)

        if touches_edge(worm, frame.shape):
            print(f"Worm reached frame edge at frame {frame_number} — stopping data collection.")
            break
        M = cv2.moments(worm)
        if M["m00"] != 0:
            center = np.array([M["m10"] / M["m00"], M["m01"] / M["m00"]]) 
            end1, end2 = get_end_points(worm)

            # Determine which end is the head (closest to the previous head position)
            if previous_head is None:
                # first frame: just pick one arbitrarily as a starting guess
                head = end1
            else:
                # whichever end is CLOSER to last frame's head, call that the head
                if np.linalg.norm(end1 - previous_head) < np.linalg.norm(end2 - previous_head):
                    head = end1
                else:
                    head = end2

            previous_head = head

            # "neck" = average position of the outline points near the head
            points = worm.reshape(-1, 2)
            near_head = points[np.linalg.norm(points - head, axis=1) < 40]
            neck = near_head.mean(axis=0)

            vector = head - neck
            angle = np.arctan2(vector[1], vector[0])
            angles.append(angle)
            
    frame_number += 1

fps = video.get(cv2.CAP_PROP_FPS)
video.release()

 # 4. Clean up the angle signal
angles = np.unwrap(np.array(angles))   # removes the fake jumps at +/- pi
window = min(151, len(angles) - 1)
if window % 2 == 0:
    window -= 1
trend = savgol_filter(angles, window_length=window, polyorder=2)   # slow turning of the whole worm
swing = angles - trend                                          # what's left is the head swinging
smoothed = savgol_filter(swing, window_length=15, polyorder=2)

print("Frames in video:", frame_number)
print("Frames where worm was found:", len(angles))
print("fps:", fps)

# 5. Count peaks and troughs, ignoring tiny wiggles
min_size = 0.5 * np.std(smoothed)
min_distance = 10  # minimum frames between separate bends
peaks, _ = find_peaks(smoothed, prominence=min_size, distance=min_distance)
troughs, _ = find_peaks(-smoothed, prominence=min_size, distance=min_distance)
total_bends = (len(peaks) + len(troughs)) / 2

# 6. Bends per minute
video_length_seconds = len(angles) / fps
print("Total peaks + troughs:", total_bends)
print("Bends per minute:", total_bends / (video_length_seconds / 60))

# 7. Plot raw vs smoothed
plt.plot(swing, alpha=0.4, label="raw")
plt.plot(smoothed, label="smoothed")
plt.plot(peaks, smoothed[peaks], "ro")
plt.plot(troughs, smoothed[troughs], "go")
plt.xlabel("Frame")
plt.ylabel("Head angle")
plt.legend()
plt.show()




