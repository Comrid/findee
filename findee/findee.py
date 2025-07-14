from __future__ import annotations
import time
import atexit
import sys
import numpy as np
import logging
import os
import subprocess
import psutil
import threading
from typing import Optional
from .util import FindeeFormatter, LogMessage
from dataclasses import dataclass
from pydantic import BaseModel

# region : Dataclass Definition
class Status(BaseModel):
    safe_mode: bool = False
    motor_status: bool = False
    camera_status: bool = False
    ultrasonic_status: bool = False

class CameraStatus(BaseModel):
    fps: float
    current_resolution: tuple[int, int]

class SystemInfo(BaseModel):
    hostname: str  = "0.0.0.0"
    cpu_percent: float = 0.0
    cpu_cores_percent: list[float] = []
    cpu_temperature: float = 0.0
    memory_percent: float = 0.0
# endregion

logger = FindeeFormatter().get_logger()
logging.getLogger('picamera2').setLevel(logging.WARNING)

# region : Check for uninstalled modules & Platform
try:
    logger.info(LogMessage.module_import_start)
    is_initialize_error_occured: bool = False

    # Check for RPi.GPIO
    try:
        import RPi.GPIO as GPIO # pip install RPi.GPIO
    except ImportError:
        logger.error(LogMessage.module_not_installed.format(module="RPi.GPIO"))
        is_initialize_error_occured = True

    # Check for picamera2
    try:
        from picamera2 import Picamera2 # pip install picamera2
    except ImportError:
        logger.error(LogMessage.module_not_installed.format(module="picamera2"))
        is_initialize_error_occured = True

    # Check for opencv-python
    try:
        import cv2 # pip install opencv-python
    except ImportError:
        logger.error(LogMessage.module_not_installed.format(module="opencv-python"))
        is_initialize_error_occured = True

    # Check for Platform
    platform = sys.platform
    if platform == "win32":
        logger.error(LogMessage.platform_not_supported.format(platform=platform))
        is_initialize_error_occured = True

    if is_initialize_error_occured:
        raise Exception()
except Exception as e:
    logger.error(LogMessage.module_import_failure.format(error=e))
    sys.exit(1)
else:
    logger.info(LogMessage.module_import_success)
# endregion

# region : Findee Class Definition
class Findee:
    def __init__(self, safe_mode: bool = False, camera_resolution: tuple[int, int] = (640, 480)):
        try:
            logger.info(LogMessage.findee_init_start)

            # GPIO Setting
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)

            # Class Initialization
            self.motor = self.Motor(safe_mode)
            self.camera = self.Camera(safe_mode, camera_resolution)
            self.ultrasonic = self.Ultrasonic(safe_mode)

            # Class Variables
            self.system_info = SystemInfo(hostname=subprocess.check_output(['hostname', '-I'], shell=False).decode().strip())
            self.update_system_info()
            self.status = Status(
                safe_mode = safe_mode,
                motor_status = self.motor._is_available,
                camera_status = self.camera._is_available,
                ultrasonic_status = self.ultrasonic._is_available
            )

            #-Cleanup-#
            atexit.register(self.cleanup)
        except Exception as e:
            logger.error(LogMessage.findee_init_failure.format(error=e))
            sys.exit(1)
        else:
            logger.info(LogMessage.findee_init_success)
            time.sleep(0.1)

# region : Findee Class Methods
    def update_system_info(self):
        def _update():
            while True:
                self.system_info.cpu_percent = psutil.cpu_percent(interval=0.1)
                self.system_info.cpu_cores_percent = psutil.cpu_percent(interval=0.1, percpu=True)
                self.system_info.memory_percent = psutil.virtual_memory().percent
                try:
                    with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                        self.system_info.cpu_temperature = int(f.read()) / 1000.0
                except FileNotFoundError:
                    self.system_info.cpu_temperature = 0.0
                time.sleep(1)
        threading.Thread(target=_update, daemon=True).start()

    def get_system_info(self) -> dict:
        return self.system_info.model_dump()

    def get_status(self) -> dict:
        return self.status.model_dump()

    def get_hostname(self) -> str:
        return self.system_info.hostname

    #-Cleanup-#
    def cleanup(self):
        self.motor.cleanup()
        self.camera.cleanup()
        self.ultrasonic.cleanup()
        logger.info("프로그램이 정상적으로 종료되었습니다.")
