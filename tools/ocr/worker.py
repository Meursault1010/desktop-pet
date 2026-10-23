"""Offline CPU OCR worker. One image on stdin; one JSON result on stdout."""
import base64
import json
import sys


def main():
    import cv2
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR

    request = json.loads(sys.stdin.buffer.read(16 * 1024 * 1024))
    raw = base64.b64decode(request["image"], validate=True)
    if len(raw) > 10 * 1024 * 1024:
        raise ValueError("Image exceeds 10 MB")
    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None or image.shape[0] * image.shape[1] > 24000000:
        raise ValueError("Invalid image or exceeds 24 megapixels")
    if image.ndim == 3 and image.shape[2] == 4:
        alpha = image[:, :, 3:4].astype(np.float32) / 255
        image = (image[:, :, :3] * alpha + 255 * (1 - alpha)).astype(np.uint8)
    engine = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1)
    result, _ = engine(image)
    lines = [{"text": str(row[1]), "confidence": float(row[2])} for row in (result or [])]
    text = "\n".join(row["text"] for row in lines)
    print(json.dumps({"text": text[:18000], "truncated": len(text) > 18000,
                      "lines": len(lines)}, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True), flush=True)
        sys.exit(1)
