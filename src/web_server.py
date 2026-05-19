"""
Web 服务模块 — Flask + Flask-SocketIO 应用工厂

提供 REST API 和 WebSocket 视频推流。

REST 端点:
  GET  /api/status              — 系统状态
  POST /api/mode                — 切换控制模式
  POST /api/servo/move          — 舵机移动到指定角度
  POST /api/servo/calibrate     — 舵机校准
  POST /api/servo/set_neutral   — 设置舵机中位角度
  POST /api/servo/set_on_offset — 设置开灯偏移
  POST /api/servo/set_off_offset— 设置关灯偏移
  POST /api/light/threshold     — 设置光照阈值
  POST /api/light/use_current   — 使用当前光照读数作为阈值
  POST /api/conditions          — 设置灯光条件配置
  GET  /api/conditions          — 获取灯光条件配置
  POST /api/time/fallback       — 设置时间回退配置
  POST /api/ac/thresholds       — 设置温度阈值
  POST /api/ir/learn            — 红外学习
  POST /api/ir/send             — 红外发送
  GET  /api/ir/commands         — 红外命令列表
  DELETE /api/ir/commands/<name> — 删除红外命令
  POST /api/ir/wizard/start     — 启动IR录制向导
  POST /api/ir/wizard/record    — 录制当前步骤
  POST /api/ir/wizard/skip      — 跳过当前步骤
  POST /api/ir/wizard/retry     — 重试当前步骤
  GET  /api/ir/wizard/status    — 获取向导状态

WebSocket:
  'video_frame' 事件 — base64 编码的 JPEG 帧
  'metrics' 事件     — fps / inference_ms 性能指标
"""

from __future__ import annotations

import base64
import logging
import os
import time
import threading
from pathlib import Path

from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit

logger = logging.getLogger(__name__)

# 路径计算（相对于本文件所在的 src/ 目录）
_SRC_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SRC_DIR.parent
_TEMPLATE_DIR = _PROJECT_ROOT / "templates"
_ASSETS_DIR = _PROJECT_ROOT / "assets"


