import time
from gpiozero import AngularServo, Device
from gpiozero.pins.lgpio import LGPIOFactory

# 使用 lgpio，适配 Raspberry Pi 5
Device.pin_factory = LGPIOFactory()

# 舵机信号线接 GPIO23，也就是物理 Pin 16
SERVO_GPIO = 23

servo = AngularServo(
    SERVO_GPIO,
    min_angle=0,
    max_angle=180,
    min_pulse_width=0.0005,
    max_pulse_width=0.0025
)

try:
    print("SG90 舵机测试开始，按 Ctrl+C 退出")

    while True:
        print("转到 0 度")
        servo.angle = 0
        time.sleep(1)

        print("转到 90 度")
        servo.angle = 90
        time.sleep(1)

        print("转到 180 度")
        servo.angle = 180
        time.sleep(1)

        print("回到 90 度")
        servo.angle = 90
        time.sleep(1)

except KeyboardInterrupt:
    print("\n退出测试")

finally:
    servo.detach()
