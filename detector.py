"""
YOLO人员检测模块

摄像头后端优先级（自动选择最优）:
  1. Picamera2  — 树莓派 CSI 摄像头，MIPI 总线，延迟最低
  2. V4L2       — Linux USB 摄像头，直接访问驱动（等效 Windows CAP_DSHOW）
  3. OpenCV默认 — 兜底，Windows/macOS 开发用

推流架构:
  读帧线程  → 全速采集，缓冲区=1，不积压旧帧
  检测线程  → 按间隔独立推理，不阻塞画面
  帧队列    → maxsize=1，推流端永远拿最新帧（丢弃积压）
  WebSocket → 服务端主动推帧，比 MJPEG 轮询延迟低 50~100ms

性能统计:
  capture_fps   采集帧率（摄像头实际输出）
  stream_fps    推流帧率（发送给浏览器的帧率）
  infer_ms      单帧推理耗时(ms)
  infer_fps     推理帧率上限
  camera_backend 当前使用的摄像头后端
"""

import cv2
import os
import sys
import time
import queue
import threading
import logging
import numpy as np
from ultralytics import YOLO
import config

logger = logging.getLogger(__name__)

# ── 尝试导入 Picamera2（仅树莓派有） ──────────────────────────────────
try:
    from picamera2 import Picamera2
    HAS_PICAMERA2 = True
except ImportError:
    HAS_PICAMERA2 = False