def create_app(engine) -> tuple[Flask, SocketIO]:
    """应用工厂：创建 Flask + SocketIO 实例。

    Args:
        engine: DecisionEngine 实例，提供 get_state() 及各子组件接口。

    Returns:
        (app, socketio) 元组
    """
    app = Flask(
        __name__,
        template_folder=str(_TEMPLATE_DIR),
        static_folder=str(_ASSETS_DIR),
        static_url_path="/assets",
    )
    app.config["SECRET_KEY"] = "smart-room-control-secret"

    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

    # ------------------------------------------------------------------
    # 页面路由
    # ------------------------------------------------------------------

    @app.route("/")
    def index():
        """主页"""
        return render_template("index.html")

    @app.route("/favicon.ico")
    def favicon():
        """Favicon"""
        return send_from_directory(
            str(_ASSETS_DIR), "favicon.ico", mimetype="image/x-icon"
        )

    # ------------------------------------------------------------------
    # REST API
    # ------------------------------------------------------------------

    @app.route("/api/status", methods=["GET"])
    def api_status():
        """返回系统当前状态"""
        try:
            state = engine.get_state()
            return jsonify(state), 200
        except Exception as e:
            logger.error("获取状态失败: %s", e)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/mode", methods=["POST"])
    def api_mode():
        """切换控制模式 (AUTO / MANUAL)"""
        data = request.get_json(silent=True) or {}
        mode = data.get("mode", "")
        if not mode:
            return jsonify({"error": "缺少 mode 参数"}), 400
        try:
            new_mode = engine.set_mode(mode)
            return jsonify({"ok": True, "mode": new_mode}), 200
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @app.route("/api/servo/move", methods=["POST"])
    def api_servo_move():
        """移动舵机到指定角度，或执行开灯/关灯动作序列。"""
        data = request.get_json(silent=True) or {}
        action = (data.get("action") or "").strip().lower()

        # 网页端的“开灯/关灯”按钮应该走完整动作序列：
        # neutral → target → pause → neutral
        if action == "on":
            try:
                engine.servo.press_on()
                servo_status = engine.servo.get_status()
                return jsonify({"ok": True, "action": "on", "servo": servo_status}), 200
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        if action == "off":
            try:
                engine.servo.press_off()
                servo_status = engine.servo.get_status()
                return jsonify({"ok": True, "action": "off", "servo": servo_status}), 200
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        try:
            angle = int(data.get("angle"))
        except (TypeError, ValueError):
            return jsonify({"error": "无效角度值"}), 400
        try:
            engine.servo.move_to(angle)
            return jsonify({"ok": True, "angle": angle}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/servo/calibrate", methods=["POST"])
    def api_servo_calibrate():
        """校准舵机预设角度"""
        data = request.get_json(silent=True) or {}
        preset = data.get("preset")
        angle = data.get("angle")
        if preset is None or angle is None:
            return jsonify({"error": "缺少 preset 或 angle 参数"}), 400
        try:
            angle = int(angle)
        except (TypeError, ValueError):
            return jsonify({"error": "无效角度值"}), 400
        try:
            engine.servo.calibrate(preset, angle)
            engine.servo.save_calibration()
            return jsonify({"ok": True, "preset": preset, "angle": angle}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/ir/learn", methods=["POST"])
    def api_ir_learn():
        """开始红外学习"""
        data = request.get_json(silent=True) or {}
        name = data.get("name")
        if not name:
            return jsonify({"error": "缺少 name 参数"}), 400
        try:
            result = engine.ir_controller.start_learning(name)
            return jsonify({"ok": True, "name": name, "result": result}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/ir/send", methods=["POST"])
    def api_ir_send():
        """发送红外命令"""
        data = request.get_json(silent=True) or {}
        name = data.get("name")
        if not name:
            return jsonify({"error": "缺少 name 参数"}), 400
        try:
            success = engine.ir_controller.send_command(name)
            return jsonify({"ok": success, "name": name}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/ir/commands", methods=["GET"])
    def api_ir_commands():
        """列出所有已学习的红外命令"""
        try:
            commands = engine.ir_controller.list_commands()
            return jsonify({"commands": commands}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/ir/commands/<name>", methods=["DELETE"])
    def api_ir_delete_command(name):
        """删除指定红外命令"""
        try:
            success = engine.ir_controller.delete_command(name)
            if success:
                return jsonify({"ok": True, "deleted": name}), 200
            else:
                return jsonify({"error": f"命令 '{name}' 不存在"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ------------------------------------------------------------------
    # 舵机校准端点
    # ------------------------------------------------------------------

    @app.route("/api/servo/set_neutral", methods=["POST"])
    def api_servo_set_neutral():
        """设置舵机中位角度并立即移动到该位置"""
        data = request.get_json(silent=True) or {}
        try:
            angle = int(data.get("angle"))
        except (TypeError, ValueError):
            return jsonify({"error": "无效角度值"}), 400
        try:
            engine.servo.set_neutral(angle)
            return jsonify({"ok": True, "neutral_angle": angle}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/servo/set_on_offset", methods=["POST"])
    def api_servo_set_on_offset():
        """设置开灯偏移并执行测试动作"""
        data = request.get_json(silent=True) or {}
        try:
            offset = int(data.get("offset"))
        except (TypeError, ValueError):
            return jsonify({"error": "无效偏移值"}), 400
        try:
            engine.servo.set_on_offset(offset)
            return jsonify({"ok": True, "on_offset": offset}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/servo/set_off_offset", methods=["POST"])
    def api_servo_set_off_offset():
        """设置关灯偏移并执行测试动作"""
        data = request.get_json(silent=True) or {}
        try:
            offset = int(data.get("offset"))
        except (TypeError, ValueError):
            return jsonify({"error": "无效偏移值"}), 400
        try:
            engine.servo.set_off_offset(offset)
            return jsonify({"ok": True, "off_offset": offset}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ------------------------------------------------------------------
    # 光照阈值端点
    # ------------------------------------------------------------------

    @app.route("/api/light/threshold", methods=["POST"])
    def api_light_threshold():
        """设置光照不足阈值 (lux)"""
        data = request.get_json(silent=True) or {}
        try:
            threshold = float(data.get("threshold"))
        except (TypeError, ValueError):
            return jsonify({"error": "无效阈值"}), 400
        if threshold <= 0:
            return jsonify({"error": "阈值必须为正数"}), 400
        try:
            engine.light_sensor.set_threshold(threshold)
            # 持久化到 UserSettings
            from src import user_settings
            user_settings.set("dark_threshold", threshold)
            return jsonify({"ok": True, "dark_threshold": threshold}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/light/use_current", methods=["POST"])
    def api_light_use_current():
        """使用当前光照读数作为阈值"""
        try:
            current_lux = engine.light_sensor.read_lux()
            if current_lux <= 0:
                return jsonify({"error": "当前光照读数无效 (<=0)"}), 400
            engine.light_sensor.set_threshold(current_lux)
            # 持久化到 UserSettings
            from src import user_settings
            user_settings.set("dark_threshold", current_lux)
            return jsonify({"ok": True, "dark_threshold": current_lux}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ------------------------------------------------------------------
    # 条件配置端点
    # ------------------------------------------------------------------

    @app.route("/api/conditions", methods=["GET"])
    def api_conditions_get():
        """获取灯光条件启用配置"""
        try:
            config = engine.condition_evaluator.config
            return jsonify({
                "time_enabled": config.time_enabled,
                "light_enabled": config.light_enabled,
                "presence_enabled": config.presence_enabled,
            }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/conditions", methods=["POST"])
    def api_conditions_set():
        """设置灯光条件启用配置"""
        data = request.get_json(silent=True) or {}
        try:
            from src.condition_evaluator import ConditionConfig
            from src import user_settings

            # 获取当前配置作为基础，仅更新提供的字段
            current = engine.condition_evaluator.config
            time_enabled = data.get("time_enabled", current.time_enabled)
            light_enabled = data.get("light_enabled", current.light_enabled)
            presence_enabled = data.get("presence_enabled", current.presence_enabled)

            new_config = ConditionConfig(
                time_enabled=bool(time_enabled),
                light_enabled=bool(light_enabled),
                presence_enabled=bool(presence_enabled),
            )
            engine.condition_evaluator.update_config(new_config)

            # 持久化到 UserSettings
            user_settings.set("light_conditions", {
                "time_enabled": new_config.time_enabled,
                "light_enabled": new_config.light_enabled,
                "presence_enabled": new_config.presence_enabled,
            })

            return jsonify({
                "ok": True,
                "time_enabled": new_config.time_enabled,
                "light_enabled": new_config.light_enabled,
                "presence_enabled": new_config.presence_enabled,
            }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ------------------------------------------------------------------
    # 时间回退配置端点
    # ------------------------------------------------------------------

    @app.route("/api/time/fallback", methods=["POST"])
    def api_time_fallback():
        """设置时间条件回退白天时间范围"""
        data = request.get_json(silent=True) or {}
        start = data.get("start")
        end = data.get("end")
        if not start or not end:
            return jsonify({"error": "缺少 start 或 end 参数"}), 400
        try:
            engine.time_condition.set_fallback(start, end)
            # 持久化到 UserSettings
            from src import user_settings
            user_settings.set("fallback_daytime", {"start": start, "end": end})
            return jsonify({"ok": True, "start": start, "end": end}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ------------------------------------------------------------------
    # 温度阈值端点
    # ------------------------------------------------------------------

    @app.route("/api/ac/thresholds", methods=["POST"])
    def api_ac_thresholds():
        """设置空调温度阈值"""
        data = request.get_json(silent=True) or {}
        try:
            cooling = data.get("cooling")
            heating = data.get("heating")
            if cooling is None and heating is None:
                return jsonify({"error": "缺少 cooling 或 heating 参数"}), 400

            from src import user_settings

            if cooling is not None:
                cooling = float(cooling)
                engine.ac_controller.cooling_threshold = cooling
            if heating is not None:
                heating = float(heating)
                engine.ac_controller.heating_threshold = heating

            # 持久化到 UserSettings
            user_settings.set("ac_thresholds", {
                "cooling": engine.ac_controller.cooling_threshold,
                "heating": engine.ac_controller.heating_threshold,
            })

            return jsonify({
                "ok": True,
                "cooling": engine.ac_controller.cooling_threshold,
                "heating": engine.ac_controller.heating_threshold,
            }), 200
        except (TypeError, ValueError):
            return jsonify({"error": "无效温度值"}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ------------------------------------------------------------------
    # 模型切换端点
    # ------------------------------------------------------------------

    @app.route("/api/model/switch", methods=["POST"])
    def api_model_switch():
        """切换 YOLO 检测模型"""
        data = request.get_json(silent=True) or {}
        model = data.get("model")
        if not model:
            return jsonify({"error": "缺少 model 参数"}), 400
        try:
            result = engine.detector.switch_model(model)
            if result.get("ok"):
                from src import user_settings
                user_settings.set("yolo_model", model)
                return jsonify({"ok": True, "model": model, "status": "switching"}), 202
            else:
                return jsonify({"error": result.get("error", "切换失败")}), 500
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ------------------------------------------------------------------
    # IR Wizard 端点
    # ------------------------------------------------------------------

    # 模块级 IR Wizard 实例
    _ir_wizard_holder = {"instance": None}

    def _get_or_create_wizard():
        """获取或创建 IRWizard 实例"""
        if _ir_wizard_holder["instance"] is None:
            from src.ir_wizard import IRWizard
            _ir_wizard_holder["instance"] = IRWizard(engine.ir_controller)
        return _ir_wizard_holder["instance"]

    @app.route("/api/ir/wizard/start", methods=["POST"])
    def api_ir_wizard_start():
        """启动IR录制向导"""
        try:
            from src.ir_wizard import IRWizard
            # 每次启动创建新实例
            _ir_wizard_holder["instance"] = IRWizard(engine.ir_controller)
            wizard = _ir_wizard_holder["instance"]
            result = wizard.start()
            return jsonify(result), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/ir/wizard/record", methods=["POST"])
    def api_ir_wizard_record():
        """录制当前步骤"""
        try:
            wizard = _get_or_create_wizard()
            data = request.get_json(silent=True) or {}
            timeout = data.get("timeout", 10.0)
            result = wizard.record_current(timeout=float(timeout))
            return jsonify(result), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/ir/wizard/skip", methods=["POST"])
    def api_ir_wizard_skip():
        """跳过当前步骤"""
        try:
            wizard = _get_or_create_wizard()
            result = wizard.skip_current()
            return jsonify(result), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/ir/wizard/retry", methods=["POST"])
    def api_ir_wizard_retry():
        """重试当前步骤"""
        try:
            wizard = _get_or_create_wizard()
            result = wizard.retry_current()
            return jsonify(result), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/ir/wizard/status", methods=["GET"])
    def api_ir_wizard_status():
        """获取向导状态"""
        try:
            wizard = _get_or_create_wizard()
            result = wizard.get_status()
            return jsonify(result), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ------------------------------------------------------------------
    # WebSocket 视频推流
    # ------------------------------------------------------------------

    @socketio.on("connect")
    def handle_connect():
        """客户端连接"""
        logger.info("WebSocket 客户端已连接")

    @socketio.on("disconnect")
    def handle_disconnect():
        """客户端断开"""
        logger.info("WebSocket 客户端已断开")

    @socketio.on("request_video")
    def handle_request_video():
        """客户端请求视频流，启动后台推帧线程"""
        _start_video_stream(socketio, engine)

    # ------------------------------------------------------------------
    # 视频推流后台线程
    # ------------------------------------------------------------------

    def _start_video_stream(sio: SocketIO, eng) -> None:
        """启动后台线程，持续推送视频帧和性能指标。"""

        def _stream_loop():
            fps_counter = 0
            fps_timer = time.time()
            current_fps = 0.0

            while True:
                try:
                    t0 = time.time()

                    # 获取最新帧
                    frame = eng.detector.get_latest_frame()
                    if frame is not None:
                        # 编码为 base64 JPEG
                        import cv2
                        _, jpeg_buf = cv2.imencode(
                            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70]
                        )
                        frame_b64 = base64.b64encode(jpeg_buf.tobytes()).decode("utf-8")

                        # 推送帧
                        sio.emit("video_frame", {"data": frame_b64})

                    inference_ms = (time.time() - t0) * 1000

                    # 计算 FPS
                    fps_counter += 1
                    elapsed_fps = time.time() - fps_timer
                    if elapsed_fps >= 1.0:
                        current_fps = fps_counter / elapsed_fps
                        fps_counter = 0
                        fps_timer = time.time()

                    # 推送性能指标
                    sio.emit("metrics", {
                        "fps": round(current_fps, 1),
                        "inference_ms": round(inference_ms, 1),
                    })

                    # 控制帧率 (~15 fps)
                    sleep_time = max(0, (1.0 / 15) - (time.time() - t0))
                    time.sleep(sleep_time)

                except Exception as e:
                    logger.warning("视频推流异常: %s", e)
                    time.sleep(1.0)

        thread = threading.Thread(target=_stream_loop, name="VideoStream", daemon=True)
        thread.start()

    return app, socketio
