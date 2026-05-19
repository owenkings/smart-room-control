import time
import board
import adafruit_dht

PIN = board.D17

while True:
    dht = adafruit_dht.DHT22(PIN, use_pulseio=False)

    try:
        temperature = dht.temperature
        humidity = dht.humidity

        if temperature is not None and humidity is not None:
            print(f"温度: {temperature:.1f}°C  湿度: {humidity:.1f}%")
        else:
            print("读取为空，重试中...")

    except RuntimeError as e:
        print("读取失败，重试中：", e)
    except OverflowError as e:
        print("读取溢出，重试中：", e)
    finally:
        dht.exit()

    time.sleep(6)