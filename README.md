# 智能教室测控系统

基于 YOLO 人员检测的非侵入式智能教室网络化测控原型系统。

课程：《网络化测控技术》

---

## 系统架构

```
摄像头 → YOLOv8/11/26 人员检测 → 决策引擎 → 执行器
                                      ↑
                          DHT22温湿度 + BH1750光照

执行器:
  舵机 MG90S  → 物理按压墙壁灯开关（非侵入式）
  红外发射管  → 模拟空调遥控器信号
  继电器      → 低压设备电源控制

界面:
  Web 版  → 浏览器访问，支持远程监控
  GUI 版  → PyQt6 本地界面，画面最流畅
```

---

## 快速开始

### 方式一：本地运行（PC 开发测试）

```bash
pip install -r requirements.txt

# Web 版
python main.py
# 浏览器访问 http://localhost:8080

# GUI 版
python gui_app.py
```

### 方式二：树莓派部署

详见 [部署指南_树莓派5.md](部署指南_树莓派5.md)

---

## 远程访问树莓派

### 方法一：Raspberry Pi Connect（推荐，无需同一局域网）

1. 在树莓派上启用 Raspberry Pi Connect：
   ```bash
   sudo apt install rpi-connect
   rpi-connect signin
   ```
2. 在任意设备浏览器打开：
   **https://connect.raspberrypi.com/devices**
3. 登录你的 Raspberry Pi 账号，即可远程桌面或 SSH

> 无需配置端口转发，树莓派不在同一局域网也能访问。

### 方法二：局域网 SSH

```bash
# 在同一 Wi-Fi 下
ssh admin@树莓派IP地址

# 查看树莓派 IP
hostname -I
```

### 方法三：局域网访问 Web 界面

树莓派运行 `python main.py` 后，在同一局域网的手机或电脑浏览器输入：
```
http://树莓派IP:8080
```

---

## 硬件清单

| 模块 | 型号 | 用途 |
|------|------|------|
| 主控板 | 树莓派 5（8GB） | 核心计算 |
| 摄像头 | USB 摄像头 | 人员检测 |
| 舵机 | MG90S / SG90 | 按压墙壁灯开关 |
| 温湿度 | DHT22 | 环境感知 |
| 光照 | BH1750（GY-302） | 判断是否需要开灯 |
| 光敏模块 | 3针光敏电阻模块 | 灯光状态反馈（闭环） |
| 红外接收 | VS1838B | 学习空调遥控信号 |
| 红外发射 | 3mm 940nm 发射管 | 发送空调控制信号 |
| 继电器 | 5V 单路继电器 | 低压设备电源控制 |
| 面包板 | MB-102 + 830孔 | 免焊接搭建 |

GPIO 接线详见 [硬件接线与自检指南_树莓派5.md](硬件接线与自检指南_树莓派5.md)

---

## 硬件自检

```bash
# 逐模块验证（建议顺序）
python hw_check.py relay     # 继电器：听咔哒声
python hw_check.py servo     # 舵机：看是否转动
python hw_check.py photo     # 光敏：遮挡看状态变化
python hw_check.py ir_recv   # 红外接收：按遥控器
python hw_check.py bh1750    # 光照传感器
python hw_check.py dht22     # 温湿度传感器
```

---

## 模型选择

首次使用会自动下载，之后缓存本地。

| 系列 | 推荐型号 | 适用场景 |
|------|---------|---------|
| YOLOv8 | `yolov8n.pt` | PC 开发测试 |
| YOLOv8 | `yolov8s.pt` | 树莓派5 推荐 |
| YOLO11 | `yolo11s.pt` | 精度更高 |
| YOLO26 | `yolo26n.pt` | 最新一代 |

Web 界面和 GUI 均支持运行时热切换模型，无需重启。

---

## 文件说明

| 文件 | 说明 |
|------|------|
| `main.py` | Web 版主程序 |
| `gui_app.py` | GUI 版主程序 |
| `config.py` | 所有配置参数 |
| `detector.py` | YOLO 检测 + 摄像头管理 |
| `decision_engine.py` | 决策引擎 |
| `device_manager.py` | 执行器统一管理 |
| `servo_switch.py` | 舵机控制 |
| `ir_controller.py` | 红外遥控 |
| `ir_learn_tool.py` | 红外信号学习工具 |
| `relay_controller.py` | 继电器控制 |
| `sensor.py` | DHT22 温湿度 |
| `light_sensor.py` | BH1750 光照 + 光敏反馈 |
| `hw_check.py` | 硬件自检脚本 |
| `user_settings.py` | 用户配置持久化 |
| `web_server.py` | Flask Web 服务 |
| `templates/index.html` | Web 监控界面 |
| `ISSUES_TODO.md` | 待解决问题与开发方向 |
| `部署指南_树莓派5.md` | 完整部署文档 |
| `硬件接线与自检指南_树莓派5.md` | 接线图与步骤 |

---

## 当前状态

- ✅ PC 端模拟模式完整运行
- ✅ YOLO 人员检测（USB 摄像头）
- ✅ Web 界面 + GUI 界面
- ✅ WebSocket 低延迟推流
- ✅ 模型热切换
- ⚠️ BH1750 接线待修复（见 ISSUES_TODO.md）
- ⚠️ DHT22 接线待修复（见 ISSUES_TODO.md）
- ⚠️ 红外收发待验证
- ⚠️ 舵机校准流程待实现（见 ISSUES_TODO.md）
