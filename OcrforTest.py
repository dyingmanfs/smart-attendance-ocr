import cv2
import pytesseract
import re
import numpy as np
import time
import subprocess
import RPi.GPIO as GPIO
from datetime import datetime
import os
import csv
import checker
# GPIO Setup
BUTTON_PIN = 17  # Change this to your actual GPIO pin number
LED_RED = 22
LED_GREEN = 23
LED_BLUE = 24

GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Setup LED pins as outputs with PWM (software dimming, no resistors needed)
GPIO.setup(LED_RED, GPIO.OUT)
GPIO.setup(LED_GREEN, GPIO.OUT)
GPIO.setup(LED_BLUE, GPIO.OUT)

# Create PWM objects (100Hz frequency, 30% duty cycle for safety)
pwm_red = GPIO.PWM(LED_RED, 100)
pwm_green = GPIO.PWM(LED_GREEN, 100)
pwm_blue = GPIO.PWM(LED_BLUE, 100)

# Start PWM at 0% (off)
pwm_red.start(0)
pwm_green.start(0)
pwm_blue.start(0)

# Output directory
OUTPUT_DIR = "/home/pi/id_scans"  # Change this path as needed
os.makedirs(OUTPUT_DIR, exist_ok=True)


def set_led_color(red=False, green=False, blue=False):
    """Control RGB LED colors with PWM (30% brightness for safety without resistors)"""
    pwm_red.ChangeDutyCycle(30 if red else 0)
    pwm_green.ChangeDutyCycle(30 if green else 0)
    pwm_blue.ChangeDutyCycle(30 if blue else 0)


def led_off():
    """Turn off all LED colors"""
    set_led_color(False, False, False)

