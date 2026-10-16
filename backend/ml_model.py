```python
import os
from functools import lru_cache

import torch
import torch.nn.functional as F
from PIL import Image
from ultralytics import YOLO

# ============================================================
# MODEL SETUP
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
YOLO_MODEL_PATH = os.path.join(BASE_DIR, "..", "yolo11n.pt")
DINO_MODEL_NAME = "facebook/dinov2-small"

# Use CPU on Render's standard web instances
DEVICE = torch.device("cpu")

print("Loading YOLO model...")

yolo_model = YOLO(YOLO_MODEL_PATH)
yolo_model.to("cpu")

print("YOLO model ready")


# ============================================================
# LAZY DINOv2 LOADING
# ============================================================

image_processor = None
feature_model = None


def load_dino_model():
    """Load DINOv2 only when image similarity is needed."""
    global image_processor, feature_model

    if feature_model is None:
        from transformers import AutoImageProcessor, AutoModel

        print("Loading DINOv2 model...")

        image_processor = AutoImageProcessor.from_pretrained(
            DINO_MODEL_NAME
        )

        feature_model = AutoModel.from_pretrained(
            DINO_MODEL_NAME
        )

        feature_model.to(DEVICE)
        feature_model.eval()

        print("DINOv2 model ready")

    return image_processor, feature_model


# ============================================================
# YOLO OBJECT DETECTION
# ============================================================

def detect_objects(image_path):
    if not os.path.exists(image_path):
        return {
            "success": False,
            "message": "Image file not found",
            "detections": []
        }

    try:
        results = yolo_model.predict(
            source=image_path,
            device="cpu",
            verbose=False
        )

        detections = []

        for result in results:
            if result.boxes is None:
                continue

            for box in result.boxes:
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                class_name = yolo_model.names[class_id]

                x1, y1, x2, y2 = box.xyxy[0].tolist()

                detections.append({
                    "object": class_name,
                    "confidence": round(confidence, 3),
                    "box": [
                        round(x1),
                        round(y1),
                        round(x2),
                        round(y2)
                    ]
                })

        return {
            "success": True,
            "detections": detections
        }

    except Exception as error:
        return {
            "success": False,
            "message": str(error),
            "detections": []
        }


# ============================================================
# BEST DETECTION
# ============================================================

def get_best_detection(image_path):
    result = detect_objects(image_path)

    if not result["success"]:
        return None

    detections = result["detections"]

    if not detections:
        return None

    return max(
        detections,
        key=lambda item: item["confidence"]
    )


# ============================================================
# CROP DETECTED OBJECT
# ============================================================

def crop_detected_object(image_path):
    if not os.path.exists(image_path):
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    with Image.open(image_path) as source:
        image = source.convert("RGB")

    detection = get_best_detection(image_path)

    if detection is None:
        return image

    x1, y1, x2, y2 = detection["box"]
    width, height = image.size

    x1 = max(0, min(x1, width))
    y1 = max(0, min(y1, height))
    x2 = max(0, min(x2, width))
    y2 = max(0, min(y2, height))

    if x2 <= x1 or y2 <= y1:
        return image

    return image.crop((x1, y1, x2, y2))


# ============================================================
# DINOv2 FEATURE EXTRACTION
# ============================================================

def extract_features_from_image(image):
    processor, model = load_dino_model()

    inputs = processor(
        images=image.convert("RGB"),
        return_tensors="pt"
    )

    inputs = {
        key: value.to(DEVICE)
        for key, value in inputs.items()
    }

    with torch.inference_mode():
        outputs = model(**inputs)
        features = outputs.last_hidden_state[:, 0]

        features = F.normalize(
            features,
            p=2,
            dim=1
        )

    return features


def extract_features(image_path):
    if not os.path.exists(image_path):
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    object_image = crop_detected_object(image_path)

    return extract_features_from_image(object_image)


# ============================================================
# IMAGE SIMILARITY
# ============================================================

def compare_images(reference_path, candidate_path):
    reference_features = extract_features(reference_path)
    candidate_features = extract_features(candidate_path)

    similarity = F.cosine_similarity(
        reference_features,
        candidate_features,
        dim=1
    ).item()

    return round(similarity, 4)


# ============================================================
# COMPLETE MATCH RESULT
# ============================================================

def match_images(
    reference_path,
    candidate_path,
    threshold=0.70
):
    similarity = compare_images(
        reference_path,
        candidate_path
    )

    return {
        "success": True,
        "similarity": similarity,
        "threshold": threshold,
        "match": similarity >= threshold
    }


# ============================================================
# MODEL STATUS
# ============================================================

def model_status():
    return {
        "yolo": {
            "model": "YOLO11n",
            "status": "loaded"
        },
        "embedding": {
            "model": "DINOv2-small",
            "status": (
                "loaded"
                if feature_model is not None
                else "not_loaded"
            )
        }
    }
```