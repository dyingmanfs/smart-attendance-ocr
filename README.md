# Smart Attendance OCR

A Raspberry Pi attendance prototype that reads student cards using computer vision and OCR, then calls a course-membership checker and records results.

## Stack
Python, OpenCV, Tesseract/pytesseract, NumPy, Raspberry Pi GPIO.

## Source workflow
- Button and camera input.
- Card contour detection and color-based card-format handling.
- Text-region cropping, grayscale conversion, and thresholding.
- Turkish/English OCR and student-number extraction.
- Course-membership checking through a separate `checker` module.
- RGB LED feedback and CSV logging.

## Hardware and setup
Requires a Raspberry Pi with compatible camera access, a button on BCM GPIO 17, and RGB LED channels on BCM GPIO 22/23/24. Use current-limiting resistors; PWM is not a replacement for resistors despite comments in the original prototype.

Install Tesseract with Turkish and English language data through your operating system, then install Python dependencies:
```bash
pip install -r requirements.txt
```
Review camera commands and `/home/pi/id_scans` in `OcrforTest.py` for your hardware.

## Missing dependency and current status
The supplied snapshot imports `checker.py`, but that file is absent. Restore the original module implementing `check_student_by_current_course(student_id, ocr_name)` and its course data before running:
```bash
python OcrforTest.py
```
This is a hardware prototype and has not been validated on a Raspberry Pi in this preparation pass. Captured cards, student records, and generated CSV files are excluded from version control.
