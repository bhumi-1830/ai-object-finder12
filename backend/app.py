from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client
import os
from werkzeug.utils import secure_filename

from ml_model import (
    detect_objects,
    compare_images,
    model_status
)


# =========================
# LOAD ENVIRONMENT VARIABLES
# =========================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


# =========================
# SUPABASE CONNECTION
# =========================

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL or SUPABASE_KEY is missing from .env"
    )

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# =========================
# FLASK APP
# =========================

app = Flask(__name__)
CORS(app)


# =========================
# UPLOAD CONFIGURATION
# =========================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "uploads"
)

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


# =========================
# FILE VALIDATION
# =========================

def allowed_file(filename):

    return (
        "." in filename
        and
        filename.rsplit(
            ".",
            1
        )[1].lower()
        in ALLOWED_EXTENSIONS
    )


# =========================
# HOME / SERVER STATUS
# =========================

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "status": "online",
        "message": "AI Object Finder ML Server is running",
        "model": model_status(),
        "supabase": "connected"
    })


# =========================
# UPLOAD REFERENCE IMAGE
# =========================

@app.route(
    "/upload-reference",
    methods=["POST"]
)
def upload_reference():

    if "image" not in request.files:

        return jsonify({
            "success": False,
            "message": "No image received"
        }), 400

    image = request.files["image"]

    if image.filename == "":

        return jsonify({
            "success": False,
            "message": "No image selected"
        }), 400

    if not allowed_file(image.filename):

        return jsonify({
            "success": False,
            "message": "Unsupported image format"
        }), 400

    filename = secure_filename(
        image.filename
    )

    # Read image data
    image_data = image.read()

    # Supabase Storage path
    storage_path = f"references/{filename}"

    try:

        supabase.storage \
            .from_("object-images") \
            .upload(
                storage_path,
                image_data,
                {
                    "content-type": image.content_type,
                    "upsert": "true"
                }
            )

    except Exception as error:

        return jsonify({
            "success": False,
            "message": "Failed to upload image to Supabase",
            "error": str(error)
        }), 500

    # Also save locally.
    # This is useful because the ML model
    # can use the local file immediately.
    local_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    with open(local_path, "wb") as file:

        file.write(image_data)

    return jsonify({

        "success": True,

        "message": (
            "Reference image uploaded "
            "to Supabase successfully"
        ),

        "filename": filename,

        "storage_path": storage_path

    })


# =========================
# YOLO OBJECT DETECTION
# =========================

@app.route(
    "/detect",
    methods=["POST"]
)
def detect():

    if "image" not in request.files:

        return jsonify({
            "success": False,
            "message": "No image received"
        }), 400

    image = request.files["image"]

    if image.filename == "":

        return jsonify({
            "success": False,
            "message": "No image selected"
        }), 400

    if not allowed_file(image.filename):

        return jsonify({
            "success": False,
            "message": "Unsupported image format"
        }), 400

    filename = secure_filename(
        image.filename
    )

    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        "detect_" + filename
    )

    image.save(filepath)

    result = detect_objects(
        filepath
    )

    return jsonify(result)


# =========================
# REFERENCE vs CANDIDATE
# IMAGE MATCHING
# =========================

@app.route(
    "/match",
    methods=["POST"]
)
def match():

    # Check reference image
    if "reference" not in request.files:

        return jsonify({
            "success": False,
            "message": "Reference image is required"
        }), 400

    # Check candidate image
    if "candidate" not in request.files:

        return jsonify({
            "success": False,
            "message": "Candidate image is required"
        }), 400

    reference = request.files["reference"]

    candidate = request.files["candidate"]

    # Check filenames
    if (
        reference.filename == ""
        or
        candidate.filename == ""
    ):

        return jsonify({
            "success": False,
            "message": "Both images are required"
        }), 400

    # Check file types
    if not allowed_file(
        reference.filename
    ):

        return jsonify({
            "success": False,
            "message": (
                "Unsupported reference "
                "image format"
            )
        }), 400

    if not allowed_file(
        candidate.filename
    ):

        return jsonify({
            "success": False,
            "message": (
                "Unsupported candidate "
                "image format"
            )
        }), 400

    # Secure filenames
    reference_filename = secure_filename(
        reference.filename
    )

    candidate_filename = secure_filename(
        candidate.filename
    )

    # Create paths
    reference_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        "reference_" + reference_filename
    )

    candidate_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        "candidate_" + candidate_filename
    )

    # Save images
    reference.save(
        reference_path
    )

    candidate.save(
        candidate_path
    )

    # Calculate DINOv2 similarity
    similarity = compare_images(
        reference_path,
        candidate_path
    )

    # Initial threshold.
    # We will calibrate this using
    # real project images later.
    threshold = 0.70

    is_match = (
        similarity >= threshold
    )

    return jsonify({

        "success": True,

        "similarity": similarity,

        "threshold": threshold,

        "match": is_match

    })


# =========================
# START SERVER
# =========================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )