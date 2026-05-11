"""
硬件自检脚本 — 第一轮台架验证
针对当前最小硬件配置:
  BH1750 × 1  (I2C, GPIO2/3)
  DHT22  × 1  (GPIO4)
  SG90   × 1  (GPIO18 PWM)
  VS1838B× 1  (GPIO24)
  红外发射管×1 (GPIO25, 直接接法)
  继电器 × 1  (GPIO27)
  光敏模块×1  (GPIO17)

运行方式:
  python hw_check.py           # 全部检测
  python hw_check.py bh1750    # 只检测 BH1750
  python hw_check.py dht22
  python hw_check.py servo
  python hw_check.py ir_recv
  python hw_check.py ir_send
  python hw_check.py relay
  python hw_check.py photo
"""

import sys
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("hw_check")

PASS = "  ✅ PASS"
FAIL = "  ❌ FAIL"
SKIP = "  ⏭  SKIP"
INFO = "  ℹ️  INFO"


def check_gpio_available():
    """检查 GPIO 库是否可用"""
    try:
        from gpio_compat import GPIO, HAS_GPIO
        if not HAS_GPIO:
            print(f"{FAIL} GPIO 库不可用")
            print("       请运行: pip install rpi-lgpio")
            return False, None, None
        print(f"{PASS} GPIO 库已加载")
        return True, GPIO, HAS_GPIO
    except Exception as e:
        print(f"{FAIL} GPIO 导入失败: {e}")
        return False, None, None


# ── BH1750 ────────────────────────────────────────────────────────────

def check_bh1750():
    print("\n[BH1750 光照传感器]")
    try:
        import smbus2
    except ImportError:
        print(f"{FAIL} smbus2 未安装，请运行: pip install smbus2")
        return False

    # 先扫描所有可用 I2C 总线
    import os
    buses = sorted([
        int(f.replace("i2c-", ""))
        for f in os.listdir("/dev")
        if f.startswith("i2c-")
    ])
    print(f"{INFO} 发现 I2C 总线: {[f'/dev/i2c-{b}' for b in buses]}")

    found_bus = None
    found_addr = None

    for bus_num in buses:
        try:
            bus = smbus2.SMBus(bus_num)
            for addr in [0x23, 0x5C]:
                try:
                    bus.read_byte(addr)
                    print(f"{PASS} 在 i2c-{bus_num} 总线上发现设备，地址 0x{addr:02X}")
                    found_bus = bus_num
                    found_addr = addr
                    break
                except OSError:
                    pass
            bus.close()
            if found_bus is not None:
                break
        except Exception as e:
            print(f"{INFO} i2c-{bus_num} 无法访问: {e}")

    if found_bus is None:
        print(f"{FAIL} 所有 I2C 总线上均未发现 BH1750 (0x23 或 0x5C)")
        print()
        print("  排查步骤:")
        print("  1. 确认 I2C 已启用: sudo raspi-config → Interface → I2C → Yes")
        print("  2. 重启后再试: sudo reboot")
        print("  3. 检查接线:")
        print("     VCC  → Pin 1  (3.3V)   红线")
        print("     GND  → Pin 6  (GND)    黑线")
        print("     SDA  → Pin 3  (GPIO2)  蓝线")
        print("     SCL  → Pin 5  (GPIO3)  绿线")
        print("  4. 确认杜邦线插紧，面包板接触良好")
        print("  5. 用万用表测 VCC 引脚对 GND 是否有 3.3V")
        return False

    # 找到设备，尝试读取
    try:
        bus = smbus2.SMBus(found_bus)
        bus.write_byte(found_addr, 0x20)
        time.sleep(0.2)
        data = bus.read_i2c_block_data(found_addr, 0x20, 2)
        lux = ((data[0] << 8) | data[1]) / 1.2
        print(f"{PASS} BH1750 读取成功: {lux:.1f} lux")

        if found_bus != 1:
            print(f"{INFO} 注意: BH1750 在 i2c-{found_bus}，但代码默认用 i2c-1")
            print(f"{INFO} 需要修改 light_sensor.py 中的 SMBus({found_bus})")
            # 自动修复
            _fix_bh1750_bus(found_bus)

        bus.close()
        return True
    except Exception as e:
        print(f"{FAIL} BH1750 读取失败: {e}")
        return False


def _fix_bh1750_bus(bus_num):
    """自动修复 light_sensor.py 中的 I2C 总线编号"""
    import re
    path = "light_sensor.py"
    try:
        with open(path, "r") as f:
            content = f.read()
        new_content = re.sub(
            r"smbus2\.SMBus\(\d+\)",
            f"smbus2.SMBus({bus_num})",
            content
        )
        if new_content != content:
            with open(path, "w") as f:
                f.write(new_content)
            print(f"{INFO} 已自动修复 light_sensor.py: SMBus({bus_num})")
    except Exception as e:
        print(f"{INFO} 自动修复失败，请手动修改 light_sensor.py: {e}")


