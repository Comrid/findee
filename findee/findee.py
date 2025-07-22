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
from dataclasses import dataclass
from pydantic import BaseModel

if __name__ == "__main__": from util import FindeeFormatter, LogMessage
else: from .util import FindeeFormatter, LogMessage

DEBUG = True #if __name__ == "__main__" else False

logger = FindeeFormatter().get_logger()
logging.getLogger('picamera2').setLevel(logging.WARNING)

if DEBUG:logger.info(LogMessage.excecuted_in_debug_mode)

def exit_func():
    sys.exit(0) if not DEBUG else logger.debug(LogMessage.exit_debug_mode)

# region : Dataclass Definition
class Status(BaseModel):
    safe_mode: bool = False
    motor_status: bool = False
    camera_status: bool = False
    ultrasonic_status: bool = False

class SystemInfo(BaseModel):
    hostname: str  = "localhost"
    cpu_percent: float = 0.0
    num_cpu_cores: int = 1
    cpu_cores_percent: list[float] = []
    cpu_temperature: float = 0.0
    memory_percent: float = 0.0

@dataclass
class Object:
    motor: str = "모터"
    camera: str = "카메라"
    ultrasonic: str = "초음파 센서"
# endregion

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
    exit_func()
else:
    logger.info(LogMessage.module_import_success)
# endregion

# region : Findee Class Definition
class Findee:
    def __init__(self, safe_mode: bool = False, camera_resolution: tuple[int, int] = (640, 480)):
        try:
            logger.info(LogMessage.findee_init_start)
            if DEBUG: safe_mode = True

            # GPIO Setting
            GPIO.setwarnings(False) if not DEBUG else None
            GPIO.setmode(GPIO.BCM) if not DEBUG else None

            # Class Initialization
            self.motor = self.Motor(safe_mode)
            self.camera = self.Camera(safe_mode, camera_resolution)
            self.ultrasonic = self.Ultrasonic(safe_mode)

            # Class Variables
            self.is_system_updating = False
            if platform != "linux":
                self.system_info = SystemInfo(num_cpu_cores=psutil.cpu_count(logical=False))
            else:
                self.system_info = SystemInfo(hostname=subprocess.check_output(['hostname', '-I'], shell=False).decode().strip())

            self.update_system_info()
            self.status = Status(
                safe_mode = safe_mode,
                motor_status = self.motor._is_available if not DEBUG else True,
                camera_status = self.camera._is_available if not DEBUG else True,
                ultrasonic_status = self.ultrasonic._is_available if not DEBUG else True
            )

            #-Cleanup-#
            atexit.register(self.cleanup)
        except Exception as e:
            logger.error(LogMessage.findee_init_failure.format(error=e))
            exit_func()
        else:
            logger.info(LogMessage.findee_init_success)
            time.sleep(0.1)
# region : Findee Class Methods
    def update_system_info(self):
        def _update_cpu():
            while True:
                self.system_info.cpu_cores_percent = psutil.cpu_percent(interval=1.0, percpu=True)
                self.system_info.cpu_percent = round(sum(self.system_info.cpu_cores_percent) / self.system_info.num_cpu_cores, 2)

        def _update_memory_temp():
            while True:
                self.system_info.memory_percent = psutil.virtual_memory().percent
                try:
                    with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                        self.system_info.cpu_temperature = int(f.read()) / 1000.0
                except FileNotFoundError:
                    self.system_info.cpu_temperature = 0.0
                time.sleep(1)

        if not self.is_system_updating:
            self.is_system_updating = True
            threading.Thread(target=_update_cpu, daemon=True).start()
            threading.Thread(target=_update_memory_temp, daemon=True).start()

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
        logger.info(LogMessage.program_exit)
