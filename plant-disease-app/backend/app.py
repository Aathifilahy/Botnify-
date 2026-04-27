import os
import io
import base64
from datetime import datetime

import cloudinary
import cloudinary.uploader
from flask import Flask, request, jsonify
from flask_cors import CORS

allowed_origins = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000').split(',')
CORS(app, origins=allowed_origins)

from dotenv import load_dotenv
import numpy as np
from PIL import Image

# Optional TensorFlow import
try:
    import tensorflow as tf
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    print("⚠️ TensorFlow not available - running in mock mode")

from pymongo import MongoClient
from bson.objectid import ObjectId

load_dotenv()

app = Flask(__name__)
CORS(app, origins=os.getenv("ALLOWED_ORIGINS", "*").split(","))

# ---------- Cloudinary config ----------
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

# ---------- MongoDB ----------
mongo_uri = os.getenv("MONGODB_URI")
mongo_db_name = os.getenv("MONGODB_DB_NAME", "plantscan")
mongo_client = MongoClient(mongo_uri)
db = mongo_client[mongo_db_name]
scans_collection = db["scans"]

# ---------- Load model (with mock fallback) ----------
MODEL_PATH = "model/plant_disease_model.h5"
model = None
use_mock = False

if not TENSORFLOW_AVAILABLE:
    use_mock = True
    print("⚠️ TensorFlow not installed – using mock predictions")
else:
    try:
        if os.path.exists(MODEL_PATH):
            model = tf.keras.models.load_model(MODEL_PATH)
            print("✅ Model loaded successfully")
        else:
            use_mock = True
            print("⚠️ Model not found – using mock predictions")
    except Exception as e:
        use_mock = True
        print(f"❌ Model load error: {e} – using mock predictions")

# Class names (PlantVillage 38 classes – shortened for brevity; full list in train_model.py)
CLASS_NAMES = [
    "Apple___Apple_scab", "Apple___Black_rot", "Apple___Cedar_apple_rust", "Apple___healthy",
    "Blueberry___healthy", "Cherry___Powdery_mildew", "Cherry___healthy",
    "Corn___Cercospora_leaf_spot", "Corn___Common_rust", "Corn___Northern_Leaf_Blight", "Corn___healthy",
    "Grape___Black_rot", "Grape___Esca", "Grape___Leaf_blight", "Grape___healthy",
    "Orange___Haunglongbing", "Peach___Bacterial_spot", "Peach___healthy",
    "Pepper_bell___Bacterial_spot", "Pepper_bell___healthy",
    "Potato___Early_blight", "Potato___Late_blight", "Potato___healthy",
    "Raspberry___healthy", "Soybean___healthy", "Squash___Powdery_mildew",
    "Strawberry___Leaf_scorch", "Strawberry___healthy",
    "Tomato___Bacterial_spot", "Tomato___Early_blight", "Tomato___Late_blight",
    "Tomato___Leaf_Mold", "Tomato___Septoria_leaf_spot", "Tomato___Spider_mites",
    "Tomato___Target_Spot", "Tomato___Tomato_Yellow_Leaf_Curl_Virus", "Tomato___Tomato_mosaic_virus", "Tomato___healthy"
]

TREATMENT_MAP = {
    "Apple_scab": "Apply fungicide (myclobutanil) in early spring. Remove fallen leaves.",
    "Early_blight": "Use chlorothalonil or copper fungicide. Water at base.",
    "Late_blight": "Remove infected leaves. Apply copper-based fungicide.",
    "healthy": "No treatment needed. Maintain proper watering and sunlight.",
    # Add more as needed – fallback generic treatment below
}

def get_treatment(disease_name):
    for key, treatment in TREATMENT_MAP.items():
        if key.lower() in disease_name.lower():
            return treatment
    return "Remove affected parts and apply broad-spectrum fungicide. Consult local extension."

def preprocess_image(image_bytes, target_size=(224, 224)):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = img.resize(target_size)
    img_array = np.array(img) / 255.0
    return np.expand_dims(img_array, axis=0)

