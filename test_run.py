"""
项目验证脚本 - 无需摄像头和硬件即可测试完整逻辑链路
运行: python test_run.py

测试内容:
  1. 依赖库是否安装正确
  2. 各模块能否正常初始化
  3. 决策引擎逻辑是否正确(模拟有人/无人场景)
  4. Web服务是否能启动
  5. 红外/舵机/继电器模拟控制是否响应
"""

import sys
import time
import threading

PASS = "  [PASS]"
FAIL = "  [FAIL]"
INFO = "  [INFO]"


def check(desc, fn):
    try:
        result = fn()
        print(f"{PASS} {desc}" + (f": {result}" if result else ""))
        return True
    except Exception as e:
        print(f"{FAIL} {desc}: {e}")
        return False


def test_imports():
    print("\n[1] 检查依赖库...")
    libs = [
        ("ultralytics (YOLO)", lambda: __import__("ultralytics")),
        ("opencv-python", lambda: __import__("cv2")),
        ("flask", lambda: __import__("flask")),
        ("numpy", lambda: __import__("numpy")),
    ]
    results = []
    for name, fn in libs:
        results.append(check(name, fn))
    return all(results)


def test_modules():
    print("\n[2] 检查模块初始化...")
    ok = True
    ok &= check("config 加载", lambda: __import__("config") and "OK")
    ok &= check("RelayController 初始化", lambda: (
        __import__("relay_controller").RelayController() and "OK"
    ))
    ok &= check("ServoSwitch 初始化", lambda: (
        __import__("servo_switch").ServoSwitch() and "OK"
    ))
    ok &= check("IRController 初始化", lambda: (
        __import__("ir_controller").IRController() and "OK"
    ))
    ok &= check("DeviceManager 初始化", lambda: (
        __import__("device_manager").DeviceManager() and "OK"
    ))
    ok &= check("TemperatureSensor 初始化", lambda: (
        __import__("sensor").TemperatureSensor() and "OK"
    ))
    ok &= check("LightSensor 初始化", lambda: (
        __import__("light_sensor").LightSensor() and "OK"
    ))
    ok &= check("PresenceFilter 初始化", lambda: (
        __import__("presence_filter").PresenceFilter() and "OK"
    ))
    ok &= check("DataLogger 初始化", lambda: (
        __import__("data_logger").DataLogger() and "OK"
    ))
    return ok


def test_device_control():
    print("\n[3] 检查设备控制逻辑...")
    from device_manager import DeviceManager
    dm = DeviceManager()

    results = []

    # 测试灯光
    dm.set_light(True)
    results.append(check("开灯", lambda: "OK" if dm.state["light"] else (_ for _ in ()).throw(AssertionError("灯未开"))))
    dm.set_light(False)
    results.append(check("关灯", lambda: "OK" if not dm.state["light"] else (_ for _ in ()).throw(AssertionError("灯未关"))))

    # 测试空调
    dm.set_ac(True, "cooling")
    results.append(check("空调制冷", lambda: "OK" if dm.ac_mode == "cooling" else (_ for _ in ()).throw(AssertionError("模式错误"))))
    dm.set_ac(False)
    results.append(check("关空调", lambda: "OK" if dm.ac_mode == "off" else (_ for _ in ()).throw(AssertionError("未关闭"))))

    # 测试电源
    dm.set_power(True)
    results.append(check("通电", lambda: "OK" if dm.state["power"] else (_ for _ in ()).throw(AssertionError("未通电"))))
    dm.set_power(False)
    results.append(check("断电", lambda: "OK" if not dm.state["power"] else (_ for _ in ()).throw(AssertionError("未断电"))))

    dm.cleanup()
    return all(results)


