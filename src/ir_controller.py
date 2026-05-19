"""
红外收发控制模块 (NEC 协议)

基于 lgpio 实现 NEC 红外协议的接收解码与发射编码。
- 接收：GPIO4 监听红外接收模块输出，解码 NEC 帧
- 发射：GPIO18 模拟 38kHz 载波，按 NEC 时序发射

参考来源：tests/test_ir.py (接收解码), tests/send_ir.py (发射编码)
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# NEC 协议时序常量 (微秒)
NEC_LEADER_MARK = 9000
NEC_LEADER_SPACE = 4500
NEC_BIT_MARK = 562  # 562.5µs
NEC_ZERO_SPACE = 562  # 562.5µs
NEC_ONE_SPACE = 1687  # 1687.5µs
NEC_STOP_MARK = 562

# ±10% 容差
TOLERANCE = 0.10

# 38kHz 载波参数
CARRIER_FREQ = 38000
CARRIER_PERIOD_US = int(1_000_000 / CARRIER_FREQ)  # ~26µs
HALF_PERIOD_US = CARRIER_PERIOD_US // 2  # ~13µs

# 汉明距离匹配阈值
MATCH_THRESHOLD = 3


def _in_range(value: int, target: int, tolerance: float = TOLERANCE) -> bool:
    """判断 value 是否在 target ± tolerance 范围内"""
    low = target * (1 - tolerance)
    high = target * (1 + tolerance)
    return low <= value <= high


def _hamming_distance(a: list[int], b: list[int]) -> int:
    """计算两个 bit 列表的汉明距离，长度不同的部分计入差异"""
    length = min(len(a), len(b))
    diff = sum(1 for i in range(length) if a[i] != b[i])
    diff += abs(len(a) - len(b))
    return diff


class IRController:
    """基于 lgpio 的 NEC 红外收发控制"""

    def __init__(self, recv_pin: int = None, send_pin: int = None,
                 commands_file: str = None):
        """
        初始化红外收发，加载已学习命令。

        Args:
            recv_pin: 红外接收 GPIO 引脚 (默认从 config 读取)
            send_pin: 红外发射 GPIO 引脚 (默认从 config 读取)
            commands_file: 命令存储文件路径
        """
        from config import IR_RECV_PIN, IR_SEND_PIN, DATA_DIR

        self.recv_pin = recv_pin if recv_pin is not None else IR_RECV_PIN
        self.send_pin = send_pin if send_pin is not None else IR_SEND_PIN

        if commands_file is None:
            self.commands_file = str(DATA_DIR / "ir_commands.json")
        else:
            self.commands_file = commands_file

        self.commands: dict = {}
        self._chip = None

        # 加载已保存的命令
        self.load_commands()

        # 初始化 GPIO
        self._init_gpio()

    def _init_gpio(self) -> None:
        """初始化 lgpio：打开 chip 0，配置收发引脚"""
        try:
            import lgpio
            self._chip = lgpio.gpiochip_open(0)
            # 接收引脚：输入模式，上拉
            lgpio.gpio_claim_input(self._chip, self.recv_pin, lgpio.SET_PULL_UP)
            # 发射引脚：输出模式，初始低电平
            lgpio.gpio_claim_output(self._chip, self.send_pin, 0)
            logger.info(f"IR GPIO 初始化完成: recv=GPIO{self.recv_pin}, send=GPIO{self.send_pin}")
        except Exception as e:
            logger.error(f"IR GPIO 初始化失败: {e}")
            self._chip = None

    @staticmethod
    def decode_nec(pulses: list[tuple[int, int]]) -> dict | None:
        """
        NEC 协议解码：脉冲时序 → 位数据。

        输入格式: [(mark_us, space_us), ...] — 成对的 mark/space 时序
        第一对应为引导码 (9000µs mark, 4500µs space)，
        后续 32 对为数据位，最后可能有一个 stop mark。

        Returns:
            解码成功: {'address': int, 'command': int, 'bits': list[int]}
            解码失败: None
        """
        if not pulses or len(pulses) < 2:
            return None

        # 验证引导码
        leader_mark, leader_space = pulses[0]
        if not _in_range(leader_mark, NEC_LEADER_MARK):
            return None
        if not _in_range(leader_space, NEC_LEADER_SPACE):
            return None

        # 解码数据位 (跳过引导码对)
        bits = []
        data_pulses = pulses[1:]

        for mark, space in data_pulses:
            # 验证 mark 在 562.5µs ±10% 范围
            if not _in_range(mark, NEC_BIT_MARK):
                # 如果是最后一个 stop mark (space 可能为 0 或很小)，跳过
                if len(bits) >= 32:
                    break
                continue

            # 根据 space 长度判断 bit 值
            if _in_range(space, NEC_ZERO_SPACE):
                bits.append(0)
            elif _in_range(space, NEC_ONE_SPACE):
                bits.append(1)
            else:
                # 如果已经有 32 位了，可能是 stop bit 的 space
                if len(bits) >= 32:
                    break
                # 否则标记为未知，尝试继续
                return None

        if len(bits) < 32:
            return None

        # 只取前 32 位
        bits = bits[:32]

        # 提取地址和命令
        address = 0
        for i in range(8):
            address |= bits[i] << i

        command = 0
        for i in range(8):
            command |= bits[16 + i] << i

        return {
            'address': address,
            'command': command,
            'bits': bits
        }

    @staticmethod
    def encode_nec(bits: list[int]) -> list[tuple[int, int]]:
        """
        NEC 协议编码：位数据 → 脉冲时序。

        输入: 32 位数据列表 [bit0, bit1, ..., bit31]
        输出: [(mark_us, space_us), ...] 包含引导码 + 32 数据对 + stop mark

        返回的列表结构:
        - 第 0 对: 引导码 (9000, 4500)
        - 第 1-32 对: 数据位 (562, 562) 或 (562, 1687)
        - 第 33 对: 停止位 (562, 0)
        """
        if len(bits) != 32:
            raise ValueError(f"NEC 帧必须为 32 位，收到 {len(bits)} 位")

        pulses = []

        # 引导码
        pulses.append((NEC_LEADER_MARK, NEC_LEADER_SPACE))

        # 32 位数据
        for bit in bits:
            if bit == 1:
                pulses.append((NEC_BIT_MARK, NEC_ONE_SPACE))
            else:
                pulses.append((NEC_BIT_MARK, NEC_ZERO_SPACE))

        # 停止位 (mark only, space = 0)
        pulses.append((NEC_STOP_MARK, 0))

        return pulses

    def _capture_one_frame(self, timeout: float = 10.0) -> list[int] | None:
        """
        捕获一帧红外信号的原始脉冲。

        返回交替的 mark/space 时长列表 (微秒)，
        超过 30ms 无电平变化视为帧结束。

        Returns:
            脉冲列表 [mark0, space0, mark1, space1, ...] 或 None (超时)
        """
        import lgpio

        if self._chip is None:
            logger.error("GPIO 未初始化，无法捕获红外信号")
            return None

        start_time = time.monotonic()
        last_value = lgpio.gpio_read(self._chip, self.recv_pin)
        last_time = time.monotonic_ns()

        pulses = []
        started = False

        while True:
            # 超时检查
            if time.monotonic() - start_time > timeout:
                logger.warning("红外捕获超时")
                return None

            value = lgpio.gpio_read(self._chip, self.recv_pin)
            now = time.monotonic_ns()

            if value != last_value:
                duration_us = (now - last_time) // 1000

                if not started:
                    # 等待下降沿 (1→0) 作为帧起始
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

            # 帧结束判断：超过 30ms 无变化
            if started and (now - last_time) > 30_000_000:
                return pulses

    def _raw_pulses_to_pairs(self, raw_pulses: list[int]) -> list[tuple[int, int]]:
        """将交替的 mark/space 列表转换为 (mark, space) 对列表"""
        pairs = []
        for i in range(0, len(raw_pulses) - 1, 2):
            pairs.append((raw_pulses[i], raw_pulses[i + 1]))
        # 如果有奇数个脉冲，最后一个 mark 配 space=0
        if len(raw_pulses) % 2 == 1:
            pairs.append((raw_pulses[-1], 0))
        return pairs

    def _is_valid_leader(self, raw_pulses: list[int]) -> bool:
        """判断原始脉冲是否包含有效的 NEC 引导码"""
        if len(raw_pulses) < 4:
            return False
        leader_mark = raw_pulses[0]
        leader_space = raw_pulses[1]
        return (_in_range(leader_mark, NEC_LEADER_MARK, 0.12) and
                _in_range(leader_space, NEC_LEADER_SPACE, 0.22))

    def _match_command(self, bits: list[int]) -> str | None:
        """用汉明距离匹配已存储的命令"""
        if not self.commands:
            return None

        best_name = None
        best_dist = float('inf')

        for name, info in self.commands.items():
            stored_bits = info.get('bits', [])
            if not stored_bits:
                continue
            dist = _hamming_distance(bits, stored_bits)
            if dist < best_dist:
                best_dist = dist
                best_name = name

        if best_dist <= MATCH_THRESHOLD:
            return best_name
        return None

    def start_learning(self, command_name: str, timeout: float = 10.0) -> dict:
        """
        开始学习模式，等待红外信号。

        Args:
            command_name: 命令名称
            timeout: 超时时间 (秒)

        Returns:
            成功: {'success': True, 'name': str, 'address': int, 'command': int}
            失败: {'success': False, 'error': str}
        """
        logger.info(f"开始学习红外命令: {command_name}, 超时: {timeout}s")

        raw_pulses = self._capture_one_frame(timeout=timeout)
        if raw_pulses is None:
            return {'success': False, 'error': '捕获超时，未接收到红外信号'}

        # 验证引导码
        if not self._is_valid_leader(raw_pulses):
            return {'success': False, 'error': '无效帧：未检测到 NEC 引导码'}

        # 转换为 (mark, space) 对并解码
        pairs = self._raw_pulses_to_pairs(raw_pulses)
        decoded = self.decode_nec(pairs)

        if decoded is None:
            return {'success': False, 'error': '解码失败：无法解析 NEC 帧'}

        # 保存命令
        self.commands[command_name] = {
            'protocol': 'NEC',
            'bits': decoded['bits'],
            'address': decoded['address'],
            'command': decoded['command'],
            'learned_at': datetime.now().isoformat()
        }
        self.save_commands()

        logger.info(f"学习成功: {command_name} (addr={decoded['address']}, cmd={decoded['command']})")
        return {
            'success': True,
            'name': command_name,
            'address': decoded['address'],
            'command': decoded['command']
        }

    def send_command(self, command_name: str, repeat: int = 3) -> bool:
        """
        发送已学习的红外命令。

        Args:
            command_name: 命令名称
            repeat: 重复发送次数 (默认 3)

        Returns:
            True 发送成功, False 失败
        """
        import lgpio

        if command_name not in self.commands:
            logger.error(f"未找到命令: {command_name}")
            return False

        if self._chip is None:
            logger.error("GPIO 未初始化，无法发送红外信号")
            return False

        info = self.commands[command_name]
        bits = info.get('bits', [])
        if not bits:
            logger.error(f"命令 {command_name} 没有有效的 bits 数据")
            return False

        # 编码为 NEC 脉冲时序
        pulses = self.encode_nec(bits)

        try:
            for i in range(repeat):
                self._send_pulses(pulses)
                if i < repeat - 1:
                    time.sleep(0.08)  # 重复间隔 80ms

            logger.info(f"红外命令已发送: {command_name} (重复 {repeat} 次)")
            return True

        except Exception as e:
            logger.error(f"红外发送失败: {e}")
            return False

    def _send_pulses(self, pulses: list[tuple[int, int]]) -> None:
        """发送一组 (mark_us, space_us) 脉冲，mark 期间模拟 38kHz 载波"""
        import lgpio

        for mark_us, space_us in pulses:
            if mark_us > 0:
                self._carrier_mark(mark_us)
            if space_us > 0:
                lgpio.gpio_write(self._chip, self.send_pin, 0)
                self._busy_wait_us(space_us)

        # 确保结束时为低电平
        lgpio.gpio_write(self._chip, self.send_pin, 0)

    def _carrier_mark(self, duration_us: int) -> None:
        """在指定时长内模拟 38kHz 载波 (GPIO 快速翻转)"""
        import lgpio

        end = time.monotonic_ns() // 1000 + duration_us
        while time.monotonic_ns() // 1000 < end:
            lgpio.gpio_write(self._chip, self.send_pin, 1)
            self._busy_wait_us(HALF_PERIOD_US)
            lgpio.gpio_write(self._chip, self.send_pin, 0)
            self._busy_wait_us(HALF_PERIOD_US)

        lgpio.gpio_write(self._chip, self.send_pin, 0)

    @staticmethod
    def _busy_wait_us(duration_us: int) -> None:
        """忙等待指定微秒数"""
        end = time.monotonic_ns() // 1000 + duration_us
        while time.monotonic_ns() // 1000 < end:
            pass

    def list_commands(self) -> list[str]:
        """列出所有已学习命令名称"""
        return list(self.commands.keys())

    def delete_command(self, command_name: str) -> bool:
        """
        删除指定命令。

        Returns:
            True 删除成功, False 命令不存在
        """
        if command_name not in self.commands:
            return False
        del self.commands[command_name]
        self.save_commands()
        logger.info(f"已删除红外命令: {command_name}")
        return True

    def save_commands(self) -> None:
        """保存命令到 JSON 文件"""
        # 确保目录存在
        os.makedirs(os.path.dirname(self.commands_file), exist_ok=True)

        with open(self.commands_file, 'w', encoding='utf-8') as f:
            json.dump(self.commands, f, indent=2, ensure_ascii=False)
        logger.debug(f"命令已保存到 {self.commands_file}")

    def load_commands(self) -> dict:
        """
        从 JSON 文件加载命令。

        Returns:
            加载的命令字典
        """
        if not os.path.exists(self.commands_file):
            self.commands = {}
            return self.commands

        try:
            with open(self.commands_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 兼容旧格式：如果 bits 是字符串，转换为 int 列表
            for name, info in data.items():
                if isinstance(info.get('bits'), str):
                    # 旧格式: "10011010..." → [1, 0, 0, 1, ...]
                    info['bits'] = [int(b) for b in info['bits'] if b in ('0', '1')]
                elif isinstance(info.get('bits'), list):
                    # 确保是 int 列表
                    info['bits'] = [int(b) for b in info['bits']]

                # 兼容旧格式的 clean_bits 字段
                if 'clean_bits' in info and 'bits' not in info:
                    info['bits'] = [int(b) for b in info['clean_bits'] if b in ('0', '1')]

            self.commands = data
            logger.info(f"已加载 {len(self.commands)} 个红外命令")

        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"加载命令文件失败: {e}")
            self.commands = {}

        return self.commands

    def cleanup(self) -> None:
        """释放 GPIO 资源"""
        if self._chip is not None:
            try:
                import lgpio
                lgpio.gpio_write(self._chip, self.send_pin, 0)
                lgpio.gpiochip_close(self._chip)
                logger.info("IR GPIO 资源已释放")
            except Exception as e:
                logger.warning(f"IR GPIO 清理时出错: {e}")
            finally:
                self._chip = None
