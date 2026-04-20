import cv2
import numpy as np

def largest_contour(mask: np.ndarray, min_area_ratio: float = 0.01, max_area_ratio: float = 0.8):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None
    img_h, img_w = mask.shape[:2]
    img_area = img_h * img_w
    min_area = img_area * min_area_ratio
    max_area = img_area * max_area_ratio
    def is_reasonable_foot_shape(cnt):
        x, y, w, h = cv2.boundingRect(cnt)
        aspect = h / (w + 1e-5)
        if not (1.2 < aspect < 3.5):
            return False
        margin = 10
        if x < margin or y < margin or (x + w) > (img_w - margin) or (y + h) > (img_h - margin):
            return False
        return True
    filtered = [c for c in contours if min_area < cv2.contourArea(c) < max_area and is_reasonable_foot_shape(c)]
    if not filtered:
        return None
    def aspect_ratio(cnt):
        x, y, w, h = cv2.boundingRect(cnt)
        return h / (w + 1e-5)
    return max(filtered, key=aspect_ratio)
