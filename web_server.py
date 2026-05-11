"""
Web服务模块 - B/S架构监控界面

推流方案:
  /video_feed  — MJPEG（兼容性好，适合低带宽/旧浏览器）
  /ws/video    — WebSocket 二进制推帧（延迟更低，推荐）
  前端自动选择 WebSocket，不支持时降级到 MJPEG
"""

import time
import threading
import logging
from flask import Flask, render_template, jsonify, Response, request
from flask_sock import Sock
import config

logger = logging.getLogger(__name__)

app = Flask(__name__)
sock = Sock(app)

engine = None
detector = None


def init_app(decision_engine, person_detector):
    global engine, detector
    engine = decision_engine
    detector = person_detector


# ── 页面 ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ── 状态 API ──────────────────────────────────────────────────────────

@app.route("/api/status")
def api_status():
    if engine is None:
        return jsonify({"error": "系统未初始化"}), 503
    return jsonify(engine.get_full_status())


@app.route("/api/mode", methods=["POST"])
def api_mode():
    data = request.get_json()
    mode = data.get("mode", "").upper()
    if engine.set_mode(mode):
        return jsonify({"ok": True, "mode": mode})
    return jsonify({"error": "无效模式"}), 400


@app.route("/api/detection_interval", methods=["POST"])
def api_detection_interval():
    data = request.get_json()
    try:
        seconds = float(data.get("seconds", 2))
    except (TypeError, ValueError):
        return jsonify({"error": "无效数值"}), 400
    actual = detector.set_detection_interval(seconds)
    engine._log_action(f"检测间隔调整为 {actual}s")
    return jsonify({"ok": True, "seconds": actual})


@app.route("/api/model/switch", methods=["POST"])
def api_model_switch():
    data = request.get_json()
    model_path = data.get("model_path", "").strip()
    if not model_path:
        return jsonify({"error": "请提供模型路径"}), 400
    result = detector.switch_model(model_path)
    if result["ok"]:
        engine._log_action(f"切换模型: {model_path}")
    return jsonify(result)


@app.route("/api/model/status")
def api_model_status():
    return jsonify({
        "model_name": detector.model_name,
        "model_loading": detector.model_loading,
    })


@app.route("/api/control", methods=["POST"])
def api_control():
    data = request.get_json()
    device = data.get("device")
    action = data.get("action")
    if device not in ("light", "power", "ac"):
        return jsonify({"error": "无效设备"}), 400
    if action not in ("on", "off"):
        return jsonify({"error": "无效操作"}), 400
    on = action == "on"
    if device == "ac":
        engine.devices.set_ac(on, data.get("mode", "cooling"))
    elif device == "light":
        engine.devices.set(device, on, force=True)
    else:
        engine.devices.set(device, on)
    device_names = {"light": "灯光(舵机)", "power": "电源(继电器)", "ac": "空调(红外)"}
    engine._log_action(f"[手动] {'开启' if on else '关闭'} {device_names.get(device, device)}")
    return jsonify({"ok": True})


@app.route("/api/ir/learn", methods=["POST"])
def api_ir_learn():
    data = request.get_json()
    name = data.get("name")
    if not name:
        return jsonify({"error": "请提供信号名称"}), 400
    success = engine.devices.learn_ir_code(name)
    return jsonify({"ok": success, "name": name})


@app.route("/api/ir/codes")
def api_ir_codes():
    codes = engine.devices.ir.codes
    return jsonify({"codes": list(codes.keys()), "count": len(codes)})


@app.route("/api/servo/status")
def api_servo_status():
    return jsonify(engine.devices.get_servo_status())


@app.route("/api/servo/move", methods=["POST"])
def api_servo_move():
    data = request.get_json()
    try:
        angle = int(data.get("angle"))
    except (TypeError, ValueError):
        return jsonify({"error": "无效角度"}), 400
    actual = engine.devices.move_servo_to(angle)
    engine._log_action(f"[标定] 舵机移动到 {actual}°")
    return jsonify({"ok": True, "angle": actual, "status": engine.devices.get_servo_status()})


@app.route("/api/servo/nudge", methods=["POST"])
def api_servo_nudge():
    data = request.get_json()
    try:
        delta = int(data.get("delta"))
    except (TypeError, ValueError):
        return jsonify({"error": "无效步进"}), 400
    actual = engine.devices.nudge_servo(delta)
    engine._log_action(f"[标定] 舵机微调 {delta:+d}° -> {actual}°")
    return jsonify({"ok": True, "angle": actual, "status": engine.devices.get_servo_status()})


@app.route("/api/servo/save", methods=["POST"])
def api_servo_save():
    data = request.get_json()
    preset = data.get("preset")
    angle = data.get("angle")
    try:
        status = engine.devices.save_servo_preset(preset, angle)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    engine._log_action(
        f"[标定] 记录舵机{preset}角度: 开={status['angle_on']}° "
        f"关={status['angle_off']}° 中立={status['angle_neutral']}°"
    )
    return jsonify({"ok": True, "status": status})


@app.route("/api/servo/config", methods=["POST"])
def api_servo_config():
    data = request.get_json()
    try:
        status = engine.devices.save_servo_config(
            angle_on=data.get("angle_on"),
            angle_off=data.get("angle_off"),
            angle_neutral=data.get("angle_neutral"),
            action_duration=data.get("action_duration"),
        )
    except (TypeError, ValueError):
        return jsonify({"error": "无效舵机参数"}), 400
    engine._log_action(
        f"[标定] 保存舵机参数: 开={status['angle_on']}° "
        f"关={status['angle_off']}° 中立={status['angle_neutral']}° "
        f"保持={status['action_duration']:.2f}s"
    )
    return jsonify({"ok": True, "status": status})


# ── 推流：MJPEG（兼容性兜底） ─────────────────────────────────────────

def _gen_mjpeg():
    """MJPEG 生成器，浏览器不支持 WebSocket 时使用"""
    interval = 1.0 / config.STREAM_WS_FPS
    while True:
        t0 = time.time()
        frame_bytes = detector.get_frame_bytes()
        if frame_bytes:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + frame_bytes
                + b"\r\n"
            )
        elapsed = time.time() - t0
        sleep_t = interval - elapsed
        if sleep_t > 0:
            time.sleep(sleep_t)


@app.route("/video_feed")
def video_feed():
    return Response(
        _gen_mjpeg(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


# ── 推流：WebSocket（低延迟，推荐） ───────────────────────────────────

@sock.route("/ws/video")
def ws_video(ws):
    """
    WebSocket 视频推流端点。
    服务端主动推帧，客户端无需轮询，延迟比 MJPEG 低 50~100ms。
    帧格式：原始 JPEG 二进制（前端用 Blob URL 显示）
    """
    logger.info("WebSocket 视频连接已建立")
    interval = 1.0 / config.STREAM_WS_FPS

    try:
        while True:
            t0 = time.time()
            frame_bytes = detector.get_frame_bytes_nowait()
            if frame_bytes:
                ws.send(frame_bytes)   # 发送二进制 JPEG
            elapsed = time.time() - t0
            sleep_t = interval - elapsed
            if sleep_t > 0:
                time.sleep(sleep_t)
    except Exception:
        # 客户端断开连接时正常退出
        logger.info("WebSocket 视频连接已断开")


def start_web():
    logger.info(f"Web服务启动: http://{config.WEB_HOST}:{config.WEB_PORT}")
    app.run(
        host=config.WEB_HOST,
        port=config.WEB_PORT,
        threaded=True,
        use_reloader=False,
    )
