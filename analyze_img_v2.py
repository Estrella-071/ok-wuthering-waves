
import cv2
import os
import re

# Simulate the project's environment as much as possible
number_re = re.compile(r'(\d+)')
stamina_re = re.compile(r'(\d+)/(\d+)')

img_path = r'D:\MyProject\ok-wuthering-waves\logs\debug_snapshots\stamina_3.png'

def analyze():
    if not os.path.exists(img_path):
        print(f"Path not found: {img_path}")
        return
        
    img = cv2.imread(img_path)
    if img is None:
        print("Failed to read image")
        return
        
    h, w, _ = img.shape
    print(f"Image Dimensions: {w}x{h}")
    
    # Coordinates from different attempts
    regions = {
        "Upstream (0.49, 0.0, 0.92, 0.10)": (0.49, 0.0, 0.92, 0.10),
        "Modified (0.50, 0.0, 1.00, 0.17)": (0.50, 0.0, 1.00, 0.17),
        "Tight (0.50, 0.0, 1.00, 0.12)": (0.50, 0.0, 1.00, 0.12)
    }
    
    for name, (x1, y1, x2, y2) in regions.items():
        px1, py1, px2, py2 = int(x1*w), int(y1*h), int(x2*w), int(y2*h)
        print(f"{name}: px={px1}~{px2}, py={py1}~{py2}")
        
    # Since I cannot run OCR directly here without the library setup, 
    # I will just print the regions and ask the agent to verify if the stamina bubbles fall within.
    # Looking at the user provided media__1773493132717.png:
    # 240/240 is at a certain pixel pos.
    
analyze()
