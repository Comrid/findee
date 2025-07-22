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

    @classmethod
    def disable_flask_logger(cls):
        logging.getLogger('werkzeug').setLevel(logging.ERROR)

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

    #-General Messages-#
    """
    {object} : 객체 이름(모터, 카메라, 초음파 센서)
    {command} : 명령
    {error} : 오류 메시지
    """
    init_start: str = "{object} 초기화 시작!"
    init_success: str = "{object} 초기화 성공!"
    init_failure: str = "{object} 초기화 중 오류가 발생했습니다. 프로그램을 종료합니다. {error}"
    init_failure_in_safe_mode: str = "[Safe Mode] {object} 초기화 중 오류가 발생했습니다. {object} 관련 함수를 사용할 수 없습니다. {error}"

    control_in_safe_mode: str = "[Safe Mode] [{object}] {command}"
    control_failure: str = "{object} 제어 중 오류가 발생했습니다. {error}"

    cleanup_success: str = "{object} 정리 완료!"
    cleanup_failure: str = "{object} 정리 중 오류가 발생했습니다. {error}"

    program_exit: str = "프로그램이 정상적으로 종료되었습니다."

    #-Camera Messages-#
    camera_frame_capture_start: str = "카메라 프레임 캡처 시작!"
    camera_frame_capture_stop: str = "카메라 프레임 캡처 중단!"
    camera_frame_capture_start_in_debug_mode: str = "[DEBUG] 랜덤 그레이스케일 프레임 생성 시작!"
    camera_frame_capture_already_running: str = "카메라 프레임 캡처가 이미 실행 중입니다."
    camera_frame_capture_failure: str = "카메라 프레임 캡처 중 오류가 발생했습니다. {error}"
    camera_resolution_change_success: str = "카메라 해상도 변경 성공! {previous_resolution} -> {new_resolution}"
    camera_resolution_change_failure: str = "카메라 해상도 변경 중 오류가 발생했습니다. {error}"
    camera_resolution_restore_success: str = "기본 해상도로 복구 성공!"
    camera_resolution_restore_failure: str = "기본 해상도로 복구 중 오류가 발생했습니다. {error}"

    #-Ultrasonic Sensor Messages-#
    ultrasonic_distance_measurement_start: str = "초음파 센서 거리 측정 시작!"
    ultrasonic_distance_measurement_stop: str = "초음파 센서 거리 측정 중단!"
    ultrasonic_distance_measurement_start_in_debug_mode: str = "[DEBUG] 랜덤 거리 측정 시작!"
    ultrasonic_distance_measurement_already_running: str = "초음파 센서 거리 측정이 이미 실행 중입니다."
    ultrasonic_distance_measurement_failure: str = "초음파 센서 거리 측정 중 오류가 발생했습니다. {error}"
    ultrasonic_echo_timeout: str = "ECHO 핀을 읽을 수 없습니다. 초음파 센서의 ECHO 핀의 연결을 확인해주세요."

    #-System Info Messages-#
    excecuted_in_debug_mode: str = "프로그램이 디버그 모드로 실행되었습니다."
    exit_debug_mode: str = "여기서 원래 프로그램이 종료됩니다."
    warning_debug_mode: str = "DEBUG MODE"