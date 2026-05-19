import time
import json
import os
import sys
import lgpio

# =========================
# 基本配置
# =========================

GPIO = 4  # 红外接收模块 OUT 接 GPIO4，也就是物理 Pin 7
RECORD_FILE = "ir_record.json"
COMMANDS_FILE = "ir_commands.json"

MATCH_THRESHOLD = 3  # 允许最多 3 位误差


# =========================
# 工具函数
# =========================

def in_range(x, low, high):
    return low <= x <= high


def hamming_distance(a, b):
    """
    计算两个 bit 串差异。
    ? 视为未知位，不计入差异。
    长度不同的部分计入差异。
    """
    length = min(len(a), len(b))
    diff = 0

    for i in range(length):
        if a[i] == "?" or b[i] == "?":
            continue
        if a[i] != b[i]:
            diff += 1

    diff += abs(len(a) - len(b))
    return diff


def is_valid_leader(pulses):
    """
    判断是否为 NEC-like 红外帧。
    标准引导码大致为：
    9000us + 4500us
    """
    if len(pulses) < 4:
        return False

    leader_mark = pulses[0]
    leader_space = pulses[1]

    return in_range(leader_mark, 8000, 10000) and in_range(leader_space, 3500, 5500)


def decode_nec_to_bits(pulses):
    """
    将 NEC-like 红外脉冲归一化为 0/1/?。

    典型格式：
    [9000, 4500, 560, 560, 560, 1690, ...]

    规则：
    mark + short space -> 0
    mark + long space  -> 1
    模糊值             -> ?
    """

    if len(pulses) < 4:
        return ""

    bits = []
    data = pulses[2:]  # 跳过引导码

    for i in range(0, len(data) - 1, 2):
        mark = data[i]
        space = data[i + 1]

        # 你新模块/新遥控器测出来 mark 大概在 660us 左右，
        # 所以这里给宽一点的范围。
        if not in_range(mark, 250, 1000):
            continue

        # 0 的 space 通常在 500~700us 左右
        if in_range(space, 250, 1000):
            bits.append("0")

        # 1 的 space 通常在 1500~1800us 左右
        elif in_range(space, 1100, 2400):
            bits.append("1")

        else:
            bits.append("?")

    return "".join(bits)


def bits_to_hex(bits):
    clean_bits = bits.replace("?", "")
    usable_len = len(clean_bits) // 8 * 8
    clean_bits = clean_bits[:usable_len]

    hex_values = []

    for i in range(0, len(clean_bits), 8):
        byte = clean_bits[i:i + 8]
        value = int(byte, 2)
        hex_values.append(f"{value:02X}")

    return " ".join(hex_values)


def load_commands():
    if not os.path.exists(COMMANDS_FILE):
        return {}

    with open(COMMANDS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_commands(commands):
    with open(COMMANDS_FILE, "w", encoding="utf-8") as f:
        json.dump(commands, f, indent=2, ensure_ascii=False)


def recognize_command(clean_bits, commands):
    """
    将当前 clean_bits 和已学习的命令比较。
    """
    if not commands:
        return "unknown", {}

    distances = {}

    for name, info in commands.items():
        target_bits = info["clean_bits"]
        distances[name] = hamming_distance(clean_bits, target_bits)

    best_name = min(distances, key=distances.get)
    best_dist = distances[best_name]

    if best_dist <= MATCH_THRESHOLD:
        return best_name, distances

    return "unknown", distances


def capture_one_frame(chip):
    """
    捕获一帧红外信号。
    超过 30ms 没有电平变化，认为一帧结束。
    """
    last_value = lgpio.gpio_read(chip, GPIO)
    last_time = time.monotonic_ns()

    pulses = []
    started = False

    while True:
        value = lgpio.gpio_read(chip, GPIO)
        now = time.monotonic_ns()

        if value != last_value:
            duration_us = (now - last_time) // 1000

            if not started:
                if last_value == 1 and value == 0:
                    started = True
                    pulses = []
                    last_time = now
                    last_value = value
                    continue
            else:
                pulses.append(int(duration_us))

            last_value = value
            last_time = now

        if started and (now - last_time) > 30_000_000:
            return pulses


def capture_valid_frame():
    chip = lgpio.gpiochip_open(0)
    lgpio.gpio_claim_input(chip, GPIO, lgpio.SET_PULL_UP)

    print(f"开始监听 GPIO{GPIO}")
    print("请短按遥控器上的一个按键，不要长按。")
    print("程序会自动丢弃无效帧，只处理带有 9000/4500 引导码的有效帧。")

    try:
        while True:
            pulses = capture_one_frame(chip)

            print("\n捕获到一帧")
            print("脉冲数量:", len(pulses))
            print("前 20 个脉冲:", pulses[:20])

            if not is_valid_leader(pulses):
                print("无效帧：没有检测到标准 9000/4500 引导码，已丢弃。请再按一次。")
                continue

            return pulses

    finally:
        lgpio.gpiochip_close(chip)


def save_record(record):
    with open(RECORD_FILE, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)


# =========================
# 主程序
# =========================

def main():
    mode = "recognize"
    learn_name = None

    if len(sys.argv) >= 3 and sys.argv[1] == "learn":
        mode = "learn"
        learn_name = sys.argv[2]

    pulses = capture_valid_frame()

    bits = decode_nec_to_bits(pulses)
    clean_bits = bits.replace("?", "")
    hex_code = bits_to_hex(bits)

    commands = load_commands()

    if mode == "learn":
        commands[learn_name] = {
            "name": learn_name,
            "bits": bits,
            "clean_bits": clean_bits,
            "hex": hex_code,
            "pulse_count": len(pulses),
            "leader": pulses[:2],
            "first_20_pulses": pulses[:20]
        }
        save_commands(commands)

        result = learn_name
        distances = {}

    else:
        result, distances = recognize_command(clean_bits, commands)

    record = {
        "gpio": GPIO,
        "unit": "microseconds",
        "protocol_guess": "NEC-like",

        "pulse_count": len(pulses),
        "leader": pulses[:2],
        "first_20_pulses": pulses[:20],
        "pulses": pulses,

        "bits": bits,
        "clean_bits": clean_bits,
        "bit_count": len(bits),
        "clean_bit_count": len(clean_bits),
        "hex": hex_code,

        "mode": mode,
        "match": {
            "result": result,
            "distances": distances
        }
    }

    save_record(record)

    print("\n有效红外帧记录完成")

    print("\n归一化后的 0/1/? bit 串:")
    print(bits)
    print("bit 数量:", len(bits))

    print("\n去除 ? 后的 clean_bits:")
    print(clean_bits)
    print("clean_bits 数量:", len(clean_bits))

    print("\nHEX:")
    print(hex_code)

    if mode == "learn":
        print(f"\n学习完成：已保存为命令 `{learn_name}`")
        print(f"命令文件：{COMMANDS_FILE}")
    else:
        print("\n匹配结果:")
        print("识别为:", result)
        print("距离:", distances)

    print(f"\n本次记录已保存到 {RECORD_FILE}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已退出")