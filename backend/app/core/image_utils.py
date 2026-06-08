"""이미지 처리 유틸리티 (Pillow).

Rekognition DetectFaces가 돌려주는 정규화된 BoundingBox로 얼굴 영역을 잘라낸다.
SearchFacesByImage는 이미지의 '가장 큰 얼굴'만 보므로, 멀티 얼굴 스틸은
얼굴별로 crop한 뒤 개별 검색한다(DESIGN §4-B).
"""

import io

from PIL import Image


def crop_face(image_bytes: bytes, bounding_box: dict, margin: float = 0.0) -> bytes:
    """정규화 BoundingBox(Left/Top/Width/Height, 0~1)로 얼굴을 잘라 JPEG 바이트로 반환한다.

    margin은 박스 크기 대비 추가 여백 비율(예: 0.1 = 10%)이며, 이미지 경계로 클램프된다.
    """
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != "RGB":
        img = img.convert("RGB")
    width, height = img.size

    left = bounding_box["Left"] * width
    top = bounding_box["Top"] * height
    box_w = bounding_box["Width"] * width
    box_h = bounding_box["Height"] * height

    pad_x = box_w * margin
    pad_y = box_h * margin

    x1 = max(0, int(left - pad_x))
    y1 = max(0, int(top - pad_y))
    x2 = min(width, int(left + box_w + pad_x))
    y2 = min(height, int(top + box_h + pad_y))

    cropped = img.crop((x1, y1, x2, y2))

    out = io.BytesIO()
    cropped.save(out, format="JPEG")
    return out.getvalue()
