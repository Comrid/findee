import cv2
import numpy as np
import logging
from dataclasses import dataclass

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
def image_to_ascii(image: np.ndarray, width: int = 100, contrast: int = 10, reverse: bool = True) -> str:
    # Density Definition
    density = r'$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:,"^`\'.            '
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

#-Colored Formatter for Logging-#
class FindeeFormatter(logging.Formatter):
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',    # cyan
        'INFO': '\033[32m',     # green
        'WARNING': '\033[33m',  # yellow
        'ERROR': '\033[31m',    # red
        'CRITICAL': '\033[35m', # purple
        'RESET': '\033[0m'      # reset
    }

    def format(self, record):
        # Apply original format
        message = super().format(record)

        # Apply color to level name
        level_color = self.COLORS.get(record.levelname, '')
        reset = self.COLORS['RESET']

        # Return colored message
        return f"{level_color}[{record.levelname}]{reset} {message}"

    def get_logger(self):
        logger = logging.getLogger("Findee")
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(FindeeFormatter('%(message)s'))
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
        return logger

@dataclass
class LogMessage:
    #-Module Initialize Messages-#
    module_import_start: str = "패키지 체크 시작!"
    module_import_success: str = "패키지 체크 완료!"
    module_import_failure: str = "패키지 체크 중 오류가 발생했습니다. 프로그램을 종료합니다. {error}"
    module_not_installed: str = "findee 모듈을 사용하기 위해 {module} 모듈이 필요합니다. pip install {module} 를 통해 설치할 수 있습니다."
    platform_not_supported: str = "findee 모듈은 Windows 플랫폼에서는 사용할 수 없습니다. {platform} 플랫폼은 지원하지 않습니다."

    #-Findee Class Messages-#
    findee_init_start: str = "Findee 클래스 초기화 시작!"
    findee_init_success: str = "Findee 클래스 초기화 성공!"
    findee_init_failure: str = "Findee 클래스 초기화 중 오류가 발생했습니다. 프로그램을 종료합니다. {error}"

    #-Motor Messages-#
    motor_init_success: str = "모터 초기화 성공!"
    motor_init_failure: str = "모터 초기화에 실패했습니다. 프로그램을 종료합니다."
    motor_init_failure_safe_mode: str = "[Safe Mode] 모터 초기화에 실패했습니다. 모터 관련 함수를 사용할 수 없습니다."
    motor_control_on_safe_mode: str = "모터가 비활성화 상태입니다."
    motor_control_failure: str = "모터 제어 중 오류가 발생했습니다."
    motor_cleanup_success: str = "모터 정리 완료!"

    #-Camera Messages-#
    camera_init_success: str = "카메라 초기화 성공!"
    camera_init_failure: str = "카메라 초기화에 실패했습니다. 프로그램을 종료합니다."
    camera_init_failure_safe_mode: str = "[Safe Mode] 카메라 초기화에 실패했습니다. 카메라 관련 함수를 사용할 수 없습니다."
    camera_control_on_safe_mode: str = "카메라가 비활성화 상태입니다."
    camera_control_failure: str = "카메라 제어 중 오류가 발생했습니다."
    camera_cleanup_success: str = "카메라 정리 완료!"

    #-Ultrasonic Messages-#
    ultrasonic_init_success: str = "초음파 센서 초기화 성공!"
    ultrasonic_init_failure: str = "초음파 센서 초기화에 실패했습니다. 프로그램을 종료합니다."
    ultrasonic_init_failure_safe_mode: str = "[Safe Mode] 초음파 센서 초기화에 실패했습니다. 초음파 센서 관련 함수를 사용할 수 없습니다."
    ultrasonic_control_on_safe_mode: str = "초음파 센서가 비활성화 상태입니다."
    ultrasonic_control_failure: str = "초음파 센서 제어 중 오류가 발생했습니다."
    ultrasonic_cleanup_success: str = "초음파 센서 정리 완료!"