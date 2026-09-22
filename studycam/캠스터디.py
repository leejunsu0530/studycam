import cv2
import os
import time
from datetime import datetime

# =========================
# 설정
# =========================

CAMERA_INDEX = 0

# 몇 초마다 사진을 찍을지
CAPTURE_INTERVAL = 10

# 총 촬영 시간 (분)
STUDY_DURATION_MINUTES = 60

# 결과 영상 FPS
VIDEO_FPS = 30

# 저장 폴더
PHOTO_DIR = "study_photos"

# 결과 영상 파일
OUTPUT_VIDEO = "study_timelapse.mp4"


# =========================
# 초기 설정
# =========================

os.makedirs(PHOTO_DIR, exist_ok=True)

cap = cv2.VideoCapture(CAMERA_INDEX)

if not cap.isOpened():
    raise RuntimeError("카메라를 열 수 없습니다.")

study_seconds = STUDY_DURATION_MINUTES * 60

start_time = time.time()
last_capture_time = start_time - CAPTURE_INTERVAL

photo_paths = []

print("캠 스터디 촬영 시작")
print(f"촬영 간격: {CAPTURE_INTERVAL}초")
print(f"총 촬영 시간: {STUDY_DURATION_MINUTES}분")
print("ESC 키를 누르면 조기 종료됩니다.")


# =========================
# 사진 촬영
# =========================

while True:
    ret, frame = cap.read()

    if not ret:
        print("카메라 프레임을 읽지 못했습니다.")
        break

    current_time = time.time()
    elapsed = current_time - start_time

    # 현재 화면 표시
    remaining = max(0, study_seconds - elapsed)

    text = (
        f"Study: {int(elapsed // 60):02d}:"
        f"{int(elapsed % 60):02d}"
        f" / {STUDY_DURATION_MINUTES}:00"
    )

    preview = frame.copy()

    cv2.putText(
        preview,
        text,
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 0),
        2
    )

    cv2.imshow("Cam Study", preview)

    # 지정된 시간마다 사진 저장
    if current_time - last_capture_time >= CAPTURE_INTERVAL:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        filename = os.path.join(
            PHOTO_DIR,
            f"{len(photo_paths):06d}_{timestamp}.jpg"
        )

        cv2.imwrite(filename, frame)
        photo_paths.append(filename)

        print(f"[{len(photo_paths)}] 사진 저장: {filename}")

        last_capture_time = current_time

    # 정해진 시간 종료
    if elapsed >= study_seconds:
        print("설정된 공부 시간이 끝났습니다.")
        break

    # ESC 키
    key = cv2.waitKey(1) & 0xFF
    if key == 27:
        print("사용자가 촬영을 종료했습니다.")
        break


cap.release()
cv2.destroyAllWindows()


# =========================
# 영상 생성
# =========================

if not photo_paths:
    print("촬영된 사진이 없어 영상을 만들 수 없습니다.")
    exit()

first_frame = cv2.imread(photo_paths[0])

height, width = first_frame.shape[:2]

fourcc = cv2.VideoWriter_fourcc(*"mp4v")

video_writer = cv2.VideoWriter(
    OUTPUT_VIDEO,
    fourcc,
    VIDEO_FPS,
    (width, height)
)

for path in photo_paths:
    image = cv2.imread(path)

    if image is None:
        continue

    # 혹시 크기가 다르면 맞춤
    if image.shape[1] != width or image.shape[0] != height:
        image = cv2.resize(image, (width, height))

    video_writer.write(image)

video_writer.release()

print()
print("완료!")
print(f"촬영 사진 수: {len(photo_paths)}장")
print(f"영상 저장 위치: {OUTPUT_VIDEO}")