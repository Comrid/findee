from __future__ import annotations
import time
import atexit
import sys
import numpy as np
import logging
import os

#-Colored Formatter for Logging-#
class ColoredFormatter(logging.Formatter):
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

#-Logger Setting-#
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter('%(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)
logging.getLogger('picamera2').setLevel(logging.WARNING)

#-Check for uninstalled modules & Platform-#
try:
    is_initialize_error_occured: bool = False

    # Check for RPi.GPIO
    try:
        import RPi.GPIO as GPIO # pip install RPi.GPIO
    except ImportError:
        logger.error(f"findee 모듈을 사용하기 위해 RPi.GPIO 모듈이 필요합니다. pip install RPi.GPIO 를 통해 설치할 수 있습니다.")
        is_initialize_error_occured = True

    # Check for picamera2
    try:
        from picamera2 import Picamera2 # pip install picamera2
    except ImportError:
        logger.error(f"findee 모듈을 사용하기 위해 picamera2 모듈이 필요합니다. pip install picamera2 를 통해 설치할 수 있습니다.")
        is_initialize_error_occured = True

    # Check for opencv-python
    try:
        import cv2 # pip install opencv-python
    except ImportError:
        logger.error(f"findee 모듈을 사용하기 위해 opencv-python 모듈이 필요합니다. pip install opencv-python 를 통해 설치할 수 있습니다.")
        is_initialize_error_occured = True

    # Check for Platform
    platform = sys.platform
    if platform == "win32":
        logger.error(f"findee 모듈은 Windows 플랫폼에서는 사용할 수 없습니다. {platform} 플랫폼은 지원하지 않습니다.")
        is_initialize_error_occured = True

    if is_initialize_error_occured:
        raise Exception()
except Exception as e:
    sys.exit(1)

#-Findee Class Definition-#
class Findee:
    def __init__(self, safe_mode: bool = False):
        # GPIO Setting
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

        # Class Variables
        self.safe_mode = safe_mode
        self._component_status = {
            "motor": False,
            "camera": False,
            "ultrasonic": False
        }

        # Class Initialization
        try:
            self.motor = self.Motor(self)
            self._component_status["motor"] = self.motor._is_available
        except Exception as e:
            logger.error(f"모터 클래스 생성 실패: {e}")

        try:
            self.camera = self.Camera(self)
            self._component_status["camera"] = self.camera._is_available
        except Exception as e:
            logger.error(f"카메라 클래스 생성 실패: {e}")

        try:
            self.ultrasonic = self.Ultrasonic(self)
            self._component_status["ultrasonic"] = self.ultrasonic._is_available
        except Exception as e:
            logger.error(f"초음파 센서 클래스 생성 실패: {e}")

        #-Cleanup-#
        atexit.register(self.cleanup)

        # Time delay for Stabilization
        time.sleep(0.1)

    def get_status(self) -> dict:
        return self._component_status.copy()

    #-Motor Class Definition-#
    class Motor:
        def __init__(self, parent_instance):
            self.parent = parent_instance
            #-Class Usability-#
            self._is_available = False

            #-Left Wheel GPIO Pins-#
            self.IN3 = 22  # 왼쪽 모터 방향 1
            self.IN4 = 27  # 왼쪽 모터 방향 2
            self.ENB = 13  # 왼쪽 모터 PWM

            #-Right Wheel GPIO Pins-#
            self.IN1 = 23  # 오른쪽 모터 방향 1
            self.IN2 = 24  # 오른쪽 모터 방향 2
            self.ENA = 12  # 오른쪽 모터 PWM

            try:
                #-GPIO Setup-#
                self.chan_list = [self.IN1, self.IN2, self.IN3, self.IN4, self.ENA, self.ENB]
                GPIO.setup(self.chan_list, GPIO.OUT, initial=GPIO.LOW)

                #-PWM Setup-#
                self.rightPWM = GPIO.PWM(self.ENA, 1000); self.rightPWM.start(0)
                self.leftPWM = GPIO.PWM(self.ENB, 1000); self.leftPWM.start(0)
            except Exception as e:
                if self.parent.safe_mode:
                    logger.warning(f"[Safe Mode] 모터 초기화에 실패했습니다. 모터 관련 함수를 사용할 수 없습니다. {e}")
                    self._is_available = False
                else:
                    logger.error(f"모터 초기화에 실패했습니다. 프로그램을 종료합니다. {e}")
                    sys.exit(1)
            else:
                logger.info("모터 초기화 성공!")
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
                    GPIO.output(self.IN3, GPIO.HIGH if left > 0 else GPIO.LOW)
                    GPIO.output(self.IN4, GPIO.LOW if left > 0 else GPIO.HIGH)
                    time.sleep(0.02)
                    self.leftPWM.ChangeDutyCycle(abs(left))
            except Exception as e:
                logger.warning(f"모터 제어 중 오류가 발생했습니다. {e}")
                return False
            else:
                return True

        #-Derived Motor Control Method-#
        # Straight, Backward
        def move_forward(self, speed : float, time_sec : float = None):
            self.control_motors(speed, speed)
            if time_sec is not None:
                time.sleep(time_sec)
                self.stop()

        def move_backward(self, speed : float, time_sec : float = None):
            self.control_motors(-speed, -speed)
            if time_sec is not None:
                time.sleep(time_sec)
                self.stop()

        # Rotation
        def turn_left(self, speed : float, time_sec : float = None):
            self.control_motors(-speed, speed)
            if time_sec is not None:
                time.sleep(time_sec)
                self.stop()

        def turn_right(self, speed : float, time_sec : float = None):
            self.control_motors(speed, -speed)
            if time_sec is not None:
                time.sleep(time_sec)
                self.stop()

        # Curvilinear Rotation
        def curve_left(self, speed : float, angle : int, time_sec : float = None):
            angle = self.constrain(angle, 0, 60)
            ratio = 1.0 - (angle / 60.0) * 0.5
            self.control_motors(speed, speed * ratio)
            if time_sec is not None:
                time.sleep(time_sec)
                self.stop()

        def curve_right(self, speed : float, angle : int, time_sec : float = None):
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
            logger.info("Motor      Cleanup Successfully!")

    #-Camera Class Definition-#
    class Camera:
        def __init__(self, parent_instance):
            # Parent Instance
            self.parent = parent_instance

            # Class Usability
            self._is_available = False

            # Camera Object
            self.picam2 = None

            try:
                os.environ['LIBCAMERA_LOG_FILE'] = '/dev/null' # disable logging
                self.picam2 = Picamera2()
                self.picam2.preview_configuration.main.size = (640, 480)
                self.picam2.preview_configuration.main.format = "RGB888"
                self.picam2.configure("preview")
                self.picam2.start()
            except Exception as e:
                if self.parent.safe_mode:
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

        #-Cleanup-#
        def cleanup(self):
            if self._is_available:
                self.picam2.stop()
                del self.picam2
                logger.info("Camera     Cleanup Successfully!")

    #-Ultrasonic Class Definition-#
    class Ultrasonic:
        def __init__(self, parent_instance):
            # Parent Instance
            self.parent = parent_instance

            # Class Usability
            self._is_available = False

            # GPIO Pin Number
            self.TRIG = 5
            self.ECHO = 6

            # Ultrasonic Sensor Parameter
            self.SOUND_SPEED = 34300
            self.TRIGGER_PULSE = 0.00001 # 10us
            self.TIMEOUT = 0.03 # 30ms
            self.last_distance: float | None = None

            try:
                # GPIO Pin Setting
                GPIO.setup(self.TRIG, GPIO.OUT, initial=GPIO.LOW)
                GPIO.setup(self.ECHO, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            except Exception as e:
                if self.parent.safe_mode:
                    logger.warning(f"[Safe Mode] 초음파 센서 초기화에 실패했습니다. 초음파 센서 관련 함수를 사용할 수 없습니다. {e}")
                    self._is_available = False
                else:
                    logger.error(f"초음파 센서 초기화에 실패했습니다. 프로그램을 종료합니다. {e}")
                    sys.exit(1)
            else:
                logger.info("초음파 센서 초기화 성공!")
                self._is_available = True

        #-Get Last Distance from Ultrasonic Sensor-#
        def get_last_distance(self) -> float | None:
            return self.last_distance

        #-Get Distance from Ultrasonic Sensor-#
        def get_distance(self) -> float | None:
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

                #r = GPIO.wait_for_edge(self.ECHO, GPIO.FALLING, timeout=self.TIMEOUT)

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
                logger.info("Ultrasonic Cleanup Successfully!")

    #-Cleanup-#
    def cleanup(self):
        self.motor.cleanup()
        self.camera.cleanup()
        self.ultrasonic.cleanup()
        logger.info("프로그램이 정상적으로 종료되었습니다.")