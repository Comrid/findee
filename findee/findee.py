import subprocess
import time
import threading
import multiprocessing as mp
import atexit
import sys

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    datefmt='%Y년 %m월 %d일 %H:%M:%S'
)
logger = logging.getLogger(__name__)

#-Check for uninstalled modules-#
is_uninstall_module_exist: bool = False
try:
    import RPi.GPIO as GPIO # pip install RPi.GPIO
except ImportError as e:
    logger.error(f"RPi.GPIO 모듈이 설치되어 있지 않습니다. RPi.GPIO 설치 후 다시 시도해주세요. {e}")
    logger.error(f"pip install RPi.GPIO 를 통해 설치할 수 있습니다.")
    is_uninstall_module_exist = True

try:
    from picamera2 import Picamera2 # pip install picamera2
except ImportError as e:
    logger.error(f"picamera2 모듈이 설치되어 있지 않습니다. picamera2 설치 후 다시 시도해주세요. {e}")
    logger.error(f"pip install picamera2 를 통해 설치할 수 있습니다.")
    is_uninstall_module_exist = True

try:
    import cv2 # pip install opencv-python
except ImportError as e:
    logger.error(f"opencv-python 모듈이 설치되어 있지 않습니다. opencv-python 설치 후 다시 시도해주세요. {e}")
    logger.error(f"pip install opencv-python 를 통해 설치할 수 있습니다.")
    is_uninstall_module_exist = True

if is_uninstall_module_exist:
    sys.exit(1)
del is_uninstall_module_exist