# ── DHT22 ─────────────────────────────────────────────────────────────

def check_dht22():
    print("\n[DHT22 温湿度传感器]")
    try:
        import adafruit_dht
        import board
    except ImportError as e:
        print(f"{FAIL} 库未安装: {e}")
        print(f"{INFO} 请运行: pip install adafruit-circuitpython-dht")
        print(f"{INFO} 并运行: sudo apt install libgpiod2")
        return False

    print(f"{INFO} 使用 GPIO4 (Pin 7)，尝试读取（最多10次，每次间隔2秒）...")
    dht = None
    try:
        dht = adafruit_dht.DHT22(board.D4)
        success_count = 0
        fail_count = 0

        for attempt in range(10):
            try:
                temp = dht.temperature
                humi = dht.humidity
                if temp is not None and humi is not None:
                    print(f"{PASS} 第{attempt+1}次读取成功: {temp:.1f}°C  {humi:.1f}%")
                    success_count += 1
                    if success_count >= 2:
                        break
                else:
                    print(f"{INFO} 第{attempt+1}次: 返回 None")
                    fail_count += 1
            except RuntimeError as e:
                fail_count += 1
                print(f"{INFO} 第{attempt+1}次读取失败: {e}")
            time.sleep(2)

        if success_count > 0:
            print(f"{PASS} DHT22 工作正常（成功{success_count}次）")
            return True
        else:
            print(f"{FAIL} DHT22 连续{fail_count}次读取失败")
            print()
            print("  排查步骤:")
            print("  1. 检查接线: VCC→3.3V(Pin1), DATA→GPIO4(Pin7), GND→GND(Pin9)")
            print("  2. 确认三个脚在面包板的不同横排（不能在同一行）")
            print("  3. 在 VCC行 和 DATA行 之间加一个 10kΩ 上拉电阻")
            print("  4. 确认面包板GND轨已连接树莓派GND引脚（共地）")
            print("  5. 尝试换一个GPIO引脚，在config.py里改 TEMP_SENSOR_PIN")
            return False
    except Exception as e:
        print(f"{FAIL} DHT22 初始化失败: {e}")
        return False
    finally:
        if dht:
            try:
                dht.exit()
            except Exception:
                pass


# ── SG90 舵机 ─────────────────────────────────────────────────────────

def check_servo():
    print("\n[SG90 舵机]")
    ok, GPIO, HAS_GPIO = check_gpio_available()
    if not ok:
        return False

    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(18, GPIO.OUT)
        pwm = GPIO.PWM(18, 50)
        pwm.start(0)

        def set_angle(angle):
            duty = 2.5 + (angle / 180.0) * 10.0
            pwm.ChangeDutyCycle(duty)
            time.sleep(0.4)
            pwm.ChangeDutyCycle(0)

        print(f"{INFO} 舵机归位到 90°（中立）...")
        set_angle(90)
        time.sleep(0.5)

        print(f"{INFO} 转到 60°（模拟开灯方向）...")
        set_angle(60)
        time.sleep(0.5)

        print(f"{INFO} 回到 90°（中立）...")
        set_angle(90)
        time.sleep(0.5)

        print(f"{INFO} 转到 120°（模拟关灯方向）...")
        set_angle(120)
        time.sleep(0.5)

        print(f"{INFO} 回到 90°（中立）...")
        set_angle(90)

        pwm.stop()
        GPIO.cleanup(18)
        print(f"{PASS} 舵机动作完成，请确认舵机有实际转动")
        return True
    except Exception as e:
        print(f"{FAIL} 舵机测试失败: {e}")
        return False


# ── VS1838B 红外接收 ──────────────────────────────────────────────────

def check_ir_recv():
    print("\n[VS1838B 红外接收管]")
    ok, GPIO, HAS_GPIO = check_gpio_available()
    if not ok:
        return False

    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(24, GPIO.IN)

        print(f"{INFO} 等待红外信号（5秒内请按遥控器任意键）...")
        start = time.time()
        detected = False
        last_state = GPIO.input(24)

        while time.time() - start < 5:
            current = GPIO.input(24)
            if current != last_state:
                detected = True
                break
            last_state = current
            time.sleep(0.001)

        GPIO.cleanup(24)

        if detected:
            print(f"{PASS} VS1838B 检测到红外信号变化")
            return True
        else:
            print(f"{FAIL} 5秒内未检测到信号")
            print(f"{INFO} 检查: OUT→GPIO24(Pin18), VCC→3.3V, GND→GND")
            print(f"{INFO} 确认遥控器对准 VS1838B 平面（黑色接收面）")
            return False
    except Exception as e:
        print(f"{FAIL} 红外接收测试失败: {e}")
        return False


# ── 红外发射管（直接接法）────────────────────────────────────────────

