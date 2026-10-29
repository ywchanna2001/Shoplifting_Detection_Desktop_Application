"""Runs the exported YOLO ONNX model on single video frames using ONNX Runtime.

The app does not need PyTorch or Ultralytics at runtime: pre-processing (letterbox)
and post-processing (decoding boxes, NMS) are implemented here with NumPy and OpenCV.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

DEFAULT_CLASS_NAMES = {0: "normal", 1: "shoplifting"}
DEFAULT_INPUT_SIZE = 640
LETTERBOX_COLOR = (114, 114, 114)  # same grey padding Ultralytics uses during training


@dataclass(frozen=True)
class Detection:
    box: tuple[float, float, float, float]  # x1, y1, x2, y2 in original frame pixels
    confidence: float
    class_id: int
    label: str


class Detector:
    def __init__(
        self,
        model_path: str | Path,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.5,
    ) -> None:
        model_path = Path(model_path)
        if not model_path.is_file():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self._session = ort.InferenceSession(
            str(model_path), sess_options=options, providers=["CPUExecutionProvider"]
        )

        model_input = self._session.get_inputs()[0]
        self._input_name = model_input.name
        height, width = model_input.shape[2:4]
        # Dynamic dimensions are reported as strings; fall back to the training size.
        self.input_size = (
            width if isinstance(width, int) else DEFAULT_INPUT_SIZE,
            height if isinstance(height, int) else DEFAULT_INPUT_SIZE,
        )
        self._input_dtype = np.float16 if "float16" in model_input.type else np.float32

        self.model_path = model_path
        self.class_names = self._read_class_names()
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold

    def _read_class_names(self) -> dict[int, str]:
        """Ultralytics stores class names in the ONNX metadata as a dict literal string."""
        raw = self._session.get_modelmeta().custom_metadata_map.get("names")
        if raw:
            try:
                return {int(k): str(v) for k, v in ast.literal_eval(raw).items()}
            except (ValueError, SyntaxError, AttributeError):
                pass
        return dict(DEFAULT_CLASS_NAMES)

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Detect people in one BGR frame (as returned by OpenCV)."""
        blob, scale, (pad_x, pad_y) = self._preprocess(frame)
        output = self._session.run(None, {self._input_name: blob})[0]
        boxes, scores, class_ids = self._postprocess(output)
        if len(boxes) == 0:
            return []

        # Undo the letterbox so boxes are in original frame coordinates.
        height, width = frame.shape[:2]
        boxes[:, [0, 2]] = ((boxes[:, [0, 2]] - pad_x) / scale).clip(0, width)
        boxes[:, [1, 3]] = ((boxes[:, [1, 3]] - pad_y) / scale).clip(0, height)

        return [
            Detection(
                box=tuple(float(v) for v in box),
                confidence=float(score),
                class_id=int(class_id),
                label=self.class_names.get(int(class_id), str(int(class_id))),
            )
            for box, score, class_id in zip(boxes, scores, class_ids)
        ]

    def _preprocess(self, frame: np.ndarray) -> tuple[np.ndarray, float, tuple[int, int]]:
        """Resize keeping the aspect ratio, then pad to the model input size (letterbox)."""
        in_w, in_h = self.input_size
        height, width = frame.shape[:2]
        scale = min(in_w / width, in_h / height)
        new_w, new_h = round(width * scale), round(height * scale)

        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        left = (in_w - new_w) // 2
        top = (in_h - new_h) // 2
        padded = cv2.copyMakeBorder(
            resized,
            top,
            in_h - new_h - top,
            left,
            in_w - new_w - left,
            cv2.BORDER_CONSTANT,
            value=LETTERBOX_COLOR,
        )

        rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
        blob = rgb.transpose(2, 0, 1)[np.newaxis].astype(np.float32) / 255.0  # HWC -> NCHW, 0-1
        return np.ascontiguousarray(blob, dtype=self._input_dtype), scale, (left, top)

    def _postprocess(self, output: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Handle both YOLO ONNX output layouts.

        - NMS-free (end-to-end) models output (1, N, 6): [x1, y1, x2, y2, score, class].
        - Classic models output (1, 4 + classes, anchors): [cx, cy, w, h, class scores...].
        """
        preds = output[0].astype(np.float32)
        if preds.shape[0] < preds.shape[1]:
            return self._decode_raw(preds.T)
        return self._decode_end_to_end(preds)

    def _decode_end_to_end(self, preds: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        preds = preds[preds[:, 4] >= self.conf_threshold]
        return preds[:, :4].copy(), preds[:, 4].copy(), preds[:, 5].astype(int)

    def _decode_raw(self, preds: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        class_scores = preds[:, 4:]
        class_ids = class_scores.argmax(axis=1)
        scores = class_scores.max(axis=1)

        keep = scores >= self.conf_threshold
        preds, scores, class_ids = preds[keep], scores[keep], class_ids[keep]
        if len(preds) == 0:
            return np.empty((0, 4), np.float32), scores, class_ids

        cx, cy, w, h = preds[:, 0], preds[:, 1], preds[:, 2], preds[:, 3]
        x1, y1 = cx - w / 2, cy - h / 2
        xywh = np.stack([x1, y1, w, h], axis=1)

        # Per-class non-maximum suppression removes duplicate boxes for the same person.
        indices = cv2.dnn.NMSBoxesBatched(
            xywh.tolist(), scores.tolist(), class_ids.tolist(),
            self.conf_threshold, self.iou_threshold,
        )
        indices = np.asarray(indices, dtype=int).reshape(-1)

        boxes = np.stack([x1, y1, x1 + w, y1 + h], axis=1)
        return boxes[indices], scores[indices], class_ids[indices]
