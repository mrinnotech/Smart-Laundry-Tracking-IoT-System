import serial
import cv2
import time
import mediapipe as mp
import json
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

# ----------------------------------------------------------
# 1️⃣ Google Drive Authentication
# ----------------------------------------------------------
gauth = GoogleAuth()
gauth.LocalWebserverAuth()
drive = GoogleDrive(gauth)

# ----------------------------------------------------------
# 2️⃣ Google Drive Folder ID
# ----------------------------------------------------------
FOLDER_ID = "1LE5emx7gzrbfjUe8jM9Onx2bu_T6o2SE"

# ----------------------------------------------------------
# 3️⃣ Serial Port Configuration
# ----------------------------------------------------------
ser = serial.Serial('COM9', 115200, timeout=1)

# ----------------------------------------------------------
# 4️⃣ Authorized RFID Card UIDs
# ----------------------------------------------------------
AUTHORIZED_UIDS = [
    "79 FC 77 5A",
    "53 21 04 05",
    "89 7A E9 49"
]

print("🎯 Listening for RFID UIDs...")

# ----------------------------------------------------------
# 5️⃣ Initialize MediaPipe Pose
# ----------------------------------------------------------
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

# ----------------------------------------------------------
# 6️⃣ Main Loop - RFID + Pose Detection + Upload
# ----------------------------------------------------------
while True:
    line = ser.readline().decode('utf-8').strip()

    if "Card UID:" in line:
        uid = line.split("Card UID:")[1].strip()
        print(f"Detected Tag ID: {uid}")

        if uid in AUTHORIZED_UIDS:
            print("✅ Authorized Tag Detected! Starting recording for 30 seconds...")

            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                print("❌ Error: Cannot access webcam.")
                continue

            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"rack_record_{timestamp}.mp4"
            out = cv2.VideoWriter(filename, fourcc, 20.0, (640, 480))
            start_time = time.time()

            rack_level = None
            box_number = None

            # ---------- Accuracy boost buffers ----------
            smooth_x = []
            smooth_y = []
            WINDOW = 10              # smoothing window size
            CONFIRM_FRAMES = 5        # number of frames to confirm result
            level_history = []
            box_history = []

            def smooth(values):
                return sum(values) / len(values)

            with mp_pose.Pose(
                static_image_mode=False,
                model_complexity=0,
                min_detection_confidence=0.7,
                min_tracking_confidence=0.7
            ) as pose:

                while (time.time() - start_time) < 30:
                    ret, frame = cap.read()
                    if not ret:
                        break

                    frame = cv2.flip(frame, 1)
                    h, w, _ = frame.shape

                    # ---------------- Horizontal Lines ----------------
                    line_bottom = int(h * 0.88)
                    line_middle = int(h * 0.65)
                    line_top = int(h * 0.40)

                    cv2.line(frame, (0, line_bottom), (w, line_bottom), (0, 255, 0), 2)
                    cv2.line(frame, (0, line_middle), (w, line_middle), (255, 255, 0), 2)
                    cv2.line(frame, (0, line_top), (w, line_top), (0, 0, 255), 2)

                    # ---------------- Vertical Lines ----------------
                    line_left = int(w * 0.33)
                    line_right = int(w * 0.66)

                    cv2.line(frame, (line_left, 0), (line_left, h), (255, 0, 255), 2)
                    cv2.line(frame, (line_right, 0), (line_right, h), (255, 150, 0), 2)

                    # ---------------- Logic Functions ----------------
                    def get_level(y):
                        if y < line_top:
                            return 2
                        elif y < line_middle:
                            return 1
                        else:
                            return 0

                    def get_box(x):
                        margin = 20  # boundary stability margin
                        if x < line_left - margin:
                            return 0
                        elif x > line_right + margin:
                            return 2
                        else:
                            return 1

                    # Convert to RGB for MediaPipe
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = pose.process(rgb)

                    if results.pose_landmarks:
                        wrist = results.pose_landmarks.landmark[mp_pose.PoseLandmark.RIGHT_WRIST]

                        if wrist.visibility > 0.75:  # require strong confidence
                            raw_x = int(wrist.x * w)
                            raw_y = int(wrist.y * h)

                            # Save values for smoothing
                            smooth_x.append(raw_x)
                            smooth_y.append(raw_y)

                            # Limit buffer size
                            if len(smooth_x) > WINDOW:
                                smooth_x.pop(0)
                                smooth_y.pop(0)

                            x = int(smooth(smooth_x))
                            y = int(smooth(smooth_y))

                            cv2.circle(frame, (x, y), 10, (0, 255, 255), -1)

                            level = get_level(y)
                            box = get_box(x)

                            # Add to history for confirmation
                            level_history.append(level)
                            box_history.append(box)

                            if len(level_history) > CONFIRM_FRAMES:
                                level_history.pop(0)
                                box_history.pop(0)

                            # Confirm when stable for 5 frames
                            if level_history.count(level_history[-1]) == CONFIRM_FRAMES:
                                rack_level = level_history[-1]

                            if box_history.count(box_history[-1]) == CONFIRM_FRAMES:
                                box_number = box_history[-1]

                            # Display text
                            cv2.putText(frame,
                                        f"Rack Level: {rack_level} + Box {box_number}",
                                        (50, 50),
                                        cv2.FONT_HERSHEY_SIMPLEX,
                                        1.1, (0, 255, 0), 3)

                            print(f"[{time.strftime('%H:%M:%S')}] Rack Level: {rack_level} + Box {box_number}")

                    out.write(frame)
                    cv2.imshow("Rack Level Detection (Press 'q' to stop)", frame)

                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        print("⏹️ Stopped manually.")
                        break

            cap.release()
            out.release()
            cv2.destroyAllWindows()
            print(f"🎥 Recording complete! Saved as: {filename}")

            # ----------------------------------------------------------
            # 7️⃣ Metadata JSON
            # ----------------------------------------------------------
            metadata = {
                "Tag_ID": uid,
                "Rack_Level": rack_level if rack_level is not None else "Unknown",
                "Box_Number": box_number if box_number is not None else "Unknown",
                "Timestamp": timestamp,
                "Video_File": filename
            }

            meta_filename = f"metadata_{timestamp}.json"
            with open(meta_filename, "w") as f:
                json.dump(metadata, f, indent=4)

            # ----------------------------------------------------------
            # 8️⃣ Upload to Google Drive
            # ----------------------------------------------------------
            print("☁️ Uploading video and metadata to Google Drive folder...")

            # Upload video
            video_file = drive.CreateFile({
                'title': filename,
                'parents': [{'id': FOLDER_ID}]
            })
            video_file.SetContentFile(filename)
            video_file.Upload()
            print(f"✅ Video uploaded: {video_file['title']}")

            # Upload metadata
            meta_file = drive.CreateFile({
                'title': meta_filename,
                'parents': [{'id': FOLDER_ID}]
            })
            meta_file.SetContentFile(meta_filename)
            meta_file.Upload()
            print(f"✅ Metadata uploaded: {meta_file['title']}")

            print("📦 Upload complete!\n")

        else:
            print("🚫 Unauthorized Tag detected.")
