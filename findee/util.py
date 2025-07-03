import cv2
import numpy as np

#-Crop Center of Image-#
def crop_image(image : np.ndarray, scale : float = 1.0) -> np.ndarray:
    h, w = image.shape[:2]
    cx, cy = w // 2, h // 2

    crop_w = int(w * scale / 2)
    crop_h = int(h * scale / 2)

    x1 = max(cx - crop_w, 0)
    x2 = min(cx + crop_w, w)
    y1 = max(cy - crop_h, 0)
    y2 = min(cy + crop_h, h)

    return image[y1:y2, x1:x2]

#-Image to ASCII-#
def image_to_ascii(image: np.ndarray, width: int = 100, contrast: int = 10, reverse: bool = False) -> str:
    # Density Definition
    density = ('$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|'
            '()1{}[]?-_+~<>i!lI;:,"^`\'.            ')
    if reverse:
        density = density[::-1]
    density = density[:-11 + contrast]
    n = len(density)

    # Convert to Grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Resize to Ratio
    orig_height, orig_width = gray.shape
    ratio = orig_height / orig_width
    height = int(width * ratio * 0.5)
    resized = cv2.resize(gray, (width, height), interpolation=cv2.INTER_AREA)

    # Map Brightness to ASCII Characters
    ascii_img = ""
    for i in range(height):
        for j in range(width):
            p = resized[i, j]
            k = int(np.floor(p / 256 * n))
            ascii_img += density[n - 1 - k]
        ascii_img += "\n"

    return ascii_img