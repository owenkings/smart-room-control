"""
智能教室/实验室网络化测控系统 — Web 版入口

运行模式:
  树莓派 (Pi mode)  — 使用真实硬件传感器和执行器
  PC 模拟 (PC mode) — 使用 stub 类返回合成数据，便于开发调试

启动:
  python main.py

课程: 网络化测控技术
"""

import sys
import signal
import logging
import random
import time
import threading

# ---------------------------------------------------------------------------
# 日志配置
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


# ---------------------------------------------------------------------------
# 平台检测: 尝试导入树莓派专用库判断运行环境
# ---------------------------------------------------------------------------
def _detect_platform() -> str:
    """检测运行平台，返回 'pi' 或 'pc'。"""
    try:
        import lgpio  # noqa: F401
        return "pi"
    except ImportError:
        pass
    try:
        import gpiozero  # noqa: F401
        return "pi"
    except ImportError:
        pass
    return "pc"


PLATFORM = _detect_platform()


# ---------------------------------------------------------------------------
# PC 模式 Stub 类 — 返回合成数据，无硬件依赖
# ---------------------------------------------------------------------------

class StubTemperatureSensor:
    """模拟温湿度传感器，返回随机合成数据。"""

    def __init__(self):
        self._running = False

    def start(self):
        self._running = True
        logger.info("[Stub] 温湿度传感器已启动 (模拟)")

    def stop(self):
        self._running = False

    def read_once(self):
        return (
            round(random.uniform(22.0, 26.0), 1),
            round(random.uniform(40.0, 60.0), 1),
        )

    def get_status(self):
        temp, hum = self.read_once()
        return {"temperature": temp, "humidity": hum}


class StubLightSensor:
    """模拟光照传感器，返回随机合成数据。"""

    def __init__(self):
        self._running = False
        self._lux = 300.0

    def start(self):
        self._running = True
        logger.info("[Stub] 光照传感器已启动 (模拟)")

    def stop(self):
        self._running = False

    def read_lux(self):
        self._lux = round(random.uniform(100.0, 500.0), 1)
        return self._lux

    def is_dark(self):
        return self._lux < 150.0

    def get_status(self):
        return {"lux": self.read_lux(), "is_dark": self.is_dark()}


class StubServoController:
    """模拟舵机控制器，所有操作为 no-op。"""

    def __init__(self):
        self._angle = 90
        self._calibration = {
            "angle_on": 60,
            "angle_off": 120,
            "angle_neutral": 90,
            "action_duration": 0.5,
        }

    def move_to(self, angle: int):
        self._angle = max(0, min(180, angle))
        logger.debug("[Stub] 舵机移动到 %d°", self._angle)

    def press_on(self):
        logger.info("[Stub] 舵机执行开灯动作 (模拟)")

    def press_off(self):
        logger.info("[Stub] 舵机执行关灯动作 (模拟)")

    def calibrate(self, preset: str, angle: int):
        if preset in ("on", "off", "neutral"):
            self._calibration[f"angle_{preset}"] = angle

    def save_calibration(self):
        pass

    def load_calibration(self):
        return self._calibration.copy()

    def get_status(self):
        return {"angle": self._angle, "calibration": self._calibration.copy()}

    def cleanup(self):
        logger.info("[Stub] 舵机资源已释放 (模拟)")


class StubIRController:
    """模拟红外控制器，所有操作为 no-op。"""

    def __init__(self):
        self._commands: dict = {}

    def start_learning(self, command_name: str, timeout: float = 10.0):
        logger.info("[Stub] 红外学习: %s (模拟, 超时 %.1fs)", command_name, timeout)
        return {"success": False, "reason": "PC 模拟模式不支持红外学习"}

    def send_command(self, command_name: str, repeat: int = 3):
        logger.info("[Stub] 红外发送: %s (模拟)", command_name)
        return command_name in self._commands

    def list_commands(self):
        return list(self._commands.keys())

    def delete_command(self, command_name: str):
        return self._commands.pop(command_name, None) is not None

    def save_commands(self):
        pass

    def load_commands(self):
        return self._commands.copy()

    def cleanup(self):
        logger.info("[Stub] 红外控制器资源已释放 (模拟)")


