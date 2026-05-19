import time
from smbus2 import SMBus

BH1750_ADDR = 0x23
CONT_H_RES_MODE = 0x10

def read_lux(bus):
    data = bus.read_i2c_block_data(BH1750_ADDR, CONT_H_RES_MODE, 2)
    raw = (data[0] << 8) | data[1]
    return raw / 1.2

with SMBus(1) as bus:
    while True:
        lux = read_lux(bus)
        print(f"光照强度: {lux:.2f} lux")
        time.sleep(1)