colorBlue = False
colorRed = False
flip = False
def detect_card(img):
    h, w = img.shape[:2]
    max_dim = 1200

    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        img_resized = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    else:
        img_resized = img
        scale = 1.0

    gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 100)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edges = cv2.dilate(edges, kernel, iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    img_area = gray.shape[0] * gray.shape[1]
    card_contour = None

    for contour in contours[:5]:
        area = cv2.contourArea(contour)
        if area < img_area * 0.001 or area > img_area * 0.7:
            continue

        x, y, w_rect, h_rect = cv2.boundingRect(contour)
        aspect_ratio = w_rect / float(h_rect)

        if 1.5 < aspect_ratio < 1.7:
            card_contour = contour
            print(f"Card detected! Area: {area / img_area * 100:.1f}% of image, Aspect ratio: {aspect_ratio:.2f}")
            break

    if card_contour is None:
        print("Warning: Card not detected")
        return None, None

    x, y, w_rect, h_rect = cv2.boundingRect(card_contour)

    if scale != 1.0:
        x = int(x / scale)
        y = int(y / scale)
        w_rect = int(w_rect / scale)
        h_rect = int(h_rect / scale)

    card = img
    bbox = (x, y, w_rect, h_rect)

    return card, bbox

def detect_blue_color(img):
    global colorBlue
    global colorRed
    global flip
    height, width = img.shape[:2]
    flipped = cv2.flip(img, 0)
    top = flipped[int(height * 0.19):int(height * 0.28), int(width * 0.2):int(width * 0.8)]
    bottom = img[int(height * 0.73):int(height * 0.82), int(width * 0.2):int(width * 0.8)]
    hsv_bottom = cv2.cvtColor(bottom, cv2.COLOR_BGR2HSV)
    hsv_top = cv2.cvtColor(top, cv2.COLOR_BGR2HSV)

    lower_blue = np.array([100, 100, 50])
    upper_blue = np.array([140, 255, 255])
    lower_red1 = np.array([0, 100, 50])
    upper_red1 = np.array([10, 255, 255])

    lower_red2 = np.array([170, 100, 50])
    upper_red2 = np.array([180, 255, 255])

    maskredBottom = cv2.inRange(hsv_bottom, lower_red1, upper_red1) + cv2.inRange(hsv_bottom, lower_red2, upper_red2)
    maskBlueBottom = cv2.inRange(hsv_bottom, lower_blue, upper_blue)
    ratioBlue = np.sum(maskBlueBottom > 0) / maskBlueBottom.size
    ratioRed = np.sum(maskredBottom > 0) / maskredBottom.size
    mask_blue_top = cv2.inRange(hsv_top, lower_blue, upper_blue)
    mask_red_top = (cv2.inRange(hsv_top, lower_red1, upper_red1) + cv2.inRange(hsv_top, lower_red2, upper_red2))

    ratioBlueTop = np.sum(mask_blue_top > 0) / mask_blue_top.size
    ratioRedTop = np.sum(mask_red_top > 0) / mask_red_top.size
    print("Blue ratio Bottom:", ratioBlue)
    print("Red ratio Bottom:", ratioRed)

    print("Blue ratio Bottom:", ratioBlueTop)
    print("Red ratio Bottom:", ratioRedTop)



    if ratioBlue > 0.2:

        colorBlue = True
        print("color:", colorBlue)
    elif ratioRed > 0.2:
        colorRed = True
    elif ratioBlueTop > 0.2 or ratioBlue:
        flip = True
        if ratioBlueTop > 0.2:
            colorBlue = True
        elif ratioRedTop > 0.2:
            colorRed = False

        print("color:", colorBlue)
        print("color", colorRed)


def preprocess_image(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh





def crop_text_region(img):
    height, width = img.shape[:2]
    x_start = int(width * 0.35)
    x_end = int(width * 0.7)
    y_start = int(height * 0.3)
    y_end = int(height * 0.9)
    text_region = img[y_start:y_end, x_start:x_end]
    return text_region
def crop_text_region_old(img):
    height, width = img.shape[:2]
    x_start = int(width * 0.2)
    x_end = int(width * 0.6)
    y_start = int(height * 0.3)
    y_end = int(height * 0.9)
    text_region = img[y_start:y_end, x_start:x_end]
    return text_region

def extract_student_info(img):

    print("Step 1: Detect card type")
    detect_blue_color(img)
    print("Step 2: Cropping text region...")
    if (colorBlue):
        text_region = crop_text_region(img)
    elif(colorRed):
        text_region = crop_text_region_old(img)
    elif(flip):
        img = cv2.flip(img, 0)
        if(colorBlue):
            text_region = crop_text_region(img)
        elif(colorRed):
            text_region = crop_text_region_old(img)


    print("Step 3: Running OCR...")
    processed = preprocess_image(text_region)
    custom_config = r'--oem 3 --psm 6 -l tur+eng'
    text = pytesseract.image_to_string(processed, config=custom_config)

    print("\nExtracted Text:")
    print("=" * 50)
    print(text)
    print("=" * 50)

    result = {
        'name': None,
        'student_id': None,
        'raw_text': text
    }

    id_match = re.search(r'\b\d{7}\b', text)
    if id_match:
        result['student_id'] = id_match.group(0)

    lines = text.split('\n')
    filter_keywords = ['program', 'pragram', 'mühendislik', 'engineering', 'bilgisayar',
                       'computer', 'kkk', 'ncc', 'mühehdislik', 'programları', 'programme',
                       'öğrenci', 'student', 'no', 'id', 'ad soyad', 'name surname',
                       'bölüm', 'department', 'fakülte', 'faculty']

    found_name = False
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        if ('ad soyad' in line_lower or 'name surname' in line_lower or
            'at soyod' in line_lower or 'nome surname' in line_lower) and not found_name:
            candidate_lines = []
            print('Name field found\n-----------------------------')
            for j in range(i + 1, min(i + 3, len(lines))):
                ln = lines[j].strip()
                ln_lower = ln.lower()
                if len(ln) < 3:
                    continue
                if any(keyword in ln_lower for keyword in filter_keywords):
                    continue
                if any(ch.isdigit() for ch in ln):
                    continue
                candidate_lines.append(ln)

            combined = " ".join(candidate_lines)
            combined = re.sub(r"[^A-Za-zÇĞİÖŞÜçğıöşü\s]", " ", combined)
            combined = re.sub(r"\s+", " ", combined).strip()
            words = combined.split()
            filtered_words = []

            for word in words:
                word_lower = word.lower()
                if not any(kw in word_lower for kw in filter_keywords):
                    filtered_words.append(word)
            if len(filtered_words) >= 2:
                result['name'] = " ".join(filtered_words)
                found_name = True
                break
            filtered_words = filtered_words[:4]

    if not result['name']:
        for line in lines:
            line_stripped = line.strip()
            line_lower = line_stripped.lower()
            if any(keyword in line_lower for keyword in filter_keywords):
                continue
            if any(char.isdigit() for char in line_stripped):
                continue
            cleaned = re.sub(r"[^A-Za-zÇĞİÖŞÜçğıöşü\s]", " ", line_stripped)
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            words = cleaned.split()
            if len(words) >= 2 and 5 < len(cleaned) < 35:
                if all(word[0].isupper() for word in words if len(word) > 0):
                    result['name'] = cleaned
                    break

    return result


def capture_and_process():
    """Capture photo and process ID card"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_filename = f"{OUTPUT_DIR}/capture_{timestamp}.jpg"
    output_filename = f"{OUTPUT_DIR}/result_{timestamp}.txt"

    print(f"\n{'=' * 60}")
    print(f"Button pressed! Taking photo...")
    print(f"{'=' * 60}\n")

    # Turn on BLUE LED to indicate processing
    set_led_color(red=False, green=False, blue=True)

    # Use rpicam-still for better image quality
    print("Camera warming up and focusing...")

    # Take photo with rpicam-still (better quality than Picamera2)
    try:
        # Try rpicam-still first (newer)
        result = subprocess.run([
            'rpicam-still',
            '-o', image_filename,
            '--width', '3280',
            '--height', '2464',
            '--timeout', '3000',  # 3 second delay for focus
            '--autofocus-mode', 'auto',
            '--brightness', '0.1',
            '--contrast', '1.2',
            '--sharpness', '1.5'
        ], capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            raise Exception("rpicam-still failed")

    except (FileNotFoundError, Exception):
        # Fallback to libcamera-still (older systems)
        print("Trying libcamera-still...")
        result = subprocess.run([
            'libcamera-still',
            '-o', image_filename,
            '--width', '3280',
            '--height', '2464',
            '-t', '3000',  # 3 second delay for focus
            '--brightness', '0.1',
            '--contrast', '1.2',
            '--sharpness', '1.5'
        ], capture_output=True, text=True, timeout=10)

    print("Photo captured successfully!")
    print(f"Photo saved: {image_filename}")

    # Read captured image - THIS WAS MISSING!
    img = cv2.imread(image_filename)

    if img is None:
        error_msg = "Error: Could not read captured image"
        print(error_msg)

        set_led_color(red=True, green=False, blue=False)  # RED = failure
        time.sleep(2)
        led_off()

        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(error_msg)
        return

    # Process the image
    start_time = time.time()
    student_info = extract_student_info(img)
    processing_time = time.time() - start_time

    # Write results to text file
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("STUDENT ID CARD SCAN RESULTS\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Image File: {image_filename}\n\n")
        f.write("-" * 60 + "\n")
        f.write("EXTRACTED INFORMATION:\n")
        f.write("-" * 60 + "\n")
        f.write(f"Name: {student_info.get('name', 'Not found')}\n")
        f.write(f"Student ID: {student_info.get('student_id', 'Not found')}\n")
        f.write(f"\nProcessing Time: {processing_time:.2f} seconds\n")
        f.write("\n" + "=" * 60 + "\n")
        f.write("RAW OCR TEXT:\n")
        f.write("=" * 60 + "\n")
        f.write(student_info.get('raw_text', ''))
        f.write("\n" + "=" * 60 + "\n")

    print(f"\n{'=' * 60}")
    print("RESULTS SAVED TO FILE:")
    print(f"{'=' * 60}")
    print(f"Output file: {output_filename}")
    print(f"Name: {student_info.get('name', 'Not found')}")
    print(f"Student ID: {student_info.get('student_id', 'Not found')}")
    print(f"Processing time: {processing_time:.2f} seconds")
    print(f"{'=' * 60}\n")

    # Show result color for 2 seconds, then turn off LED
    success = bool(student_info.get('student_id'))  # or also require name if you want
    if success:
        set_led_color(red=False, green=True, blue=False)  # GREEN = success
    else:
        set_led_color(red=True, green=False, blue=False)  # RED = fail
    time.sleep(2)
    led_off()
    print("LED turned off.")


def button_callback(channel):
    """Handle button press"""
    print("\n>>> Button detected! Processing...")
    capture_and_process()

def webcam_auto_capture():
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Camera could not be opened.")
        return None

    print("Camera active")

    stable_counter = 0
    last_bbox = None
    last_capture_time = 0
    cooldown = 3

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        display = frame.copy()

        card, bbox = detect_card(frame)

        if bbox is not None:
            x, y, w, h = bbox
            cv2.rectangle(display, (x, y), (x+w, y+h), (0,255,0), 2)

            if last_bbox is not None:
                dx = abs(x - last_bbox[0])
                dy = abs(y - last_bbox[1])

                if dx < 10 and dy < 10:
                    stable_counter += 1
                else:
                    stable_counter = 0
            else:
                stable_counter = 0

            last_bbox = bbox

            cv2.putText(display, f"Stability: {stable_counter}", (20,50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)

            current_time = time.time()

            if stable_counter > 10 and (current_time - last_capture_time) > cooldown:
                print("Capture!!!")

                filename = f"{OUTPUT_DIR}/card_{int(current_time)}.jpg"
                cv2.imwrite(filename, frame)

                print(f"Saved: {filename}")

                cap.release()
                cv2.destroyAllWindows()

                student_info = extract_student_info(frame)
                return student_info

        else:
            stable_counter = 0
            last_bbox = None

        cv2.imshow("Auto Card Capture", display)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


def main():
    print("\n" + "=" * 60)
    print("RASPBERRY PI ID CARD SCANNER")
    print("=" * 60)
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Button GPIO Pin: {BUTTON_PIN}")
    print(f"LED Pins - R:{LED_RED} G:{LED_GREEN} B:{LED_BLUE}")
    print("\nWaiting for button press...")
    print("Press Ctrl+C to exit")
    print("=" * 60 + "\n")

    # Make sure LED is off at startup
    led_off()

    last_press_time = 0
    debounce_time = 1.0  # 1 seconds between presses

    try:
        # Keep the program running and check button state
        while True:
            if GPIO.input(BUTTON_PIN) == GPIO.LOW:
                current_time = time.time()
                if current_time - last_press_time > debounce_time:
                    print("\n>>> Button detected! Processing...")

                    student_info = webcam_auto_capture()
                    student_id = student_info.get("student_id")
                    ocr_name = student_info.get("name")

                    check_result = checker.check_student_by_current_course(student_id, ocr_name)
                    last_press_time = current_time

                    dateformatted = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    csv_path = "results.csv"
                    file_exists = os.path.isfile(csv_path)

                    with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=["name", "student_id", "dateformatted"])

                        if not file_exists:
                            writer.writeheader()

                        final_name = check_result.get("name", student_info.get("name", "Not found"))

                        writer.writerow({
                            "name": final_name,
                            "student_id": student_info.get("student_id", "Not found"),
                            "dateformatted": dateformatted
                        })
                    print(f"CSV saved to: {csv_path}")
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        led_off()  # Turn off LED before cleanup
        pwm_red.stop()
        pwm_green.stop()
        pwm_blue.stop()
        GPIO.cleanup()
        print("GPIO cleaned up. Goodbye!")


if __name__ == "__main__":
    main()