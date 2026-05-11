"""
智能教室/实验室网络化测控系统 - 主程序入口

非侵入式改造方案:
  灯光: 舵机按压墙壁开关 + 光敏电阻反馈闭环
  空调: 红外发射管模拟遥控器
  电源: 继电器控制
  检测: YOLOv8 + 滞回滤波器防误触发
  感知: DHT22温湿度 + BH1750环境光
  界面: Flask B/S监控 + 自动/手动双模式
  日志: CSV数据记录 + 文件日志

课程: 网络化测控技术
"""

import sys
import signal
import logging


def main():
    # 配置基础日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S"
    )
    logger = logging.getLogger("main")

    logger.info("=" * 55)
    logger.info("  智能教室/实验室 网络化测控系统")
    logger.info("  非侵入式改造 + 闭环控制 + 多源传感融合")
    logger.info("=" * 55)

    try:
        from detector import PersonDetector
        from device_manager import DeviceManager
        from sensor import TemperatureSensor
        from light_sensor import LightSensor
        from decision_engine import DecisionEngine
        from data_logger import setup_file_logging
        import web_server
        import config
    except ImportError as e:
        logger.error(f"模块导入失败: {e}")
        logger.error("请先安装依赖: pip install -r requirements.txt")
        sys.exit(1)

    # 启用文件日志
    if config.ENABLE_FILE_LOG:
        setup_file_logging()

    # 初始化
    logger.info("正在初始化系统模块...")
    detector = PersonDetector()
    devices = DeviceManager()
    sensor = TemperatureSensor()
    light_sensor = LightSensor()
    engine = DecisionEngine(detector, devices, sensor, light_sensor)

    def shutdown(sig, frame):
        logger.info("\n正在关闭系统...")
        engine.stop()
        detector.stop()
        sensor.stop()
        light_sensor.stop()
        devices.all_off()
        devices.cleanup()
        logger.info("系统已安全关闭")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # 启动各模块
    logger.info("启动人员检测模块(YOLO)...")
    detector.start()

    logger.info("启动温度传感器模块...")
    sensor.start()

    logger.info("启动光照传感器模块...")
    light_sensor.start()

    logger.info("启动决策引擎...")
    engine.start()

    logger.info("启动Web监控界面...")
    web_server.init_app(engine, detector)

    logger.info(f"系统就绪! 浏览器访问: http://localhost:{config.WEB_PORT}")
    logger.info("按 Ctrl+C 停止系统")

    web_server.start_web()


if __name__ == "__main__":
    main()
