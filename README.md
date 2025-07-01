# Findee 🚗

[![PyPI version](https://badge.fury.io/py/findee.svg)](https://badge.fury.io/py/findee)
[![Python](https://img.shields.io/pypi/pyversions/findee.svg)](https://pypi.org/project/findee/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://pepy.tech/badge/findee)](https://pepy.tech/project/findee)

**Findee**는 Pathfinder의 라즈베리파이 제로 2 W 기반의 자율주행 차량 플랫폼입니다. 모터 제어, 카메라, 초음파 센서를 통합하여 로보틱스 프로젝트를 쉽게 구현할 수 있도록 도와줍니다.

## ✨ 주요 기능

- 🚗 **모터 제어**: DC 모터를 이용한 전진, 후진, 회전 제어
- 📷 **카메라**: Picamera2를 이용한 실시간 영상 처리
- 📡 **초음파 센서**: 거리 측정 및 장애물 감지
- 🎯 **통합 플랫폼**: 하나의 클래스로 모든 하드웨어 제어

## 🔧 하드웨어 요구사항

### 사용 하드웨어
- **라즈베리파이 제로 2 W**
- **라즈베리파이 카메라 모듈 V2** 또는 호환 카메라
- **DC 모터 2개** (바퀴용)
- **L298N 모터 드라이버**
- **HC-SR04 초음파 센서**
- **점퍼 와이어** 및 **브레드보드**

## 📦 설치 방법

### 1. 기본 설치
```bash
pip install findee
```
### 1-1. 업데이트
```bash
pip install --upgrade findee
```

### 2. 필수 라이브러리 설치
```bash
pip install opencv-python RPi.GPIO picamera2
```

## 🚀 사용법

### 1. 기본 예제
```python
from findee import Findee

# Findee 객체 생성
robot = Findee()

try:
    # 2초간 전진
    robot.motor.move_forward(50)
    time.sleep(2)

    # 1초간 우회전
    robot.motor.turn_right(30)
    time.sleep(1)

    # 정지
    robot.motor.stop()

    # 거리 측정
    distance = robot.ultrasonic.get_distance()
    print(f"거리: {distance}cm")

    # 카메라 프레임 캡처
    frame = robot.camera.get_frame()
    print(f"프레임 크기: {frame.shape}")

finally:
    # 리소스 정리
    robot.motor.cleanup()
```

### 2. 자율주행 예제
```python
import time
from findee import Findee

def autonomous_drive():
    robot = Findee()

    try:
        while True:
            # 거리 측정
            distance = robot.ultrasonic.get_distance()

            if distance is None:
                print("센서 오류")
                continue

            if distance > 20:  # 20cm 이상이면 전진
                robot.motor.move_forward(40)
            elif distance > 10:  # 10-20cm면 천천히
                robot.motor.move_forward(20)
            else:  # 10cm 이하면 회전
                robot.motor.turn_right(30)
                time.sleep(0.5)
                robot.motor.stop()

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("프로그램 종료")
    finally:
        robot.motor.cleanup()

if __name__ == "__main__":
    autonomous_drive()
```

## 📖 API 문서

### 1. Findee 클래스
메인 클래스로 모든 하드웨어 구성요소에 접근할 수 있습니다.

```python
robot = Findee()
robot.motor      # Motor 클래스 인스턴스
robot.camera     # Camera 클래스 인스턴스
robot.ultrasonic # Ultrasonic 클래스 인스턴스
```

### 2. Motor 클래스
DC 모터 제어를 담당합니다.

#### 기본 제어
- `move_forward(speed)`: 전진 (speed: 20-100)
- `move_backward(speed)`: 후진 (speed: 20-100)
- `turn_left(speed)`: 제자리 좌회전 (speed: 20-100)
- `turn_right(speed)`: 제자리 우회전 (speed: 20-100)
- `stop()`: 정지
- `cleanup()`: GPIO 정리

#### 고급 제어
- `curve_left(speed, angle)`: 좌회전 커브 (angle: 0-60)
- `curve_right(speed, angle)`: 우회전 커브(angle: 0-60)
- `control_motors(right, left)`: 개별 모터 제어 (-100 ~ 100)

### 3. Camera 클래스
라즈베리파이 카메라 제어를 담당합니다.

- `get_frame()`: 현재 프레임 반환 (numpy array)
- `camera_test()`: 카메라 연결 테스트

### 4. Ultrasonic 클래스
HC-SR04 초음파 센서 제어를 담당합니다.

- `get_distance()`: 거리 측정 반환 (cm, None if error)
- 측정 범위: 2-400cm
- 정확도: ±1cm


### 이슈 리포트
버그나 기능 요청은 [GitHub Issues](https://github.com/Comrid/findee/issues)를 이용해주세요.

## 📄 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 👥 제작자

- **Pathfinder** - *초기 개발* - [Comrid](https://github.com/Comrid)

## 🙏 감사의 말

- 라즈베리파이 재단의 훌륭한 하드웨어
- 오픈소스 커뮤니티의 지원

---


**즐거운 로보틱스 프로젝트 되세요!** 🚀