# endregion

    #-Motor Class Definition-#
    class Motor:
        def __init__(self, safe_mode: bool = False):
            #-Class Variables-#
            self.safe_mode: bool = safe_mode
            self._is_available: bool = False

            #-Motor GPIO-#
            self.IN1: int = 23 # Right Motor Direction 1
            self.IN2: int = 24 # Right Motor Direction 2
            self.ENA: int = 12 # Right Motor PWM
            self.IN3: int = 22 # Left Motor Direction 1
            self.IN4: int = 27 # Left Motor Direction 2
            self.ENB: int = 13  # Left Motor PWM

            try:
                #-GPIO Setup-#
                chan_list = [self.IN1, self.IN2, self.ENA, self.IN3, self.IN4, self.ENB]
                GPIO.setup(chan_list, GPIO.OUT, initial=GPIO.LOW)

                #-PWM Setup-#
                self.rightPWM = GPIO.PWM(self.ENA, 1000); self.rightPWM.start(0)
                self.leftPWM = GPIO.PWM(self.ENB, 1000); self.leftPWM.start(0)
            except Exception as e:
                if self.safe_mode:
                    self._is_available = False
                    logger.warning(LogMessage.motor_init_failure_safe_mode)
                else:
                    logger.error(LogMessage.motor_init_failure)
                    sys.exit(1)
            else:
                logger.info(LogMessage.motor_init_success)
                self._is_available = True

            #-Motor Parameter-#
            self.MOTOR_SPEED = 80
            self.start_time_motor = time.time()

        def pinChange(self, IN1, IN2, IN3, IN4, ENA, ENB):
            self.IN1 = IN1 if IN1 is not None else self.IN1
            self.IN2 = IN2 if IN2 is not None else self.IN2
            self.IN3 = IN3 if IN3 is not None else self.IN3
            self.IN4 = IN4 if IN4 is not None else self.IN4
            self.ENA = ENA if ENA is not None else self.ENA
            self.ENB = ENB if ENB is not None else self.ENB

        @staticmethod
        def constrain(value, min_value, max_value):
            return max(min(value, max_value), min_value)

        #-Basic Motor Control Method-#
        def control_motors(self, right : float, left : float) -> bool:
            if not self._is_available:
                logger.warning("모터가 비활성화 상태입니다.")
                return False
            try:
                """
                right : 20 ~ 100, -20 ~ -100, 0
                left : -20 ~ -100, 20 ~ 100, 0
                """
                #-Right Motor Control-#
                if right == 0.0:
                    self.rightPWM.ChangeDutyCycle(0.0)
                    GPIO.output((self.IN1, self.IN2), GPIO.LOW)
                else:
                    right = (1 if right >= 0 else -1) * self.constrain(abs(right), 20, 100)
                    self.rightPWM.ChangeDutyCycle(100.0) # 100% for strong torque at first time
                    # OUT1(HIGH) -> OUT2(LOW) : Forward
                    GPIO.output(self.IN1, GPIO.HIGH if right > 0 else GPIO.LOW)
                    GPIO.output(self.IN2, GPIO.LOW if right > 0 else GPIO.HIGH)
                    time.sleep(0.02)
                    self.rightPWM.ChangeDutyCycle(abs(right))

                #-Left Motor Control-#
                if left == 0.0:
                    self.leftPWM.ChangeDutyCycle(0.0)
                    GPIO.output((self.IN3, self.IN4), GPIO.LOW)
                else:
                    left = (1 if left >= 0 else -1) * self.constrain(abs(left), 20, 100)
                    self.leftPWM.ChangeDutyCycle(100.0) # 100% for strong torque at first time
                    # OUT4(HIGH) -> OUT3(LOW) : Forward
                    GPIO.output(self.IN4, GPIO.HIGH if left > 0 else GPIO.LOW)
                    GPIO.output(self.IN3, GPIO.LOW if left > 0 else GPIO.HIGH)
                    time.sleep(0.02)
                    self.leftPWM.ChangeDutyCycle(abs(left))
            except Exception as e:
                logger.warning(f"모터 제어 중 오류가 발생했습니다. {e}")
                return False
            else:
                return True

        #-Derived Motor Control Method-#
        # Straight, Backward
        def move_forward(self, speed : float, time_sec : Optional[float] = None):
            self.control_motors(speed, speed)
            if time_sec is not None:
                time.sleep(time_sec)
                self.stop()

        def move_backward(self, speed : float, time_sec : Optional[float] = None):
            self.control_motors(-speed, -speed)
            if time_sec is not None:
                time.sleep(time_sec)
                self.stop()

        # Rotation
        def turn_left(self, speed : float, time_sec : Optional[float] = None):
            self.control_motors(speed, -speed)
            if time_sec is not None:
                time.sleep(time_sec)
                self.stop()

        def turn_right(self, speed : float, time_sec : Optional[float] = None):
            self.control_motors(-speed, speed)
            if time_sec is not None:
                time.sleep(time_sec)
                self.stop()

        # Curvilinear Rotation
        def curve_left(self, speed : float, angle : int, time_sec : Optional[float] = None):
            angle = self.constrain(angle, 0, 60)
            ratio = 1.0 - (angle / 60.0) * 0.5
            self.control_motors(speed, speed * ratio)
            if time_sec is not None:
                time.sleep(time_sec)
                self.stop()

        def curve_right(self, speed : float, angle : int, time_sec : Optional[float] = None):
            angle = self.constrain(angle, 0, 60)
            ratio = 1.0 - (angle / 60.0) * 0.5
            self.control_motors(speed * ratio, speed)
            if time_sec is not None:
                time.sleep(time_sec)
                self.stop()

        #-Stop & Cleanup-#
        def stop(self):
            self.control_motors(0.0, 0.0)

        def cleanup(self):
            #self.stop()
            self.rightPWM.stop()
            self.leftPWM.stop()
            GPIO.cleanup(self.chan_list)
            logger.info("모터 정리 완료!")

    #-Camera Class Definition-#
    class Camera:
        def __init__(self, safe_mode: bool = False, camera_resolution: tuple[int, int] = (640, 480)):
            #-Class Variables-#
            self.safe_mode = safe_mode
            self._is_available = False

            # Camera Object
            self.picam2 = None

            # Camera Parameter
            self.current_frame = None
            self.frame_lock = threading.Lock()
            self.current_resolution = camera_resolution
            self.fps = 0
            self.frame_count = 0
            self.last_fps_time = time.time()

            self.available_resolutions = [
                {'label': '320x240 (QVGA)', 'value': '320x240', 'width': 320, 'height': 240},
                {'label': '640x480 (VGA)', 'value': '640x480', 'width': 640, 'height': 480},
                {'label': '800x600 (SVGA)', 'value': '800x600', 'width': 800, 'height': 600},
                {'label': '1024x768 (XGA)', 'value': '1024x768', 'width': 1024, 'height': 768},
                {'label': '1280x720 (HD)', 'value': '1280x720', 'width': 1280, 'height': 720},
                {'label': '1920x1080 (FHD)', 'value': '1920x1080', 'width': 1920, 'height': 1080}
            ]

            try:
                os.environ['LIBCAMERA_LOG_FILE'] = '/dev/null' # disable logging
                self.picam2 = Picamera2()
                self.picam2.preview_configuration.main.size = self.current_resolution
                self.picam2.preview_configuration.main.format = "RGB888"
                self.picam2.configure("preview")
                self.picam2.start()
            except Exception as e:
                if self.safe_mode:
                    logger.warning(f"[Safe Mode] 카메라 초기화에 실패했습니다. 카메라 관련 함수를 사용할 수 없습니다. {e}")
                    self._is_available = False
                else:
                    logger.error(f"카메라 초기화에 실패했습니다. 프로그램을 종료합니다. {e}")
                    sys.exit(1)
            else:
                os.environ['LIBCAMERA_LOG_FILE'] = '' # restore logging
                logger.info("카메라 초기화 성공!")
                self._is_available = True

        # TODO: 카메라 해상도 설정 함수 구현
        # TODO: OpenCV 필터링 등 간단한 함수 구현

        #-Get Frame from Camera-#
        def get_frame(self) -> np.ndarray | None:
            if not self._is_available:
                logger.warning("카메라가 비활성화 상태입니다.")
                return None

            try:
                frame = self.picam2.capture_array()
                return frame
            except Exception as e:
                logger.error(f"프레임 캡처 중 오류가 발생했습니다: {e}")
                return None

        def start_frame_capture(self):
            """별도 스레드에서 프레임 캡처 시작"""
            def capture_loop():
                while self._is_available:
                    try:
                        frame = self.get_frame()
                        if frame is not None:
                            with self.frame_lock:
                                self.current_frame = frame.copy()

                            # FPS 계산
                            self.frame_count += 1
                            current_time = time.time()
                            if current_time - self.last_fps_time >= 1.0:
                                self.fps = self.frame_count
                                self.frame_count = 0
                                self.last_fps_time = current_time

                        time.sleep(0.033)  # ~30 FPS
                    except Exception as e:
                        print(f"프레임 캡처 오류: {e}")
                        time.sleep(0.1)
                        continue

            capture_thread = threading.Thread(target=capture_loop, daemon=True)
            capture_thread.start()

        def generate_frames(self):
            """MJPEG 프레임 생성 (Flask 스트리밍용)"""
            while self._is_available:
                try:
                    with self.frame_lock:
                        if self.current_frame is not None:
                            frame = self.current_frame.copy()
                        else:
                            # 기본 프레임 생성 (카메라 연결 대기 중)
                            frame = self.create_placeholder_frame()

                    # JPEG로 인코딩
                    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    if ret:
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                            b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

                    time.sleep(0.033)  # ~30 FPS

                except Exception as e:
                    print(f"프레임 생성 오류: {e}")
                    time.sleep(0.1)
                    continue

        def create_placeholder_frame(self):
            """카메라 연결 대기 중 표시할 플레이스홀더 프레임"""
            frame = np.zeros((self.current_resolution[1], self.current_resolution[0], 3), dtype=np.uint8)
            frame.fill(50)  # 어두운 회색 배경

            # 텍스트 추가
            text = "Camera Connecting..."
            font = cv2.FONT_HERSHEY_SIMPLEX
            text_size = cv2.getTextSize(text, font, 1, 2)[0]
            text_x = (frame.shape[1] - text_size[0]) // 2
            text_y = (frame.shape[0] + text_size[1]) // 2

            cv2.putText(frame, text, (text_x, text_y), font, 1, (255, 255, 255), 2)
            return frame

        def configure_resolution(self, width : int, height : int):
            try:
                if hasattr(self.parent, 'camera') and self.parent.camera._is_available:
                    previous_resolution = self.current_resolution
                    self.current_resolution = (width, height)
                    # picamera2 해상도 설정
                    self.parent.camera.picam2.stop()
                    self.parent.camera.picam2.preview_configuration.main.size = (width, height)
                    self.parent.camera.picam2.configure("preview")
                    self.parent.camera.picam2.start()
                    logger.info(f"카메라 해상도가 변경되었습니다. {previous_resolution} -> {self.current_resolution}")
            except Exception as e:
                logger.error(f"카메라 해상도 변경 중 오류가 발생하였습니다. {previous_resolution} -> {self.current_resolution}")
                # 기본 해상도로 복구 시도
                if self.current_resolution != (640, 480):
                    self.current_resolution = (640, 480)
                    try:
                        self.parent.camera.picam2.preview_configuration.main.size = (640, 480)
                        self.parent.camera.picam2.configure("preview")
                        self.parent.camera.picam2.start()
                        logger.info("기본 해상도로 복구 성공")
                    except Exception as e:
                        logger.error(f"기본 해상도 복구 실패: {e}")

        def get_available_resolutions(self):
            """사용 가능한 해상도 목록 반환"""
            return self.available_resolutions

        def get_current_resolution(self):
            """현재 해상도 반환"""
            return f"{self.current_resolution[0]}x{self.current_resolution[1]}"

        #-Cleanup-#
        def cleanup(self):
            try:
                # picam2 속성이 존재하고 None이 아닌 경우에만 정리
                if hasattr(self, 'picam2') and self.picam2 is not None:
                    self.picam2.stop()
                    del self.picam2
                    logger.info("카메라 정리 완료!")
            except Exception as e:
                logger.error(f"카메라 정리 중 오류가 발생했습니다: {e}")
            finally:
                # 정리 후 상태 초기화
                self.picam2 = None
                self._is_available = False

    #-Ultrasonic Class Definition-#
    class Ultrasonic:
        def __init__(self, safe_mode: bool = False):
            #-Class Variables-#
            self.safe_mode = safe_mode
            self._is_available = False

            # GPIO Pin Number
            self.TRIG = 5
            self.ECHO = 6

            # Ultrasonic Sensor Parameter
            self.SOUND_SPEED = 34300
            self.TRIGGER_PULSE = 0.00001 # 10us
            self.TIMEOUT = 0.03 # 30ms
            self.last_distance: Optional[float] = None

            try:
                # GPIO Pin Setting
                GPIO.setup(self.TRIG, GPIO.OUT, initial=GPIO.LOW)
                GPIO.setup(self.ECHO, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            except Exception as e:
                if self.safe_mode:
                    logger.warning(f"[Safe Mode] 초음파 센서 초기화에 실패했습니다. 초음파 센서 관련 함수를 사용할 수 없습니다. {e}")
                    self._is_available = False
                else:
                    logger.error(f"초음파 센서 초기화에 실패했습니다. 프로그램을 종료합니다. {e}")
                    sys.exit(1)
            else:
                logger.info("초음파 센서 초기화 성공!")
                self._is_available = True

        #-Get Last Distance from Ultrasonic Sensor-#
        def get_last_distance(self) -> Optional[float]:
            return self.last_distance

        #-Get Distance from Ultrasonic Sensor-#
        def get_distance(self) -> Optional[float]:
            if not self._is_available:
                logger.warning("초음파 센서가 비활성화 상태입니다.")
                return None

            try:
                # Trigger
                GPIO.output(self.TRIG, GPIO.HIGH)
                time.sleep(self.TRIGGER_PULSE)
                GPIO.output(self.TRIG, GPIO.LOW)

                # Measure Distance
                loop_start_time = time.time()
                while GPIO.input(self.ECHO) is not GPIO.HIGH:
                    if time.time() - loop_start_time > 0.1:
                        logger.warning("ECHO 핀을 읽을 수 없습니다. 초음파 센서의 ECHO 핀의 연결을 확인해주세요.")
                        return None

                start_time = time.time()
                end_time = None;
                is_timeout = False;

                while GPIO.input(self.ECHO) is not GPIO.LOW:
                    if time.time() - start_time > self.TIMEOUT:
                        is_timeout = True
                        break

                end_time = time.time()

                if is_timeout:
                    # Timeout
                    return None
                else:
                    # Measure Success
                    duration = end_time - start_time
                    distance = (duration * self.SOUND_SPEED) / 2
                    self.last_distance = distance
                    #print(f"start_time: {start_time}, end_time: {end_time}, duration: {duration}, distance: {distance}")
                    return round(distance, 1)
            except Exception as e:
                logger.error(f"초음파 센서 측정 중 오류가 발생했습니다: {e}")
                return None

        #-Cleanup-#
        def cleanup(self):
            if self._is_available:
                GPIO.cleanup((self.TRIG, self.ECHO))
                logger.info("초음파 정리 완료!")
# endregion


if __name__ == "__main__":
    robot = Findee()
    print(robot.ip)