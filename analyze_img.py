
import cv2
import os

img_path = r'D:\MyProject\ok-wuthering-waves\logs\debug_snapshots\stamina_3.png'
if os.path.exists(img_path):
    img = cv2.imread(img_path)
    if img is not None:
        h, w, _ = img.shape
        print(f"Image Size: {w}x{h}")
        # Upstream coordinate check: 0.49, 0.0, 0.92, 0.10
        x1, y1, x2, y2 = int(0.49*w), int(0.0*h), int(0.92*w), int(0.10*h)
        print(f"Upstream OCR Region (Pixels): x={x1} to {x2}, y={y1} to {y2}")
        
        # Save a crop of the region for manual verification if possible
        crop = img[y1:y2, x1:x2]
        cv2.imwrite('tmp_stamina_crop.png', crop)
        print("Saved tmp_stamina_crop.png")
    else:
        print("Failed to read image")
else:
    print(f"Path not found: {img_path}")
