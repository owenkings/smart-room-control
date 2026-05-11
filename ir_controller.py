"""
红外遥控模块 - 学习并发射红外信号控制空调
内置在项目板/摄像头盒子上，对准空调红外接收窗

硬件连接:
  红外发射管 -> GPIO25 (通过三极管驱动，增大发射功率)
  红外接收管 -> GPIO24 (用于学习遥控器信号, 如VS1838B)

工作流程:
  1. 先运行学习模式，对着接收管按遥控器按键，录制信号
  2. 信号保存到 ir_codes.json
  3. 正常运行时，从文件加载信号并通过发射管重放
"""

import json
import time
import os
import logging
import config
from gpio_compat import GPIO, HAS_GPIO

logger = logging.getLogger(__name__)


class IRController:
    """红外遥控空调控制器"""

    def __init__(self):
        self.is_on = False
        self.mode = "off"  # off / cooling / heating
        self.codes = {}
        self.gpio_available = HAS_GPIO
        self._load_codes()

        if self.gpio_available:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(config.IR_SEND_PIN, GPIO.OUT)
                GPIO.output(config.IR_SEND_PIN, GPIO.LOW)
                GPIO.setup(config.IR_RECV_PIN, GPIO.IN)
                logger.info("红外遥控模块初始化完成")
            except Exception as e:
                self.gpio_available = False
                logger.warning(f"红外遥控GPIO初始化失败，切换到模拟模式: {e}")
        else:
            logger.info("红外遥控模拟模式已启动")

    def _load_codes(self):
        """从文件加载已学习的红外信号"""
        path = config.IR_CODES_FILE
        if os.path.exists(path):
            with open(path, "r") as f:
                self.codes = json.load(f)
            logger.info(f"已加载 {len(self.codes)} 个红外信号")
        else:
            self.codes = {}
            logger.warning("未找到红外信号文件，请先运行学习模式")

    def _save_codes(self):
        """保存红外信号到文件"""
        with open(config.IR_CODES_FILE, "w") as f:
            json.dump(self.codes, f, indent=2)
        logger.info("红外信号已保存")

    def _send_raw(self, pulses):
        """发送原始红外脉冲序列
        pulses: [mark_us, space_us, mark_us, space_us, ...]
        mark=发射载波, space=静默
        """
        if not self.gpio_available:
            logger.debug(f"[模拟] 发送红外脉冲, 长度={len(pulses)}")
            return

        # 38kHz载波，周期约26.3us
        carrier_period = 1.0 / 38000
        half_period = carrier_period / 2

        for i, duration_us in enumerate(pulses):
            duration_s = duration_us / 1_000_000
            start = time.time()

            if i % 2 == 0:
                # mark: 发射38kHz载波
                while time.time() - start < duration_s:
                    GPIO.output(config.IR_SEND_PIN, GPIO.HIGH)
                    time.sleep(half_period)
                    GPIO.output(config.IR_SEND_PIN, GPIO.LOW)
                    time.sleep(half_period)
            else:
                # space: 静默
                GPIO.output(config.IR_SEND_PIN, GPIO.LOW)
                time.sleep(duration_s)

    def _record_signal(self, timeout=10):
        """录制红外信号(从接收管读取脉冲序列)"""
        if not self.gpio_available:
            logger.info("[模拟] 录制红外信号")
            return [9000, 4500, 560, 560]  # 模拟NEC引导码

        logger.info(f"等待红外信号... (超时{timeout}秒)")
        pulses = []
        start_time = time.time()

        # 等待信号开始(接收管空闲时为HIGH，收到信号时为LOW)
        while GPIO.input(config.IR_RECV_PIN) == GPIO.HIGH:
            if time.time() - start_time > timeout:
                logger.warning("录制超时，未收到信号")
                return None

        # 开始记录脉冲
        last_time = time.time()
        last_state = GPIO.LOW

        while True:
            current = GPIO.input(config.IR_RECV_PIN)
            now = time.time()

            if current != last_state:
                duration_us = int((now - last_time) * 1_000_000)
                pulses.append(duration_us)
                last_time = now
                last_state = current

            # 超过50ms无变化，认为信号结束
            if now - last_time > 0.05 and len(pulses) > 4:
                break

            # 总超时保护
            if now - start_time > timeout:
                break

        logger.info(f"录制完成，共 {len(pulses)} 个脉冲")
        return pulses if len(pulses) > 4 else None

    def learn_code(self, name):
        """学习一个遥控器按键信号
        Args:
            name: 信号名称，如 "ac_on_cool", "ac_off"
        Returns:
            bool: 是否学习成功
        """
        logger.info(f"准备学习信号: {name}")
        logger.info("请将遥控器对准红外接收管，然后按下按键...")

        pulses = self._record_signal()
        if pulses:
            self.codes[name] = pulses
            self._save_codes()
            logger.info(f"信号 '{name}' 学习成功!")
            return True
        else:
            logger.error(f"信号 '{name}' 学习失败")
            return False

    def send_code(self, name):
        """发送已学习的红外信号"""
        if name not in self.codes:
            logger.warning(f"未找到信号: {name}，请先学习")
            return False

        self._send_raw(self.codes[name])
        logger.info(f"[红外] 已发送信号: {name}")
        return True

    def ac_on_cool(self):
        """开空调-制冷"""
        if self.send_code("ac_on_cool"):
            self.is_on = True
            self.mode = "cooling"

    def ac_on_heat(self):
        """开空调-制热"""
        if self.send_code("ac_on_heat"):
            self.is_on = True
            self.mode = "heating"

    def ac_off(self):
        """关空调"""
        if self.send_code("ac_off"):
            self.is_on = False
            self.mode = "off"

    def set_ac(self, on, mode="cooling"):
        """统一控制接口"""
        if on:
            if mode == "cooling":
                self.ac_on_cool()
            else:
                self.ac_on_heat()
        else:
            self.ac_off()

    def get_state(self):
        return {"is_on": self.is_on, "mode": self.mode}

    def cleanup(self):
        if self.gpio_available:
            try:
                GPIO.output(config.IR_SEND_PIN, GPIO.LOW)
            except Exception as e:
                logger.debug(f"红外清理时忽略GPIO异常: {e}")
            finally:
                self.gpio_available = False
