import logging

class ColoredFormatter(logging.Formatter):
    """컬러 로깅 포매터"""

    # ANSI 색깔 코드
    COLORS = {
        'DEBUG': '\033[36m',    # 청록색
        'INFO': '\033[32m',     # 초록색
        'WARNING': '\033[33m',  # 노란색
        'ERROR': '\033[31m',    # 빨간색
        'CRITICAL': '\033[35m', # 보라색
        'RESET': '\033[0m'      # 리셋
    }

    def format(self, record):
        # 원본 포맷 적용
        message = super().format(record)

        # 레벨명에 색깔 적용
        level_color = self.COLORS.get(record.levelname, '')
        reset = self.COLORS['RESET']

        # 색깔 적용된 메시지 반환
        return f"{level_color}[{record.levelname}]{reset} {message}"

# 로거 설정
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter('%(asctime)s - %(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)  # DEBUG부터 모든 레벨 출력

print("=== 🎨 컬러 로깅 테스트 ===\n")

# 모든 로깅 레벨 테스트
logger.debug("🔍 DEBUG: 디버깅 정보입니다 (청록색)")
logger.info("ℹ️  INFO: 일반 정보 메시지입니다 (초록색)")
logger.warning("⚠️  WARNING: 경고 메시지입니다 (노란색)")
logger.error("❌ ERROR: 오류가 발생했습니다 (빨간색)")
logger.critical("🚨 CRITICAL: 심각한 오류입니다! (보라색)")

print("\n=== 🚗 findee 시뮬레이션 ===\n")

# findee 스타일 로깅 시뮬레이션
logger.info("🔧 GPIO 초기화 완료")
logger.info("📷 카메라 연결 성공")
logger.info("📡 초음파 센서 준비 완료")
logger.warning("⚡ 배터리 잔량 부족 (20%)")
logger.info("🚗 자율주행 시작")
logger.debug("📊 거리: 45.2cm")
logger.debug("📊 거리: 32.1cm")
logger.debug("📊 거리: 18.7cm")
logger.warning("🛑 장애물 감지! 회전 시작")
logger.info("↩️  우회전 완료")
logger.error("📷 카메라 연결 끊김")
logger.critical("🚨 시스템 과열! 즉시 정지 필요")
logger.info("🔌 모든 장치 정리 완료")
logger.info("✅ 프로그램 종료")

print("\n=== 📊 색깔 코드 정보 ===")
print("DEBUG    (청록색): \\033[36m")
print("INFO     (초록색): \\033[32m")
print("WARNING  (노란색): \\033[33m")
print("ERROR    (빨간색): \\033[31m")
print("CRITICAL (보라색): \\033[35m")
print("RESET    (리셋):   \\033[0m")