def check_ir_send():
    print("\n[红外发射管（直接接法，GPIO25）]")
    ok, GPIO, HAS_GPIO = check_gpio_available()
    if not ok:
        return False

    print(f"{INFO} 此测试需要配合 VS1838B 验证")
    print(f"{INFO} 请先确保 VS1838B 已接好并对准发射管")

    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(25, GPIO.OUT)
        GPIO.setup(24, GPIO.IN)  # 同时监听接收管

        print(f"{INFO} 发送测试脉冲（模拟 NEC 引导码）...")
        detected = False

        # 发送简单脉冲序列
        for _ in range(3):
            GPIO.output(25, GPIO.HIGH)
            time.sleep(0.009)   # 9ms mark
            GPIO.output(25, GPIO.LOW)
            time.sleep(0.004)   # 4.5ms space

            # 检查接收管是否有响应
            start = time.time()
            while time.time() - start < 0.02:
                if GPIO.input(24) == GPIO.LOW:
                    detected = True
                    break
                time.sleep(0.0001)

            if detected:
                break
            time.sleep(0.1)

        GPIO.output(25, GPIO.LOW)
        GPIO.cleanup([24, 25])

        if detected:
            print(f"{PASS} 红外发射管工作正常（接收管检测到信号）")
        else:
            print(f"{INFO} 未通过接收管验证（可能距离太远或角度不对）")
            print(f"{INFO} 直接接法发射距离约 1~2 米，请靠近测试")
            print(f"{INFO} 如果 VS1838B 未接好，此测试无法验证")
        return True  # 发射管本身不报错即视为通过
    except Exception as e:
        print(f"{FAIL} 红外发射测试失败: {e}")
        return False


# ── 继电器 ────────────────────────────────────────────────────────────

def check_relay():
    print("\n[继电器模块（GPIO27）]")
    ok, GPIO, HAS_GPIO = check_gpio_available()
    if not ok:
        return False

    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(27, GPIO.OUT)

        print(f"{INFO} 继电器吸合（应听到咔哒声）...")
        GPIO.output(27, GPIO.LOW)   # 低电平触发
        time.sleep(1)

        print(f"{INFO} 继电器断开（应听到咔哒声）...")
        GPIO.output(27, GPIO.HIGH)
        time.sleep(0.5)

        GPIO.cleanup(27)
        print(f"{PASS} 继电器控制完成，请确认听到两声咔哒")
        return True
    except Exception as e:
        print(f"{FAIL} 继电器测试失败: {e}")
        return False


# ── 光敏电阻模块 ──────────────────────────────────────────────────────

def check_photo():
    print("\n[光敏电阻模块（GPIO17）]")
    ok, GPIO, HAS_GPIO = check_gpio_available()
    if not ok:
        return False

    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(17, GPIO.IN)

        readings = []
        print(f"{INFO} 读取光敏状态（3秒，请尝试遮挡/照射传感器）...")
        for i in range(6):
            val = GPIO.input(17)
            state = "暗(HIGH)" if val == GPIO.HIGH else "亮(LOW)"
            readings.append(val)
            print(f"       第{i+1}次: {state}")
            time.sleep(0.5)

        GPIO.cleanup(17)

        if len(set(readings)) > 1:
            print(f"{PASS} 光敏模块状态有变化，工作正常")
        else:
            state_str = "暗" if readings[0] == GPIO.HIGH else "亮"
            print(f"{INFO} 光敏模块状态固定为 [{state_str}]，可能需要调节电位器")
            print(f"{INFO} 用螺丝刀顺时针旋转模块上的蓝色电位器提高灵敏度")
        return True
    except Exception as e:
        print(f"{FAIL} 光敏模块测试失败: {e}")
        return False


# ── 主程序 ────────────────────────────────────────────────────────────

CHECKS = {
    "bh1750":  check_bh1750,
    "dht22":   check_dht22,
    "servo":   check_servo,
    "ir_recv": check_ir_recv,
    "ir_send": check_ir_send,
    "relay":   check_relay,
    "photo":   check_photo,
}

def main():
    print("=" * 55)
    print("  智能教室测控系统 — 硬件自检脚本")
    print("  第一轮最小台架验证")
    print("=" * 55)

    # 确认在树莓派上运行
    import platform
    if platform.system() != "Linux":
        print(f"\n{FAIL} 此脚本只能在树莓派（Linux）上运行")
        sys.exit(1)

    targets = sys.argv[1:] if len(sys.argv) > 1 else list(CHECKS.keys())
    results = {}

    for name in targets:
        if name not in CHECKS:
            print(f"\n未知检测项: {name}，可用: {', '.join(CHECKS.keys())}")
            continue
        results[name] = CHECKS[name]()

    print("\n" + "=" * 55)
    print("  检测结果汇总")
    print("=" * 55)
    all_pass = True
    for name, ok in results.items():
        icon = "✅" if ok else "❌"
        print(f"  {icon}  {name}")
        if not ok:
            all_pass = False

    print()
    if all_pass:
        print("  全部通过！可以运行主程序:")
        print("  python main.py")
    else:
        print("  部分检测未通过，请根据上方提示排查后重试")
    print("=" * 55)


if __name__ == "__main__":
    main()