class StubDetector:
    """模拟人员检测器，生成占位帧用于 Web 推流测试。"""

    def __init__(self):
        self._running = False
        self._model_name = "yolov8n.pt"

    def start(self):
        self._running = True
        logger.info("[Stub] 人员检测器已启动 (模拟)")

    def stop(self):
        self._running = False

    def get_person_count(self):
        return 0

    def get_latest_frame(self):
        """生成一个带时间戳的占位帧，确保 Web 推流正常工作"""
        import numpy as np
        import cv2
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # 深色背景 + 文字
        frame[:] = (30, 30, 40)
        font = cv2.FONT_HERSHEY_SIMPLEX
        lines = [
            "Smart Room Control",
            "PC Simulation Mode",
            time.strftime("%Y-%m-%d %H:%M:%S"),
            f"Model: {self._model_name}",
            "No camera detected",
        ]
        y0 = 160
        for i, line in enumerate(lines):
            tw = cv2.getTextSize(line, font, 0.65, 1)[0][0]
            x = (640 - tw) // 2
            color = (0, 200, 120) if i < 2 else (150, 150, 150)
            cv2.putText(frame, line, (x, y0 + i * 40), font, 0.65, color, 1)
        return frame

    def switch_model(self, path):
        logger.info("[Stub] 模型切换: %s", path)
        self._model_name = path
        return {"ok": True}

    def get_status(self):
        return {
            "person_count": 0,
            "running": self._running,
            "camera_backend": "none (PC mode)",
            "model_name": self._model_name,
            "stream_fps": 15,
            "infer_ms": 0,
        }


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------

def main():
    logger.info("=" * 55)
    logger.info("  智能教室/实验室 网络化测控系统")
    logger.info("  非侵入式改造 + 闭环控制 + 多源传感融合")
    logger.info("  运行模式: %s", "树莓派 (Pi)" if PLATFORM == "pi" else "PC 模拟")
    logger.info("=" * 55)

    # ------------------------------------------------------------------
    # 构建组件: Pi 模式使用真实硬件类, PC 模式使用 Stub
    # ------------------------------------------------------------------
    if PLATFORM == "pi":
        logger.info("检测到树莓派环境，使用真实硬件模块")
        from src.sensor_dht import TemperatureSensor
        from src.sensor_light import LightSensor
        from src.servo import ServoController
        from src.ir_controller import IRController
        from src.detector import Detector

        temperature_sensor = TemperatureSensor()
        light_sensor = LightSensor()
        servo = ServoController()
        ir_controller = IRController()
        detector = Detector()
    else:
        logger.info("PC 模拟模式，使用 Stub 组件返回合成数据")
        temperature_sensor = StubTemperatureSensor()
        light_sensor = StubLightSensor()
        servo = StubServoController()
        ir_controller = StubIRController()
        detector = StubDetector()

    # ------------------------------------------------------------------
    # 构建决策引擎
    # ------------------------------------------------------------------
    from src.decision_engine import DecisionEngine

    engine = DecisionEngine(
        temperature_sensor=temperature_sensor,
        light_sensor=light_sensor,
        detector=detector,
        servo=servo,
        ir_controller=ir_controller,
    )

    # ------------------------------------------------------------------
    # 启动引擎
    # ------------------------------------------------------------------
    logger.info("启动决策引擎...")
    engine.start()

    # ------------------------------------------------------------------
    # 创建 Web 应用
    # ------------------------------------------------------------------
    from src.web_server import create_app

    app, socketio = create_app(engine)

    # ------------------------------------------------------------------
    # 信号处理: 优雅关闭
    # ------------------------------------------------------------------
    def _shutdown(signum, frame):
        sig_name = signal.Signals(signum).name
        logger.info("收到信号 %s，正在关闭系统...", sig_name)
        engine.cleanup()
        logger.info("系统已安全关闭")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # ------------------------------------------------------------------
    # 启动 Web 服务
    # ------------------------------------------------------------------
    host = "0.0.0.0"
    port = 5000
    logger.info("Web 服务启动: http://%s:%d", host, port)
    logger.info("按 Ctrl+C 停止系统")

    socketio.run(app, host=host, port=port, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()
