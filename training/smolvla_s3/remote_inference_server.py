"""Local-only HTTP server for remote SmolVLA chunk inference.

The server owns model loading and preprocessing only. It does not own Isaac,
ROS, workspace limits, safety, task evaluation, or command authority. Bind it
to loopback and expose it through an SSH tunnel from the local Isaac host.
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import logging
from pathlib import Path
import sys
import threading
import time
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


PROTOCOL_VERSION = "smolvla_remote_inference_v1"
ACTION_SCHEMA_VERSION = "panda_absolute_eef_gripper_v0"
CHUNK_SIZE = 10
EXECUTE_K = 5
STATE_DIM = 15
IMAGE_HEIGHT = 240
IMAGE_WIDTH = 320
IMAGE_SHAPE = (IMAGE_HEIGHT, IMAGE_WIDTH, 3)
MAX_REQUEST_BYTES = 1_000_000
DEFAULT_TASK = "pick up the red box and place it in the left bin"


def _decode_rgb(value: Any, name: str) -> np.ndarray:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be base64 text")
    try:
        raw = base64.b64decode(value.encode("ascii"), validate=True)
    except Exception as error:
        raise ValueError(f"{name} is not valid base64") from error
    import cv2

    decoded = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if decoded is None:
        raise ValueError(f"{name} is not a decodable JPEG")
    rgb = cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)
    if rgb.shape != IMAGE_SHAPE:
        raise ValueError(f"{name} shape={rgb.shape} expected={IMAGE_SHAPE}")
    return rgb


def _rgb_to_chw01(rgb: np.ndarray) -> np.ndarray:
    import cv2

    resized = cv2.resize(rgb, (IMAGE_WIDTH, IMAGE_HEIGHT), interpolation=cv2.INTER_AREA)
    return np.transpose(resized.astype(np.float32) / 255.0, (2, 0, 1))


def _encode_warmup_jpeg() -> bytes:
    import cv2

    image = np.zeros(IMAGE_SHAPE, dtype=np.uint8)
    ok, encoded = cv2.imencode(
        '.jpg', cv2.cvtColor(image, cv2.COLOR_RGB2BGR),
        [cv2.IMWRITE_JPEG_QUALITY, 95],
    )
    if not ok:
        raise RuntimeError('failed to encode warmup JPEG')
    return encoded.tobytes()


@dataclass
class LoadedPolicy:
    policy: Any
    preprocess: Any
    postprocess: Any
    torch: Any
    lock: threading.Lock
    base_dir: Path
    lora_dir: Path
    vlm_dir: Path

    def reset(self) -> None:
        reset = getattr(self.policy, "reset", None)
        if callable(reset):
            reset()
        elif hasattr(self.policy, "base_model"):
            reset = getattr(self.policy.base_model, "reset", None)
            if callable(reset):
                reset()

    def predict(self, request: dict[str, Any]) -> tuple[list[list[float]], float]:
        state = np.asarray(request.get("state"), dtype=np.float32).reshape(-1)
        if state.shape[0] != STATE_DIM or not np.isfinite(state).all():
            raise ValueError("state must be finite state[15]")
        if request.get("image_encoding") != "jpeg":
            raise ValueError("image_encoding must be jpeg")
        scene = _decode_rgb(request.get("scene_jpeg_b64"), "scene_jpeg_b64")
        wrist = _decode_rgb(request.get("wrist_jpeg_b64"), "wrist_jpeg_b64")
        task = str(request.get("task") or DEFAULT_TASK)
        if not task.endswith("\n"):
            task += "\n"
        batch_in = {
            "observation.state": self.torch.from_numpy(state).unsqueeze(0),
            "observation.images.scene": self.torch.from_numpy(
                _rgb_to_chw01(scene)
            ).unsqueeze(0),
            "observation.images.wrist": self.torch.from_numpy(
                _rgb_to_chw01(wrist)
            ).unsqueeze(0),
            "task": [task],
        }
        with self.lock:
            batch = self.preprocess(batch_in)
            with self.torch.inference_mode():
                self.torch.cuda.synchronize()
                started = time.perf_counter()
                if hasattr(self.policy, "predict_action_chunk"):
                    chunk = self.policy.predict_action_chunk(batch)
                elif hasattr(self.policy, "base_model") and hasattr(
                    self.policy.base_model, "predict_action_chunk"
                ):
                    chunk = self.policy.base_model.predict_action_chunk(batch)
                else:
                    raise RuntimeError("policy lacks predict_action_chunk")
                if self.postprocess is not None:
                    try:
                        chunk = self.postprocess(chunk)
                    except Exception:
                        chunk = self.torch.stack(
                            [self.postprocess(chunk[:, i, :]) for i in range(chunk.shape[1])],
                            dim=1,
                        )
                self.torch.cuda.synchronize()
                latency_ms = (time.perf_counter() - started) * 1000.0
        values = chunk.detach().float().cpu().numpy()
        if values.ndim == 3:
            values = values[0]
        if values.ndim != 2 or values.shape[0] < CHUNK_SIZE or values.shape[1] < 8:
            raise ValueError(f"policy returned invalid chunk shape={values.shape}")
        actions = values[:CHUNK_SIZE, :8].astype(np.float64).tolist()
        if not np.isfinite(np.asarray(actions, dtype=np.float64)).all():
            raise ValueError("policy returned non-finite action")
        return actions, latency_ms


class InferenceHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "SmolVLAInference/1"

    @property
    def state(self) -> dict[str, Any]:
        return self.server.state  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: Any) -> None:
        logging.getLogger("smolvla.remote").info(format, *args)

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/healthz":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        loaded: LoadedPolicy = self.state["policy"]
        self._send_json(
            HTTPStatus.OK,
            {
                "protocol_version": PROTOCOL_VERSION,
                "status": "ready",
                "gpu": loaded.torch.cuda.get_device_name(0),
                "action_schema_version": ACTION_SCHEMA_VERSION,
                "chunk_size": CHUNK_SIZE,
                "execute_k": EXECUTE_K,
                "claims_task_success": False,
            },
        )

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in {"/predict", "/reset"}:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
            if length < 0 or length > MAX_REQUEST_BYTES:
                raise ValueError("request body exceeds limit")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("request must be a JSON object")
            if payload.get("protocol_version") != PROTOCOL_VERSION:
                raise ValueError("protocol version mismatch")
            loaded: LoadedPolicy = self.state["policy"]
            if self.path == "/reset":
                with loaded.lock:
                    loaded.reset()
                self._send_json(HTTPStatus.OK, {"protocol_version": PROTOCOL_VERSION, "reset": True})
                return
            sequence = int(payload.get("observation_sequence", -1))
            if sequence < 0:
                raise ValueError("observation_sequence must be non-negative")
            actions, inference_ms = loaded.predict(payload)
            self._send_json(
                HTTPStatus.OK,
                {
                    "protocol_version": PROTOCOL_VERSION,
                    "observation_sequence": sequence,
                    "action_schema_version": ACTION_SCHEMA_VERSION,
                    "actions": actions,
                    "execute_k": EXECUTE_K,
                    "server_inference_latency_ms": inference_ms,
                    "claims_task_success": False,
                },
            )
        except Exception as error:
            logging.getLogger("smolvla.remote").exception("request failed")
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"protocol_version": PROTOCOL_VERSION, "error": f"{type(error).__name__}: {error}"},
            )


def _load(args: argparse.Namespace) -> LoadedPolicy:
    import torch

    from training.scripts import run_smolvla_s3_open_loop as ol

    workdir = ol._prepare_lora_workdir(args.base_dir, args.lora_dir, args.vlm_dir)
    policy, preprocess, postprocess = ol._load_policy(
        workdir=workdir, lora_dir=args.lora_dir, device=torch.device("cuda")
    )
    loaded = LoadedPolicy(
        policy=policy,
        preprocess=preprocess,
        postprocess=postprocess,
        torch=torch,
        lock=threading.Lock(),
        base_dir=args.base_dir,
        lora_dir=args.lora_dir,
        vlm_dir=args.vlm_dir,
    )
    warmup = {
        "state": [0.0] * 7 + [0.45, 0.0, 0.35, 0.0, 0.0, 0.0, 1.0, 1.0],
        "image_encoding": "jpeg",
        "scene_jpeg_b64": base64.b64encode(
            _encode_warmup_jpeg()
        ).decode("ascii"),
        "wrist_jpeg_b64": base64.b64encode(
            _encode_warmup_jpeg()
        ).decode("ascii"),
        "task": DEFAULT_TASK,
    }
    loaded.predict(warmup)
    logging.info("warmup completed")
    return loaded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-dir", type=Path, required=True)
    parser.add_argument("--lora-dir", type=Path, required=True)
    parser.add_argument("--vlm-dir", type=Path, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18080)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    policy = _load(args)
    server = ThreadingHTTPServer((args.host, args.port), InferenceHandler)
    server.state = {"policy": policy}  # type: ignore[attr-defined]
    logging.info("ready on http://%s:%s", args.host, args.port)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