#-Findee Class-#
class Findee:
    def __init__(self):
        #-GPIO Setting-#
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

        #-Class Setting-#
        self.motor = self.Motor()
        self.camera = self.Camera()
        self.ultrasonic = self.Ultrasonic()

        #-Cleanup-#
        atexit.register(self.cleanup)

    class Motor:
        def __init__(self):
            #-Left Wheel GPIO Pins-#
            self.IN3 = 22  # 왼쪽 모터 방향 1
            self.IN4 = 27  # 왼쪽 모터 방향 2
            self.ENB = 13  # 왼쪽 모터 PWM

            #-Right Wheel GPIO Pins-#
            self.IN1 = 23  # 오른쪽 모터 방향 1
            self.IN2 = 24  # 오른쪽 모터 방향 2
            self.ENA = 12  # 오른쪽 모터 PWM

            #-GPIO Setup-#
            self.chan_list = [self.IN1, self.IN2, self.IN3, self.IN4, self.ENA, self.ENB]
            GPIO.setup(self.chan_list, GPIO.OUT, initial=GPIO.LOW)

            #-PWM Setup-#
            self.rightPWM = GPIO.PWM(self.ENA, 1000); self.rightPWM.start(0)
            self.leftPWM = GPIO.PWM(self.ENB, 1000); self.leftPWM.start(0)

            #-Motor Parameter-#
            self.MOTOR_SPEED = 80
            self.start_time_motor = time.time()

        def pinChange(self, IN1, IN2, IN3, IN4, ENA, ENB):
            self.IN1 = IN1
            self.IN2 = IN2
            self.IN3 = IN3
            self.IN4 = IN4
            self.ENA = ENA
            self.ENB = ENB

        @staticmethod
        def constrain(value, min_value, max_value):
            return max(min(value, max_value), min_value)

        #-Basic Motor Control Method-#
        def control_motors(self, right, left):
            """
            right : 20 ~ 100, -20 ~ -100
            left : -20 ~ -100, 20 ~ 100
            """
            right = (1 if right >= 0 else -1) * self.constrain(abs(right), 20, 100)
            left = (1 if left >= 0 else -1) * self.constrain(abs(left), 20, 100)

            if right == 0:
                self.rightPWM.ChangeDutyCycle(0.0)
                GPIO.output((self.IN1, self.IN2), GPIO.LOW)
            else:
                self.rightPWM.ChangeDutyCycle(100.0)
                GPIO.output(self.IN1, GPIO.HIGH if right > 0 else GPIO.LOW)
                GPIO.output(self.IN2, GPIO.LOW if right > 0 else GPIO.HIGH)
                time.sleep(0.02)
                self.rightPWM.ChangeDutyCycle(abs(right))

            if left == 0:
                self.leftPWM.ChangeDutyCycle(0.0)
                GPIO.output((self.IN3, self.IN4), GPIO.LOW)
            else:
                self.leftPWM.ChangeDutyCycle(100.0)
                GPIO.output(self.IN3, GPIO.HIGH if left > 0 else GPIO.LOW)
                GPIO.output(self.IN4, GPIO.LOW if left > 0 else GPIO.HIGH)
                time.sleep(0.02)
                self.leftPWM.ChangeDutyCycle(abs(left))

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
            self.control_motors(0, 0)

        def cleanup(self):
            self.stop()
            self.rightPWM.stop()
            self.leftPWM.stop()
            GPIO.cleanup(self.chan_list)

    class Camera:
        def __init__(self):
            self._is_available = False
            self.picam2 = None

            try:
                from picamera2 import Picamera2 # pip install picamera2
                self.picam2 = Picamera2()
                self.picam2.preview_configuration.main.size = (640, 480)
                self.picam2.preview_configuration.main.format = "RGB888"
                self.picam2.configure("preview")
                self.picam2.start()
            except ImportError as e:
                logger.error(f"picamera2 모듈이 설치되어 있지 않습니다. picamera2 설치 후 다시 시도해주세요. {e}")
                self._is_available = False
                sys.exit(1)
            except RuntimeError as e:
                logger.error(f"picamera2 초기화 중 오류가 발생했습니다. 카메라 연결을 확인해주세요. {e}")
                self._is_available = False
            except Exception as e:
                logger.error(f"카메라 초기화 중 오류가 발생했습니다. {e}")
                self._is_available = False
            else:
                self._is_available = True
                logger.info("카메라 초기화 완료")

        def get_frame(self):
            if self._is_available:
                frame = self.picam2.capture_array()
                return frame
            else:
                logger.error("카메라가 연결되지 않았습니다. 프레임을 가져올 수 없습니다.")
                return None

        def camera_test(self):
            process = subprocess.Popen(
                ['libcamera-hello'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            for line in process.stdout:
                print(line, end='')
            process.wait()
            if process.returncode != 0:
                print(f"\n[오류] libcamera-hello 종료 코드: {process.returncode}")

        def cleanup(self):
            if self._is_available == True:
                self.picam2.stop()
                del self.picam2

    class Ultrasonic:
        def __init__(self):
            # GPIO Pin Number
            self.TRIG = 5
            self.ECHO = 6

            # Ultrasonic Sensor Parameter
            self.SOUND_SPEED = 34300
            self.TRIGGER_PULSE = 0.00001 # 10us
            self.TIMEOUT = 30 # 30ms
            self.last_distance = None

            # GPIO Pin Setting
            GPIO.setup(self.TRIG, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(self.ECHO, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)



        def get_last_distance(self) -> float | None:
            return self.last_distance

        def get_distance(self) -> float | None:
            #-Trigger-#
            GPIO.output(self.TRIG, GPIO.HIGH)
            time.sleep(self.TRIGGER_PULSE)
            GPIO.output(self.TRIG, GPIO.LOW)

            #-Measure Distance-#
            start_time = time.time()
            r = GPIO.wait_for_edge(self.ECHO, GPIO.FALLING, timeout=self.TIMEOUT)
            end_time = time.time()

            if r is None:
                #-Timeout-#
                return None
            else:
                #-Measure Success-#
                duration = end_time - start_time
                distance = (duration * self.SOUND_SPEED) / 2
                self.last_distance = distance
                return distance

        def cleanup(self):
            GPIO.cleanup(self.TRIG, self.ECHO)

    def cleanup(self):
        self.motor.cleanup()
        self.camera.cleanup()
        self.ultrasonic.cleanup()

    def __del__(self):
        self.cleanup()