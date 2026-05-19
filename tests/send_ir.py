import sys
import time
import json
import lgpio

# =========================
# 基本配置
# =========================

IR_GPIO = 18  # 红外发射模块 DAT 接 GPIO18，也就是物理 Pin 12
COMMANDS_FILE = "ir_commands.json"

# 38kHz 载波参数
CARRIER_FREQ = 38000
CARRIER_PERIOD_US = int(1_000_000 / CARRIER_FREQ)  # 约 26us
HALF_PERIOD_US = CARRIER_PERIOD_US // 2            # 约 13us

# NEC-like 时序，单位：微秒
LEADER_MARK = 9000
LEADER_SPACE = 4500

BIT_MARK = 560
ZERO_SPACE = 560
ONE_SPACE = 1690

STOP_MARK = 560


# =========================
# 工具函数
# =========================

def now_us():
    return time.monotonic_ns() // 1000


def busy_wait_us(duration_us):
    end = now_us() + duration_us
    while now_us() < end:
        pass


def load_commands():
    with open(COMMANDS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def carrier_mark(chip, duration_us):
    """
    在 duration_us 时间内，用 GPIO 快速翻转模拟 38kHz 红外载波。
    """
    end = now_us() + duration_us

    while now_us() < end:
        lgpio.gpio_write(chip, IR_GPIO, 1)
        busy_wait_us(HALF_PERIOD_US)
        lgpio.gpio_write(chip, IR_GPIO, 0)
        busy_wait_us(HALF_PERIOD_US)

    lgpio.gpio_write(chip, IR_GPIO, 0)


def space(chip, duration_us):
    """
    不发射红外，保持低电平。
    """
    lgpio.gpio_write(chip, IR_GPIO, 0)
    busy_wait_us(duration_us)


def send_nec_like(chip, bits):
    """
    根据 clean_bits 发送 NEC-like 红外信号。

    引导码：
        9000us mark + 4500us space

    bit 0：
        560us mark + 560us space

    bit 1：
        560us mark + 1690us space

    结束：
        560us mark
    """

    print("开始发射红外信号")
    print("bits:", bits)
    print("bit 数量:", len(bits))

    # 引导码
    carrier_mark(chip, LEADER_MARK)
    space(chip, LEADER_SPACE)

    # 数据位
    for bit in bits:
        carrier_mark(chip, BIT_MARK)

        if bit == "0":
            space(chip, ZERO_SPACE)
        elif bit == "1":
            space(chip, ONE_SPACE)
        else:
            print("跳过非法 bit:", bit)

    # 结束脉冲
    carrier_mark(chip, STOP_MARK)
    lgpio.gpio_write(chip, IR_GPIO, 0)

    print("发射完成")


def send_command(command_name, repeat=3, interval=0.08):
    commands = load_commands()

    if command_name not in commands:
        print(f"没有找到命令：{command_name}")
        print("当前已保存命令：", list(commands.keys()))
        return

    info = commands[command_name]

    if "clean_bits" not in info:
        print(f"命令 {command_name} 中没有 clean_bits，请重新学习该命令。")
        return

    bits = info["clean_bits"]

    chip = lgpio.gpiochip_open(0)

    try:
        lgpio.gpio_claim_output(chip, IR_GPIO, 0)

        for i in range(repeat):
            print(f"\n第 {i + 1}/{repeat} 次发射：{command_name}")
            send_nec_like(chip, bits)
            time.sleep(interval)

    finally:
        lgpio.gpio_write(chip, IR_GPIO, 0)
        lgpio.gpiochip_close(chip)


def main():
    if len(sys.argv) < 2:
        print("用法：")
        print("  python send_ir.py open")
        print("  python send_ir.py close")
        print("  python send_ir.py open 5")
        return

    command_name = sys.argv[1]

    repeat = 3
    if len(sys.argv) >= 3:
        repeat = int(sys.argv[2])

    send_command(command_name, repeat=repeat)


if __name__ == "__main__":
    main()