import RPi.GPIO as GPIO # pip install RPi.GPIO
import subprocess
import time
from picamera2 import Picamera2 # pip install picamera2
import threading
import cv2 # pip install opencv-python
import multiprocessing as mp


class Findee:
    def __init__(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

        self.motor = self.Motor()
        self.camera = self.Camera()
        self.ultrasonic = self.Ultrasonic()

    class Motor:
        def __init__(self):
            # Left Wheel
            self.IN3 = 22  # 왼쪽 모터 방향 1
            self.IN4 = 27  # 왼쪽 모터 방향 2
            self.ENB = 13  # 왼쪽 모터 PWM

            # Right Wheel
            self.IN1 = 23  # 오른쪽 모터 방향 1
            self.IN2 = 24  # 오른쪽 모터 방향 2
            self.ENA = 12  # 오른쪽 모터 PWM

            # GPIO Setting
            GPIO.setup(self.IN1, GPIO.OUT)
            GPIO.setup(self.IN2, GPIO.OUT)
            GPIO.setup(self.IN3, GPIO.OUT)
            GPIO.setup(self.IN4, GPIO.OUT)
            GPIO.setup(self.ENA, GPIO.OUT)
            GPIO.setup(self.ENB, GPIO.OUT)

            # PWM Setting
            self.rightPWM = GPIO.PWM(self.ENA, 1000)
            self.leftPWM = GPIO.PWM(self.ENB, 1000)
            self.rightPWM.start(0)
            self.leftPWM.start(0)

            # Motor Parameter
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

        # Basic Motor Control Method
        def control_motors(self, right, left):
            """
            right : 20 ~ 100, -20 ~ -100
            left : -20 ~ -100, 20 ~ 100
            """
            right = (1 if right >= 0 else -1) * self.constrain(abs(right), 20, 100)
            left = (1 if left >= 0 else -1) * self.constrain(abs(left), 20, 100)

            if right == 0:
                self.rightPWM.ChangeDutyCycle(0)
                GPIO.output(self.IN1, GPIO.LOW)
                GPIO.output(self.IN2, GPIO.LOW)
            else:
                self.rightPWM.ChangeDutyCycle(100.0)
                GPIO.output(self.IN1, GPIO.HIGH if right > 0 else GPIO.LOW)
                GPIO.output(self.IN2, GPIO.LOW if right > 0 else GPIO.HIGH)
                time.sleep(0.02)
                self.rightPWM.ChangeDutyCycle(abs(right))

            if left == 0:
                self.leftPWM.ChangeDutyCycle(0)
                GPIO.output(self.IN3, GPIO.LOW)
                GPIO.output(self.IN4, GPIO.LOW)
            else:
                self.leftPWM.ChangeDutyCycle(100.0)
                GPIO.output(self.IN3, GPIO.HIGH if left > 0 else GPIO.LOW)
                GPIO.output(self.IN4, GPIO.LOW if left > 0 else GPIO.HIGH)
                time.sleep(0.02)
                self.leftPWM.ChangeDutyCycle(abs(left))

        # Derived Motor Control Method
        # 직진, 후진, 제자리 회전, 곡선 회전
        def move_forward(self, speed):
            self.control_motors(speed, speed)

        def move_backward(self, speed):
            self.control_motors(-speed, -speed)

        def turn_left(self, speed):
            self.control_motors(-speed, speed)

        def turn_right(self, speed):
            self.control_motors(speed, -speed)

        def smooth_turn_left(self, speed, angle):
            angle = self.constrain(angle, 0, 60)
            ratio = 1.0 - (angle / 60.0) * 0.5
            self.control_motors(speed, speed * ratio)

        def smooth_turn_right(self, speed, angle):
            angle = self.constrain(angle, 0, 60)
            ratio = 1.0 - (angle / 60.0) * 0.5
            self.control_motors(speed * ratio, speed)

        def stop(self):
            self.control_motors(0, 0)
            
        def cleanup(self):
            """GPIO 정리"""
            self.stop()
            self.rightPWM.stop()
            self.leftPWM.stop()
            GPIO.cleanup()

    class Camera:
        def __init__(self):
            self.picam2 = Picamera2()
            self.picam2.preview_configuration.main.size = (640, 480)
            self.picam2.preview_configuration.main.format = "RGB888"
            self.picam2.configure("preview")
            self.picam2.start()
        def get_frame(self):
            frame = self.picam2.capture_array()
            return frame
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
            
            
    class Ultrasonic:
        def __init__(self):
            # GPIO Pin Number
            self.TRIG = 5
            self.ECHO = 6

            # Ultrasonic Sensor Parameter
            self.SOUND_SPEED = 34300
            self.TRIGGER_PULSE = 0.00001
            self.TIMEOUT = 0.1
            self.INTERVAL = 0.1
            self.RUNNING = False

            # Ultrasonic Sensor Variable
            self.distance = None
            self.echo_start_time = None
            
            # GPIO Pin Setting
            GPIO.setup(self.TRIG, GPIO.OUT)
            GPIO.setup(self.ECHO, GPIO.IN)
            GPIO.output(self.TRIG, GPIO.LOW)

            # self.sonic_process = mp.Process(target=self.get_distance)
            # self.sonic_process.start()
            
            # try:
            #     GPIO.remove_event_detect(self.ECHO)
            # except:
            #     pass
            #GPIO.add_event_detect(self.ECHO, GPIO.BOTH, callback=self.echo_callback)

        def sonic_trigger(self):
            GPIO.output(self.TRIG, GPIO.HIGH)
            time.sleep(self.TRIGGER_PULSE)
            GPIO.output(self.TRIG, GPIO.LOW)

        def get_distance(self):
            self.sonic_trigger()

            # ECHO 신호 대기 (타임아웃 적용)
            start_time = time.time()
            timeout_start = start_time
            
            # ECHO 신호 시작 대기
            while GPIO.input(self.ECHO) == 0:
                start_time = time.time()
                if start_time - timeout_start > self.TIMEOUT:
                    return None  # 타임아웃 발생
            
            # ECHO 신호 종료 대기
            while GPIO.input(self.ECHO) == 1:
                end_time = time.time()
                if end_time - start_time > self.TIMEOUT:
                    return None  # 타임아웃 발생

            # 거리 계산 (음속 * 시간 / 2)
            duration = end_time - start_time
            distance = (duration * self.SOUND_SPEED) / 2

            # 유효 범위 체크 (2cm ~ 400cm)
            if 2 <= distance <= 400:
                return round(distance, 1)
            return None