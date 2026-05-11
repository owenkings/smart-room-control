"""
红外信号学习工具 - 独立运行
用于录制空调遥控器的红外信号

使用方法:
  python ir_learn_tool.py

步骤:
  1. 将红外接收管(VS1838B)连接到GPIO24
  2. 运行此脚本
  3. 按提示选择要学习的信号类型
  4. 将遥控器对准接收管按下按键
  5. 信号自动保存到 ir_codes.json
"""

from ir_controller import IRController

SIGNAL_NAMES = {
    "1": ("ac_on_cool", "空调开机-制冷"),
    "2": ("ac_on_heat", "空调开机-制热"),
    "3": ("ac_off", "空调关机"),
    "4": ("ac_temp_up", "温度+"),
    "5": ("ac_temp_down", "温度-"),
}


def main():
    print("=" * 40)
    print("  红外遥控信号学习工具")
    print("=" * 40)

    ir = IRController()

    while True:
        print("\n请选择要学习的信号:")
        for key, (_, desc) in SIGNAL_NAMES.items():
            code_name = SIGNAL_NAMES[key][0]
            status = "✓ 已录制" if code_name in ir.codes else "✗ 未录制"
            print(f"  {key}. {desc} [{status}]")
        print("  q. 退出")

        choice = input("\n输入选项: ").strip()
        if choice == "q":
            break

        if choice in SIGNAL_NAMES:
            name, desc = SIGNAL_NAMES[choice]
            print(f"\n准备学习: {desc}")
            print("请将遥控器对准红外接收管，然后按下对应按键...")
            success = ir.learn_code(name)
            if success:
                print(f"学习成功! 信号已保存")
            else:
                print("学习失败，请重试")
        else:
            print("无效选项")

    print("\n学习完成，信号已保存到 ir_codes.json")
    ir.cleanup()


if __name__ == "__main__":
    main()
