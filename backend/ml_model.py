from ultralytics import YOLO
from transformers import AutoImageProcessor, AutoModel
from PIL import Image
import torch
import torch.nn.functional as F
import os


# ============================================================
# MODEL SETUP
# ============================================================

YOLO_MODEL_PATH = "yolo11n.pt"
DINO_MODEL_NAME = "facebook/dinov2-small"

print("Loading YOLO...")
yolo_model = YOLO(YOLO_MODEL_PATH)

print("Loading DINOv2...")
image_processor = AutoImageProcessor.from_pretrained(DINO_MODEL_NAME)
feature_model = AutoModel.from_pretrained(DINO_MODEL_NAME)
feature_model.eval()

print("YOLO + DINOv2 READY")


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

    results = yolo_model(image_path)

    detections = []

    for result in results:

        for box in result.boxes:

            class_id = int(box.cls[0])
            confidence = float(box.conf[0])

            class_name = yolo_model.names[class_id]

            # Bounding box coordinates
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


# ============================================================
# GET BEST OBJECT DETECTION
# ============================================================

def get_best_detection(image_path):

    result = detect_objects(image_path)

    if not result["success"]:
        return None

    detections = result["detections"]

    if not detections:
        return None

    # Select highest-confidence detection
    best_detection = max(
        detections,
        key=lambda item: item["confidence"]
    )

    return best_detection


# ============================================================
# CROP DETECTED OBJECT
# ============================================================

def crop_detected_object(image_path):

    if not os.path.exists(image_path):
        raise FileNotFoundError(
            f"Image not found: {image_path}"
        )

    detection = get_best_detection(image_path)

    image = Image.open(image_path).convert("RGB")

    if detection is None:
        # If YOLO detects nothing,
        # use the complete image as fallback.
        return image

    x1, y1, x2, y2 = detection["box"]

    width, height = image.size

    # Keep coordinates inside image boundaries
    x1 = max(0, min(x1, width))
    y1 = max(0, min(y1, height))
    x2 = max(0, min(x2, width))
    y2 = max(0, min(y2, height))

    # Safety check
    if x2 <= x1 or y2 <= y1:
        return image

    cropped = image.crop(
        (x1, y1, x2, y2)
    )

    return cropped


# ============================================================
# DINOv2 FEATURE EXTRACTION
# ============================================================

def extract_features_from_image(image):

    inputs = image_processor(
        images=image,
        return_tensors="pt"
    )

    with torch.no_grad():

        outputs = feature_model(
            **inputs
        )

    # CLS token
    features = outputs.last_hidden_state[:, 0]

    # Normalize embedding
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

    # First detect the object
    # Then crop it
    object_image = crop_detected_object(
        image_path
    )

    # Extract DINOv2 features
    features = extract_features_from_image(
        object_image
    )

    return features


# ============================================================
# IMAGE SIMILARITY
# ============================================================

def compare_images(
    reference_path,
    candidate_path
):

    reference_features = extract_features(
        reference_path
    )

    candidate_features = extract_features(
        candidate_path
    )

    similarity = F.cosine_similarity(
        reference_features,
        candidate_features
    ).item()

    return round(
        similarity,
        4
    )


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

    is_match = similarity >= threshold

    return {
        "success": True,
        "similarity": similarity,
        "threshold": threshold,
        "match": is_match
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
            "status": "loaded"
        }
    }