def test_decision_logic():
    print("\n[4] 检查决策引擎逻辑(模拟场景)...")
    import config
    config.NO_PERSON_TIMEOUT = 3  # 缩短到3秒方便测试

    from device_manager import DeviceManager
    from sensor import TemperatureSensor
    from decision_engine import DecisionEngine

    # 用 Mock 替代真实检测器
    class MockDetector:
        def __init__(self):
            self.has_person = False
            self.count = 0
        def get_status(self):
            return {"has_person": self.has_person, "person_count": self.count,
                    "last_detection_time": time.time()}

    mock = MockDetector()
    devices = DeviceManager()
    sensor = TemperatureSensor()
    sensor.start()
    from light_sensor import LightSensor
    light = LightSensor()
    # 模拟光照不足(暗室50lux < LIGHT_DARK_THRESHOLD 150lux)
    # 必须用lock写入，因为read_loop线程会并发修改lux
    with light.lock:
        light.lux = 50.0
    light.start()
    engine = DecisionEngine(mock, devices, sensor, light)
    engine.start()

    results = []

    # 场景1: 有人进入 -> 应该开灯
    # 注意: 有滤波器(需连续N次)，且需要光照不足才开灯
    print(f"{INFO} 模拟有人进入(需连续{config.PRESENCE_ON_THRESHOLD}次检测，光照已设为暗室50lux)...")
    mock.has_person = True
    mock.count = 2
    # 每次read_loop随机波动±20lux，50lux不会超过150阈值，保持暗室状态
    time.sleep(config.PRESENCE_ON_THRESHOLD + 3)
    results.append(check("有人时灯光开启", lambda: "OK" if devices.state["light"] else (_ for _ in ()).throw(AssertionError("灯未自动开"))))
    results.append(check("有人时电源开启", lambda: "OK" if devices.state["power"] else (_ for _ in ()).throw(AssertionError("电源未自动开"))))

    # 场景2: 无人超时 -> 应该关灯断电
    print(f"{INFO} 模拟无人离开(等待{config.NO_PERSON_TIMEOUT}秒超时)...")
    mock.has_person = False
    mock.count = 0
    time.sleep(config.NO_PERSON_TIMEOUT + config.PRESENCE_OFF_THRESHOLD + 3)
    results.append(check("无人超时后灯光关闭", lambda: "OK" if not devices.state["light"] else (_ for _ in ()).throw(AssertionError("灯未自动关"))))
    results.append(check("无人超时后电源断开", lambda: "OK" if not devices.state["power"] else (_ for _ in ()).throw(AssertionError("电源未自动断"))))

    engine.stop()
    sensor.stop()
    light.stop()
    devices.cleanup()

    # 打印决策日志
    if engine.log_history:
        print(f"{INFO} 决策日志:")
        for entry in engine.log_history:
            print(f"       {entry['time']} - {entry['action']}")

    return all(results)


def test_web_server():
    print("\n[5] 检查Web服务...")
    import requests
    from device_manager import DeviceManager
    from sensor import TemperatureSensor
    from decision_engine import DecisionEngine
    import web_server

    class MockDetector:
        def get_status(self):
            return {"has_person": False, "person_count": 0, "last_detection_time": time.time()}
        def get_frame_bytes(self):
            return None

    mock = MockDetector()
    devices = DeviceManager()
    sensor = TemperatureSensor()
    from light_sensor import LightSensor
    light = LightSensor()
    engine = DecisionEngine(mock, devices, sensor, light)
    web_server.init_app(engine, mock)

    # 在后台线程启动Web服务
    t = threading.Thread(
        target=lambda: web_server.app.run(host="127.0.0.1", port=18080,
                                          threaded=True, use_reloader=False),
        daemon=True
    )
    t.start()
    time.sleep(1.5)

    results = []
    try:
        r = requests.get("http://127.0.0.1:18080/api/status", timeout=3)
        results.append(check("GET /api/status 返回200", lambda: "OK" if r.status_code == 200 else (_ for _ in ()).throw(AssertionError(f"状态码{r.status_code}"))))
        data = r.json()
        results.append(check("响应包含devices字段", lambda: "OK" if "devices" in data else (_ for _ in ()).throw(AssertionError("缺少devices"))))
        results.append(check("响应包含sensor字段", lambda: "OK" if "sensor" in data else (_ for _ in ()).throw(AssertionError("缺少sensor"))))

        r2 = requests.post("http://127.0.0.1:18080/api/control",
                           json={"device": "light", "action": "on"}, timeout=3)
        results.append(check("POST /api/control 手动控制", lambda: "OK" if r2.json().get("ok") else (_ for _ in ()).throw(AssertionError("控制失败"))))
    except Exception as e:
        print(f"{FAIL} Web服务请求失败: {e}")
        print(f"{INFO} 提示: 需要安装 requests 库: pip install requests")
        results.append(False)

    devices.cleanup()
    return all(results)


def main():
    print("=" * 50)
    print("  智能教室测控系统 - 项目验证脚本")
    print("=" * 50)

    all_passed = True
    all_passed &= test_imports()
    all_passed &= test_modules()
    all_passed &= test_device_control()
    all_passed &= test_decision_logic()
    all_passed &= test_web_server()

    print("\n" + "=" * 50)
    if all_passed:
        print("  全部测试通过! 项目可以正常运行")
        print("  运行主程序: python main.py")
        print("  浏览器访问: http://localhost:8080")
    else:
        print("  部分测试未通过，请根据上方 [FAIL] 提示排查")
    print("=" * 50)


if __name__ == "__main__":
    main()