def _make_placeholder_frame(msg="未检测到摄像头"):
    frame = np.zeros((config.CAMERA_HEIGHT, config.CAMERA_WIDTH, 3), dtype=np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    lines = [msg, "Simulated Mode", time.strftime("%H:%M:%S")]
    y0 = config.CAMERA_HEIGHT // 2 - 30
    for i, line in enumerate(lines):
        tw = cv2.getTextSize(line, font, 0.7, 2)[0][0]
        x = (config.CAMERA_WIDTH - tw) // 2
        cv2.putText(frame, line, (x, y0 + i * 35), font, 0.7, (0, 200, 100), 2)
    return frame


class PersonDetector:
    """人员检测器，自动选择最优摄像头后端"""

    def __init__(self):
        self.model = YOLO(config.YOLO_MODEL)
        self.model_name = config.YOLO_MODEL
        self.model_loading = False
        self._model_lock = threading.Lock()

        # 摄像头状态
        self.cap = None           # OpenCV VideoCapture（V4L2/默认后端）
        self.picam2 = None        # Picamera2 实例
        self.camera_backend = "none"
        self.simulated = False
        self.running = False
        self.detection_interval = config.DETECTION_INTERVAL

        # 帧存储
        # _raw_frame    : 最新原始帧（推流/GUI 永远用这个，保证流畅）
        # _boxes_overlay: 最新检测框数据（叠加到原始帧上，不替换原始帧）
        # _annotated_frame: 已废弃，保留字段避免外部引用报错
        self._raw_frame = None
        self._annotated_frame = None   # 不再用于推流，仅兼容保留
        self._last_boxes = []          # 检测框列表 [(x1,y1,x2,y2,conf,cls), ...]
        self._last_labels = []         # 对应标签文字
        self._frame_queue = queue.Queue(maxsize=1)
        self._frame_lock = threading.Lock()
        self._detect_lock = threading.Lock()

        # 检测结果状态（必须在启动线程前初始化，否则 get_status() 会报 AttributeError）
        self.person_count = 0
        self.last_detection_time = 0.0

        # 性能统计
        self._capture_fps = 0.0
        self._stream_fps = 0.0
        self._infer_ms = 0.0
        self._cap_count = 0
        self._stream_count = 0
        self._fps_ts = time.time()
        self._perf_lock = threading.Lock()

        logger.info(f"YOLO模型 [{self.model_name}] 加载完成")

    # ------------------------------------------------------------------ #
    #  摄像头初始化 — 自动选择最优后端
    # ------------------------------------------------------------------ #

    def _try_picamera2(self):
        """尝试 Picamera2（CSI 摄像头，树莓派专用）"""
        if not HAS_PICAMERA2:
            return False
        try:
            picam2 = Picamera2()
            cfg = picam2.create_video_configuration(
                main={
                    "size": (config.CAMERA_WIDTH, config.CAMERA_HEIGHT),
                    "format": "RGB888",   # 直接输出 RGB，省去颜色转换
                },
                controls={
                    "FrameRate": config.CAMERA_TARGET_FPS,
                    "NoiseReductionMode": 0,  # 关闭降噪，降低延迟
                },
                buffer_count=2,           # 最小缓冲，降低延迟
            )
            picam2.configure(cfg)
            picam2.start()
            time.sleep(0.5)  # 等待曝光稳定
            self.picam2 = picam2
            self.camera_backend = "Picamera2(CSI)"
            logger.info("摄像头后端: Picamera2 (CSI)")
            return True
        except Exception as e:
            logger.debug(f"Picamera2 不可用: {e}")
            return False

    def _try_v4l2(self):
        """尝试 V4L2 后端（Linux USB 摄像头，直接访问驱动）"""
        if sys.platform != "linux":
            return False
        try:
            cap = cv2.VideoCapture(config.CAMERA_SOURCE, cv2.CAP_V4L2)
            if not cap.isOpened():
                cap.release()
                return False
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
            cap.set(cv2.CAP_PROP_FPS, config.CAMERA_TARGET_FPS)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)   # 关键：缓冲区=1，不积压旧帧
            # 请求 MJPEG 格式（USB 摄像头硬件压缩，传输带宽低，帧率高）
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            ret, _ = cap.read()
            if not ret:
                cap.release()
                return False
            self.cap = cap
            self.camera_backend = "V4L2(USB)"
            logger.info("摄像头后端: V4L2 (USB)")
            return True
        except Exception as e:
            logger.debug(f"V4L2 不可用: {e}")
            return False

    def _try_default(self):
        """兜底：OpenCV 默认后端（Windows/macOS 开发用）"""
        try:
            # Windows 用 CAP_DSHOW，其他平台用默认
            backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
            cap = cv2.VideoCapture(config.CAMERA_SOURCE, backend)
            if not cap.isOpened():
                cap.release()
                return False
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
            cap.set(cv2.CAP_PROP_FPS, config.CAMERA_TARGET_FPS)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.cap = cap
            self.camera_backend = "DSHOW(Win)" if sys.platform == "win32" else "Default"
            logger.info(f"摄像头后端: {self.camera_backend}")
            return True
        except Exception as e:
            logger.debug(f"默认后端不可用: {e}")
            return False

    def _try_open_camera(self):
        """按优先级尝试各后端，全部失败则进入模拟模式"""
        # 优先级: Picamera2 > V4L2 > 默认后端
        if self._try_picamera2():
            return
        if self._try_v4l2():
            return
        if self._try_default():
            return
        # 全部失败
        self.simulated = True
        self.camera_backend = "Simulated"
        logger.warning("未检测到摄像头，已切换到模拟模式")

    # ------------------------------------------------------------------ #
    #  读帧线程
    # ------------------------------------------------------------------ #

    def _push_frame(self, frame):
        """将帧推入队列（丢弃积压，保证推流端拿到最新帧）"""
        with self._frame_lock:
            self._raw_frame = frame
        # 队列满时丢弃旧帧，放入新帧
        try:
            self._frame_queue.get_nowait()
        except queue.Empty:
            pass
        try:
            self._frame_queue.put_nowait(frame)
        except queue.Full:
            pass
        # 统计采集帧率
        with self._perf_lock:
            self._cap_count += 1
            now = time.time()
            elapsed = now - self._fps_ts
            if elapsed >= 1.0:
                self._capture_fps = round(self._cap_count / elapsed, 1)
                self._cap_count = 0
                self._fps_ts = now

    def _capture_loop_picamera2(self):
        """Picamera2 读帧循环（CSI 摄像头）"""
        logger.info("Picamera2 读帧线程已启动")
        while self.running:
            # capture_array 直接返回 numpy array，无需解码
            frame_rgb = self.picam2.capture_array()
            # Picamera2 输出 RGB，OpenCV/YOLO 需要 BGR
            frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
            self._push_frame(frame_bgr)

    def _capture_loop_opencv(self):
        """OpenCV 读帧循环（USB/默认后端）"""
        logger.info(f"OpenCV 读帧线程已启动 [{self.camera_backend}]")
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.02)
                continue
            self._push_frame(frame)

    def _simulated_capture_loop(self):
        logger.info("模拟读帧线程已启动")
        while self.running:
            frame = _make_placeholder_frame()
            self._push_frame(frame)
            time.sleep(1)

    # ------------------------------------------------------------------ #
    #  检测线程
    # ------------------------------------------------------------------ #

    def _detect_loop(self):
        logger.info("检测线程已启动")
        while self.running:
            time.sleep(self.detection_interval)
            if self.model_loading:
                continue

            with self._frame_lock:
                frame = self._raw_frame.copy() if self._raw_frame is not None else None

            if frame is None or self.simulated:
                with self._detect_lock:
                    self.person_count = 0
                    self.last_detection_time = time.time()
                continue

            t0 = time.perf_counter()
            with self._model_lock:
                results = self.model(
                    frame,
                    classes=[config.PERSON_CLASS_ID],
                    conf=config.YOLO_CONFIDENCE,
                    verbose=False,
                )
            infer_ms = (time.perf_counter() - t0) * 1000

            count = len(results[0].boxes)
            annotated = results[0].plot()

            with self._detect_lock:
                self.person_count = count
                self._annotated_frame = annotated   # 兼容保留，不用于推流
                self.last_detection_time = time.time()
                # 保存检测框，用于叠加到最新原始帧
                self._last_boxes = []
                self._last_labels = []
                for box in results[0].boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    conf = float(box.conf[0])
                    cls  = int(box.cls[0])
                    name = results[0].names.get(cls, str(cls))
                    self._last_boxes.append((int(x1), int(y1), int(x2), int(y2)))
                    self._last_labels.append(f"{name} {conf:.2f}")

            with self._perf_lock:
                self._infer_ms = round(infer_ms, 1)

            logger.debug(f"检测到 {count} 人  推理耗时 {infer_ms:.0f}ms")

    # ------------------------------------------------------------------ #
    #  启动 / 停止
    # ------------------------------------------------------------------ #

    def start(self):
        self._try_open_camera()
        self.running = True

        if self.simulated:
            t_cap = threading.Thread(target=self._simulated_capture_loop, daemon=True)
        elif self.picam2 is not None:
            t_cap = threading.Thread(target=self._capture_loop_picamera2, daemon=True)
        else:
            t_cap = threading.Thread(target=self._capture_loop_opencv, daemon=True)

        t_det = threading.Thread(target=self._detect_loop, daemon=True)
        t_cap.start()
        t_det.start()
        return t_cap, t_det

    def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()
        if self.picam2:
            self.picam2.stop()
        logger.info("检测器已停止")

    # ------------------------------------------------------------------ #
    #  模型热切换
    # ------------------------------------------------------------------ #

    def switch_model(self, model_path):
        model_path = model_path.strip()
        if not model_path:
            return {"ok": False, "error": "模型路径不能为空"}
        is_builtin = os.path.sep not in model_path and not model_path.startswith(".")
        if not is_builtin and not os.path.exists(model_path):
            return {"ok": False, "error": f"文件不存在: {model_path}"}

        logger.info(f"开始切换模型: {model_path}")
        self.model_loading = True

        def _load():
            try:
                new_model = YOLO(model_path)
                with self._model_lock:
                    self.model = new_model
                    self.model_name = model_path
                with self._detect_lock:
                    self._annotated_frame = None
                    self.person_count = 0
                with self._perf_lock:
                    self._infer_ms = 0.0
                logger.info(f"模型切换成功: {model_path}")
            except Exception as e:
                logger.error(f"模型切换失败: {e}")
            finally:
                self.model_loading = False

        threading.Thread(target=_load, daemon=True).start()
        return {"ok": True, "model": model_path}

    # ------------------------------------------------------------------ #
    #  对外接口
    # ------------------------------------------------------------------ #

    def set_detection_interval(self, seconds):
        seconds = max(0.5, min(30.0, float(seconds)))
        self.detection_interval = seconds
        logger.info(f"检测间隔已更新为 {seconds}s")
        return seconds

    def get_status(self):
        with self._detect_lock:
            person_count = self.person_count
            last_det = self.last_detection_time
        with self._perf_lock:
            cap_fps = self._capture_fps
            infer_ms = self._infer_ms
        return {
            "person_count": person_count,
            "has_person": person_count > 0,
            "last_detection_time": last_det,
            "detection_interval": self.detection_interval,
            "simulated": self.simulated,
            "camera_backend": self.camera_backend,
            "model_name": self.model_name,
            "model_loading": self.model_loading,
            "stream_fps": cap_fps,       # 采集帧率即推流帧率上限
            "infer_ms": infer_ms,
            "infer_fps": round(1000 / infer_ms, 1) if infer_ms > 0 else 0,
        }

    def _overlay_boxes(self, frame: np.ndarray) -> np.ndarray:
        """
        将最新检测框叠加到原始帧副本上。
        推流/GUI 调用此方法，原始帧不受影响，永远保持最新。
        """
        with self._detect_lock:
            boxes  = list(self._last_boxes)
            labels = list(self._last_labels)
        if not boxes:
            return frame
        out = frame.copy()
        for (x1, y1, x2, y2), label in zip(boxes, labels):
            cv2.rectangle(out, (x1, y1), (x2, y2), (78, 204, 163), 2)
            # 标签背景
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            cv2.rectangle(out, (x1, y1 - th - 6), (x1 + tw + 4, y1), (78, 204, 163), -1)
            cv2.putText(out, label, (x1 + 2, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (20, 20, 40), 1)
        return out

    def get_latest_frame(self) -> np.ndarray | None:
        """
        获取最新原始帧并叠加检测框（GUI 专用，返回 numpy array）。
        永远基于最新原始帧，不会因推理延迟而冻结。
        """
        with self._frame_lock:
            frame = self._raw_frame
        if frame is None:
            return None
        return self._overlay_boxes(frame)

    def get_frame_bytes(self) -> bytes | None:
        """Web MJPEG 推流用，永远基于最新原始帧 + 叠加检测框"""
        with self._frame_lock:
            frame = self._raw_frame
        if frame is None:
            try:
                frame = self._frame_queue.get(timeout=0.05)
            except queue.Empty:
                return None
        frame = self._overlay_boxes(frame)
        _, buf = cv2.imencode(
            ".jpg", frame,
            [cv2.IMWRITE_JPEG_QUALITY, config.STREAM_JPEG_QUALITY]
        )
        return buf.tobytes()

    def get_frame_bytes_nowait(self) -> bytes | None:
        """WebSocket 推流用，非阻塞，永远基于最新原始帧"""
        with self._frame_lock:
            frame = self._raw_frame
        if frame is None:
            return None
        frame = self._overlay_boxes(frame)
        _, buf = cv2.imencode(
            ".jpg", frame,
            [cv2.IMWRITE_JPEG_QUALITY, config.STREAM_JPEG_QUALITY]
        )
        return buf.tobytes()