def predict_disease(image_bytes):
    if use_mock or model is None:
        # Mock prediction – random top result
        import random
        idx = random.randint(0, len(CLASS_NAMES)-1)
        class_name = CLASS_NAMES[idx]
        confidence = round(random.uniform(0.65, 0.95), 2)
        plant = class_name.split("___")[0] if "___" in class_name else "Plant"
        disease_display = class_name.split("___")[1] if "___" in class_name else class_name
        return {
            "plant": plant,
            "disease": disease_display,
            "confidence": confidence,
            "top_predictions": [{"class": cn, "confidence": round(random.uniform(0.1,0.9),2)} for cn in CLASS_NAMES[:5]]
        }
    else:
        processed = preprocess_image(image_bytes)
        predictions = model.predict(processed)[0]
        top_idx = np.argmax(predictions)
        confidence = float(predictions[top_idx])
        class_name = CLASS_NAMES[top_idx]
        plant = class_name.split("___")[0] if "___" in class_name else "Plant"
        disease_display = class_name.split("___")[1] if "___" in class_name else class_name
        # Get top 5
        top5_indices = np.argsort(predictions)[-5:][::-1]
        top5 = [{"class": CLASS_NAMES[i], "confidence": float(predictions[i])} for i in top5_indices]
        return {
            "plant": plant,
            "disease": disease_display,
            "confidence": confidence,
            "top_predictions": top5
        }

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "mock_mode": use_mock,
        "cloudinary": "configured" if os.getenv("CLOUDINARY_CLOUD_NAME") else "missing",
        "mongodb": "connected" if mongo_client else "error"
    })

@app.route("/predict", methods=["POST"])
def predict():
    if "image" not in request.files:
        return jsonify({"error": "No image provided"}), 400
    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400
    try:
        image_bytes = file.read()
        # 1. Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            io.BytesIO(image_bytes),
            folder="plant_disease_scans",
            transformation={"width": 800, "height": 800, "crop": "limit", "quality": "auto"}
        )
        image_url = upload_result["secure_url"]
        public_id = upload_result["public_id"]

        # 2. Run ML prediction
        pred_result = predict_disease(image_bytes)

        # 3. Build treatment
        treatment = get_treatment(pred_result["disease"])

        # 4. Save to MongoDB
        scan_doc = {
            "image_url": image_url,
            "cloudinary_public_id": public_id,
            "plant": pred_result["plant"],
            "disease": pred_result["disease"],
            "confidence": pred_result["confidence"],
            "treatment": treatment,
            "top_predictions": pred_result["top_predictions"],
            "created_at": datetime.utcnow()
        }
        inserted = scans_collection.insert_one(scan_doc)
        scan_doc["_id"] = str(inserted.inserted_id)
        del scan_doc["cloudinary_public_id"]  # hide from client

        return jsonify({
            "success": True,
            "scan_id": str(inserted.inserted_id),
            "image_url": image_url,
            "plant": pred_result["plant"],
            "disease": pred_result["disease"],
            "confidence": pred_result["confidence"],
            "treatment": treatment,
            "top_predictions": pred_result["top_predictions"],
            "mock_mode": use_mock
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/history", methods=["GET"])
def get_history():
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 10))
    skip = (page - 1) * limit
    total = scans_collection.count_documents({})
    scans = list(scans_collection.find({}, {"cloudinary_public_id": 0})
                 .sort("created_at", -1).skip(skip).limit(limit))
    for s in scans:
        s["_id"] = str(s["_id"])
        s["created_at"] = s["created_at"].isoformat()
    return jsonify({
        "scans": scans,
        "page": page,
        "limit": limit,
        "total": total,
        "pages": (total + limit - 1) // limit
    })

@app.route("/history/<scan_id>", methods=["DELETE"])
def delete_scan(scan_id):
    try:
        # Find document to get cloudinary id
        doc = scans_collection.find_one({"_id": ObjectId(scan_id)})
        if not doc:
            return jsonify({"error": "Scan not found"}), 404
        public_id = doc.get("cloudinary_public_id")
        if public_id:
            cloudinary.uploader.destroy(public_id)
        scans_collection.delete_one({"_id": ObjectId(scan_id)})
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)