# endregion

    #-Motor Class Definition-#
    class Motor:
        def __init__(self, safe_mode: bool = False):
            #-Class Variables-#
            self.safe_mode: bool = safe_mode
            self._is_available: bool = False
            self.object = Object.motor

            #-Motor GPIO-#
            self.IN1: int = 23 # Right Motor Direction 1
            self.IN2: int = 24 # Right Motor Direction 2
            self.ENA: int = 12 # Right Motor PWM
            self.IN3: int = 22 # Left Motor Direction 1
            self.IN4: int = 27 # Left Motor Direction 2
            self.ENB: int = 13  # Left Motor PWM

            try:
                if DEBUG: raise Exception(LogMessage.warning_debug_mode)
                #-GPIO Setup-#
                self.chan_list = [self.IN1, self.IN2, self.ENA, self.IN3, self.IN4, self.ENB]
                GPIO.setup(self.chan_list, GPIO.OUT, initial=GPIO.LOW)

                #-PWM Setup-#
                self.rightPWM = GPIO.PWM(self.ENA, 1000); self.rightPWM.start(0)
                self.leftPWM = GPIO.PWM(self.ENB, 1000); self.leftPWM.start(0)
            except Exception as e:
                if self.safe_mode:
                    self._is_available = False
                    logger.warning(LogMessage.init_failure_in_safe_mode.format(object=self.object, error=e))
                else:
                    logger.error(LogMessage.init_failure.format(object=self.object, error=e))
                    exit_func()
            else:
                logger.info(LogMessage.init_success.format(object=self.object))
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
        def __control_motors(self, right : float, left : float, time_sec : Optional[float] = None) -> bool:
            if not self._is_available:
                return False
            try:
                """
                right : 20 ~ 100, -20 ~ -100, 0
                left : -20 ~ -100, 20 ~ 100, 0
                """
                #-Right Motor Control-#
                if right == 0.0:
                    self.rightPWM.ChangeDutyCycle(0.0)
                    GPIO.output((self.IN1, self.IN2), GPIO.LOW) if not DEBUG else None
                else:
                    right = (1 if right >= 0 else -1) * self.constrain(abs(right), 20, 100)
                    self.rightPWM.ChangeDutyCycle(100.0) # 100% for strong torque at first time
                    # OUT1(HIGH) -> OUT2(LOW) : Forward
                    GPIO.output(self.IN1, GPIO.HIGH if right > 0 else GPIO.LOW) if not DEBUG else None
                    GPIO.output(self.IN2, GPIO.LOW if right > 0 else GPIO.HIGH) if not DEBUG else None
                    time.sleep(0.02)
                    self.rightPWM.ChangeDutyCycle(abs(right))

                #-Left Motor Control-#
                if left == 0.0:
                    self.leftPWM.ChangeDutyCycle(0.0)
                    GPIO.output((self.IN3, self.IN4), GPIO.LOW) if not DEBUG else None
                else:
                    left = (1 if left >= 0 else -1) * self.constrain(abs(left), 20, 100)
                    self.leftPWM.ChangeDutyCycle(100.0) # 100% for strong torque at first time
                    # OUT4(HIGH) -> OUT3(LOW) : Forward
                    GPIO.output(self.IN4, GPIO.HIGH if left > 0 else GPIO.LOW) if not DEBUG else None
                    GPIO.output(self.IN3, GPIO.LOW if left > 0 else GPIO.HIGH) if not DEBUG else None
                    time.sleep(0.02)
                    self.leftPWM.ChangeDutyCycle(abs(left))

                if time_sec is not None:
                    time.sleep(time_sec)
                    self.stop()
            except Exception as e:
                logger.warning(LogMessage.control_failure.format(object=self.object, error=e))
                return False
            else:
                return True

        #-Derived Motor Control Method-#
        # Straight, Backward
        def move_forward(self, speed : float, time_sec : Optional[float] = None):
            if DEBUG: logger.warning(LogMessage.control_in_safe_mode.format(object=self.object, command=f"{self.move_forward.__name__} : right={speed}, left={speed}, time={time_sec}"))
            self.__control_motors(speed, speed, time_sec)

        def move_backward(self, speed : float, time_sec : Optional[float] = None):
            if DEBUG: logger.warning(LogMessage.control_in_safe_mode.format(object=self.object, command=f"{self.move_backward.__name__} : right={speed}, left={speed}, time={time_sec}"))
            self.__control_motors(-speed, -speed, time_sec)

        # Rotation
        def turn_left(self, speed : float, time_sec : Optional[float] = None):
            if DEBUG: logger.warning(LogMessage.control_in_safe_mode.format(object=self.object, command=f"{self.turn_left.__name__} : right={speed}, left={speed}, time={time_sec}"))
            self.__control_motors(speed, -speed, time_sec)

        def turn_right(self, speed : float, time_sec : Optional[float] = None):
            if DEBUG: logger.warning(LogMessage.control_in_safe_mode.format(object=self.object, command=f"{self.turn_right.__name__} : right={speed}, left={speed}, time={time_sec}"))
            self.__control_motors(-speed, speed, time_sec)

        # Curvilinear Rotation
        def curve_left(self, speed : float, angle : int, time_sec : Optional[float] = None):
            angle = self.constrain(angle, 0, 60)
            ratio = 1.0 - (angle / 60.0) * 0.5
            if DEBUG: logger.warning(LogMessage.control_in_safe_mode.format(object=self.object, command=f"{self.curve_left.__name__} : speed={speed}, angle={angle}, time={time_sec}"))
            self.__control_motors(speed, speed * ratio, time_sec)

        def curve_right(self, speed : float, angle : int, time_sec : Optional[float] = None):
            angle = self.constrain(angle, 0, 60)
            ratio = 1.0 - (angle / 60.0) * 0.5
            if DEBUG: logger.warning(LogMessage.control_in_safe_mode.format(object=self.object, command=f"{self.curve_right.__name__} : speed={speed}, angle={angle}, time={time_sec}"))
            self.__control_motors(speed * ratio, speed, time_sec)

        #-Stop & Cleanup-#
        def stop(self):
            if DEBUG: logger.warning(LogMessage.control_in_safe_mode.format(object=self.object, command=f"{self.stop.__name__}"))
            self.__control_motors(0.0, 0.0, None)

        def cleanup(self):
            if self._is_available:
                self.stop()
                self.rightPWM.stop() if not DEBUG else None
                self.leftPWM.stop() if not DEBUG else None
                GPIO.cleanup(self.chan_list) if not DEBUG else None
                logger.info(LogMessage.cleanup_success.format(object=self.object))

    #-Camera Class Definition-#
    class Camera:
        def __init__(self, safe_mode: bool = False, camera_resolution: tuple[int, int] = (640, 480)):
            #-Class Variables-#
            self.safe_mode = safe_mode
            self._is_available = False
            self.object = Object.camera

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
            self._capture_thread = None

            try:
                if DEBUG: raise Exception(LogMessage.warning_debug_mode)
                os.environ['LIBCAMERA_LOG_FILE'] = '/dev/null' # disable logging
                self.picam2 = Picamera2()
                self.picam2.preview_configuration.main.size = self.current_resolution
                self.picam2.preview_configuration.main.format = "RGB888"
                self.picam2.configure("preview")
                self.picam2.start()
            except Exception as e:
                if self.safe_mode:
                    logger.warning(LogMessage.init_failure_in_safe_mode.format(object=self.object, error=e))
                    self._is_available = False
                else:
                    logger.error(LogMessage.init_failure.format(object=self.object, error=e))
                    exit_func()
            else:
                os.environ['LIBCAMERA_LOG_FILE'] = '' # restore logging
                logger.info(LogMessage.init_success.format(object=self.object))
                self._is_available = True

        def get_fps(self) -> float:
            return self.fps

        #-Get Frame from Camera-#
        def get_frame(self) -> Optional[np.ndarray]:
            if not self._is_available:
                if DEBUG:
                    scaler = 10
                    gray_value = np.random.randint(0, 256, (self.current_resolution[1] // scaler, self.current_resolution[0] // scaler), dtype=np.uint8)
                    return np.stack([gray_value, gray_value, gray_value], axis=2)
                logger.warning(LogMessage.control_in_safe_mode.format(object=self.object, command=f"{self.get_frame.__name__}"))
                return None
            try:
                return self.picam2.capture_array()
            except Exception as e:
                logger.error(LogMessage.control_failure.format(object=self.object, error=e))
                return None

        def start_frame_capture(self, frame_rate: int = 30):
            if DEBUG:
                logger.warning(LogMessage.camera_frame_capture_start_in_debug_mode)

            if self._capture_thread and self._capture_thread.is_alive():
                logger.info(LogMessage.camera_frame_capture_already_running)
                return

            def capture_loop():
                interval = 1.0 / frame_rate
                while self._is_available or DEBUG:
                    try:
                        frame = self.get_frame()

                        if frame is not None:
                            with self.frame_lock:
                                self.current_frame = frame.copy()

                            self.frame_count += 1
                            now = time.time()
                            if now - self.last_fps_time >= 1.0:
                                self.fps = self.frame_count
                                self.frame_count = 0
                                self.last_fps_time = now

                        time.sleep(interval)
                    except Exception as e:
                        logger.error(LogMessage.control_failure.format(object=self.object, error=e))
                        time.sleep(0.1)

            self.current_frame = self.get_frame()
            self._capture_thread = threading.Thread(target=capture_loop, daemon=True)
            self._capture_thread.start()

        def stop_frame_capture(self):
            if DEBUG: logger.warning(LogMessage.control_in_safe_mode.format(object=self.object, command=f"{self.stop_frame_capture.__name__}"))

            if self._capture_thread and self._capture_thread.is_alive():
                self._capture_thread.join(timeout=2.0)
                logger.info(LogMessage.camera_frame_capture_stop)

            self._capture_thread = None
            self.current_frame = None
            self.fps = 0
            self.frame_count = 0

        def generate_frames(self, quality: int = 95):
            """Flask 스트리밍을 위한 MJPEG 프레임 생성기"""
            if DEBUG: logger.warning(LogMessage.control_in_safe_mode.format(object=self.object, command=f"{self.generate_frames.__name__} : quality={quality}"))
            while self._is_available or DEBUG:
                try:
                    with self.frame_lock:
                        frame = self.current_frame.copy() if self.current_frame is not None else self.create_placeholder_frame()

                    ret, buffer = cv2.imencode('.jpg', frame,
                                               [cv2.IMWRITE_JPEG_QUALITY, quality,
                                               cv2.IMWRITE_JPEG_OPTIMIZE, 1]
                                               )
                    if not ret:
                        logger.error(LogMessage.control_failure.format(object=self.object, error="JPEG 인코딩 실패"))
                        continue

                    yield (b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

                    time.sleep(1.0 / 30.0)

                except Exception as e:
                    logger.error(LogMessage.control_failure.format(object=self.object, error=e))
                    time.sleep(0.1)

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

        def configure_resolution(self, resolution: tuple[int, int]):
            """Picamera2의 해상도를 설정하고 실패 시 기본 해상도로 복원"""
            if DEBUG:
                logger.warning(LogMessage.control_in_safe_mode.format(
                object=self.object,
                command=f"{self.configure_resolution.__name__} : resolution={self.current_resolution}->{resolution}"
                ))
                self.current_resolution = resolution
                return

            if resolution == self.current_resolution:
                return

            if not (hasattr(self, 'picam2') and self._is_available):
                logger.warning("카메라 사용 불가 상태")
                return

            cam = self.picam2
            previous_resolution = self.current_resolution

            try:
                cam.stop()
                time.sleep(0.05)  # 안정성 확보용
                cam.preview_configuration.main.size = resolution
                cam.configure("preview")
                cam.start()

                self.current_resolution = resolution
                logger.info(LogMessage.camera_resolution_change_success.format(
                    previous_resolution=previous_resolution,
                    new_resolution=resolution
                ))

            except Exception as e:
                logger.error(LogMessage.camera_resolution_change_failure.format(error=e))
                self._restore_default_resolution()

        def _restore_default_resolution(self):
            """해상도 복구 시도"""
            default_res = (640, 480)
            if self.current_resolution == default_res:
                return

            try:
                cam = self.parent.camera.picam2
                cam.stop()
                time.sleep(0.05)
                cam.preview_configuration.main.size = default_res
                cam.configure("preview")
                cam.start()

                self.current_resolution = default_res
                logger.info(LogMessage.camera_resolution_restore_success)
            except Exception as e:
                logger.error(LogMessage.camera_resolution_restore_failure.format(error=e))

        def get_available_resolutions(self):
            """사용 가능한 해상도 목록 반환"""
            return self.available_resolutions

        def get_current_resolution(self):
            """현재 해상도 반환"""
            return f"{self.current_resolution[0]}x{self.current_resolution[1]}"

        #-Cleanup-#
        def cleanup(self):
            self.stop_frame_capture()
            try:
                # picam2 속성이 존재하고 None이 아닌 경우에만 정리
                if hasattr(self, 'picam2') and self.picam2 is not None:
                    self.picam2.stop()
                    del self.picam2
                    logger.info(LogMessage.cleanup_success.format(object=self.object))
            except Exception as e:
                logger.error(LogMessage.cleanup_failure.format(object=self.object, error=e))
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
            self.object = Object.ultrasonic

            # GPIO Pin Number
            self.TRIG = 5
            self.ECHO = 6

            # Ultrasonic Sensor Parameter
            self.SOUND_SPEED = 34300
            self.TRIGGER_PULSE = 0.00001 # 10us
            self.TIMEOUT = 0.03 # 30ms
            self._last_distance: Optional[float] = None
            self._distance_measurement_thread = None

            try:
                if DEBUG: raise Exception(LogMessage.warning_debug_mode)

                # GPIO Pin Setting
                GPIO.setup(self.TRIG, GPIO.OUT, initial=GPIO.LOW)
                GPIO.setup(self.ECHO, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            except Exception as e:
                if self.safe_mode:
                    logger.warning(LogMessage.init_failure_in_safe_mode.format(object=self.object, error=e))
                    self._is_available = False
                else:
                    logger.error(LogMessage.init_failure.format(object=self.object, error=e))
                    exit_func()
            else:
                logger.info(LogMessage.init_success.format(object=self.object))
                self._is_available = True

        #-Get Last Distance from Ultrasonic Sensor-#
        def get_last_distance(self) -> Optional[float]:
            return self._last_distance

        #-Get Distance from Ultrasonic Sensor-#
        def get_distance(self) -> Optional[float]:
            if not self._is_available:
                if DEBUG:
                    return (self._last_distance if self._last_distance is not None else 3) + np.round(np.random.uniform(-0.5, 0.5), 1)
                logger.warning(LogMessage.control_in_safe_mode.format(object=self.object, command=f"{self.get_distance.__name__}"))
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
                        logger.warning(LogMessage.ultrasonic_echo_timeout)
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
                    self._last_distance = distance
                    return round(distance, 1)
            except Exception as e:
                logger.error(LogMessage.control_failure.format(object=self.object, error=e))
                return None

        def start_distance_measurement(self, interval: float = 0.1):
            if DEBUG: logger.warning(LogMessage.ultrasonic_distance_measurement_start_in_debug_mode)

            if self._distance_measurement_thread and self._distance_measurement_thread.is_alive():
                logger.info(LogMessage.ultrasonic_distance_measurement_already_running)
                return

            def distance_measurement_loop():
                while self._is_available or DEBUG:
                    try:
                        distance = self.get_distance()

                        if distance is not None:
                            self._last_distance = distance
                        time.sleep(interval)
                    except Exception as e:
                        logger.error(LogMessage.control_failure.format(object=self.object, error=e))
                        time.sleep(interval // 2)

            self._last_distance = self.get_distance()
            self._distance_measurement_thread = threading.Thread(target=distance_measurement_loop, daemon=True)
            self._distance_measurement_thread.start()

        def stop_distance_measurement(self):
            if DEBUG: logger.warning(LogMessage.control_in_safe_mode.format(object=self.object, command=f"{self.stop_distance_measurement.__name__}"))

            if self._distance_measurement_thread and self._distance_measurement_thread.is_alive():
                self._distance_measurement_thread.join(timeout=2.0)
                logger.info(LogMessage.ultrasonic_distance_measurement_stop)

            self._distance_measurement_thread = None
            self._last_distance = None

        #-Cleanup-#
        def cleanup(self):
            self.stop_distance_measurement()
            if self._is_available:
                GPIO.cleanup((self.TRIG, self.ECHO)) if not DEBUG else None
                logger.info(LogMessage.cleanup_success.format(object=self.object))
# endregion


if __name__ == "__main__":
    robot = Findee()
    print(f"Hostname: {robot.get_hostname()}")
    robot.ultrasonic.start_distance_measurement(0.1)
    while True:
        print(robot.ultrasonic.get_last_distance())
        time.sleep(0.05)
