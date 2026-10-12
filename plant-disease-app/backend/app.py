import os
import io
import base64
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

import cloudinary
import cloudinary.uploader
from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
from PIL import Image
from pymongo import MongoClient
from bson.objectid import ObjectId

# Optional TensorFlow import
try:
    import tensorflow as tf
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    print("⚠️ TensorFlow not available - running in mock mode")

# ---------- Helper: get session ID ----------
def get_session_id():
    """Extract session ID from request headers (X-Session-Id) or query param."""
    session_id = request.headers.get('X-Session-Id')
    if not session_id:
        session_id = request.args.get('sessionId')
    if not session_id:
        return None
    return session_id

# ---------- Create Flask app ----------
app = Flask(__name__)

# ---------- CORS configuration ----------
allowed_origins = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000').split(',')
CORS(app, origins=allowed_origins)

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
MODEL_PATH = "model/bug_bite_model.h5"
model = None
use_mock = False

if not TENSORFLOW_AVAILABLE:
    use_mock = True
    print("⚠️ TensorFlow not installed – using mock predictions")
else:
    try:
        if os.path.exists(MODEL_PATH):
            model = tf.keras.models.load_model(MODEL_PATH)
            print("✅ Bug bite model loaded successfully")
        else:
            use_mock = True
            print("⚠️ Model not found – using mock predictions")
    except Exception as e:
        use_mock = True
        print(f"❌ Model load error: {e} – using mock predictions")

# ---------- Damage classes (insect feeding guilds) ----------
CLASS_NAMES = [
    "healthy",
    "notch_damage",
    "shothole_damage",
    "skeletonization",
    "leaf_mining",
    "window_paning",
    "defoliation",
    "leaf_curl_damage",
    "stem_damage",
]

# ---------- Solutions knowledge base ----------
SOLUTIONS = {
    "healthy": {
        "display_name": "Healthy Leaf",
        "severity": "none",
        "likely_pests": [],
        "organic": "No action needed. Continue regular monitoring.",
        "chemical": "None required.",
        "cultural": "Maintain healthy soil, proper watering, and inspect weekly.",
        "urgency": "None"
    },
    "notch_damage": {
        "display_name": "Notch Damage (Marginal Bites)",
        "severity": "mild_to_moderate",
        "likely_pests": ["Root weevil", "Leaf-cutter bee", "Vine weevil", "Fuller's rose beetle"],
        "organic": "Apply beneficial nematodes (Steinernema carpocapsae) to soil for weevil larvae. Spray neem oil on foliage every 7–10 days.",
        "chemical": "For severe weevil infestation, apply imidacloprid soil drench. Apply only after flowering to protect pollinators.",
        "cultural": "Remove crop debris. Plant garlic, marigold, or chrysanthemum as repellent companion plants. Use row covers during peak activity.",
        "urgency": "Address within 7–10 days to prevent larvae damage to roots."
    },
    "shothole_damage": {
        "display_name": "Shot Hole Damage (Small Scattered Holes)",
        "severity": "moderate",
        "likely_pests": ["Flea beetle", "Leaf beetle", "Blight beetle"],
        "organic": "Apply diatomaceous earth around plants. Use neem oil or insecticidal soap spray. Introduce beneficial nematodes.",
        "chemical": "Apply carbaryl or spinosad spray for severe infestations. Rotate chemicals to avoid resistance.",
        "cultural": "Plant trap crops like radish or mustard nearby. Use yellow sticky traps. Remove weeds that host beetles.",
        "urgency": "Act within 5–7 days – flea beetles can defoliate young plants fast."
    },
    "skeletonization": {
        "display_name": "Skeletonization (Only Veins Remain)",
        "severity": "severe",
        "likely_pests": ["Caterpillars", "Sawfly larvae", "Beetle larvae", "Leaf-mining moths"],
        "organic": "Apply Bacillus thuringiensis (Bt) – highly effective against caterpillars. Handpick visible larvae. Introduce parasitic wasps (Trichogramma).",
        "chemical": "Spray spinosad or chlorantraniliprole. Apply in the evening when caterpillars are active.",
        "cultural": "Encourage birds and predatory insects. Rotate crops. Remove plant debris after harvest.",
        "urgency": "Immediate action required – can strip entire plants within days."
    },
    "leaf_mining": {
        "display_name": "Leaf Mining (Serpentine/Blotch Tunnels)",
        "severity": "moderate",
        "likely_pests": ["Leaf miner fly", "Citrus leafminer", "Moth larvae", "Beetle miners"],
        "organic": "Remove and destroy mined leaves. Use yellow sticky traps for adult flies. Apply neem oil or spinosad spray every 7 days.",
        "chemical": "Apply abamectin or cyromazine for severe cases. Systemic insecticides are most effective.",
        "cultural": "Introduce parasitic wasps (Diglyphus isaea). Avoid excessive nitrogen fertiliser which attracts miners.",
        "urgency": "Act within 10–14 days – miners reproduce quickly in warm weather."
    },
    "window_paning": {
        "display_name": "Window Paning (Transparent Tissue Left)",
        "severity": "mild",
        "likely_pests": ["Young caterpillars", "Small beetles", "Leaf-rollers"],
        "organic": "Apply neem oil spray. Introduce ladybugs and lacewings. Handpick small caterpillars.",
        "chemical": "Bt spray for caterpillars. Insecticidal soap for beetles.",
        "cultural": "Regular inspection. Encourage natural predators. Avoid overhead watering.",
        "urgency": "Monitor closely – can progress to full defoliation if untreated."
    },
    "defoliation": {
        "display_name": "Defoliation (Entire Leaf Consumed)",
        "severity": "severe",
        "likely_pests": ["Grasshoppers", "Armyworms", "Locusts", "Large caterpillars"],
        "organic": "Apply Nosema locustae bait for grasshoppers. Bt for armyworms. Use row covers. Plant border trap crops.",
        "chemical": "Apply cypermethrin or lambda-cyhalothrin for severe infestations. Treat in early morning.",
        "cultural": "Tillage to expose soil-borne larvae. Encourage birds. Remove tall grass near crop.",
        "urgency": "Emergency – immediate action within 24–48 hours."
    },
    "leaf_curl_damage": {
        "display_name": "Leaf Curl / Distortion",
        "severity": "moderate",
        "likely_pests": ["Aphids", "Thrips", "Whiteflies", "Leafhoppers"],
        "organic": "Spray neem oil or insecticidal soap. Introduce ladybugs and lacewings. Use yellow sticky traps.",
        "chemical": "Apply imidacloprid or thiamethoxam for severe sucking-pest infestations.",
        "cultural": "Remove infected leaves. Avoid overcrowding. Use reflective mulch.",
        "urgency": "Act within 7 days – sucking pests transmit viruses."
    },
    "stem_damage": {
        "display_name": "Stem Damage / Borer Holes",
        "severity": "severe",
        "likely_pests": ["Stem borer", "Cane borer", "Weevil larvae", "Cutworms"],
        "organic": "Insert beneficial nematodes into borer holes. Apply Bt. Cut and destroy affected stems.",
        "chemical": "Apply carbaryl or chlorpyrifos as a stem spray. Inject insecticide into borer holes.",
        "cultural": "Destroy crop residues. Rotate with non-host crops. Use pheromone traps for adults.",
        "urgency": "Immediate – borers can kill the plant from inside."
    }
}

def get_solution(damage_class):
    return SOLUTIONS.get(damage_class, SOLUTIONS["healthy"])

# ---------- Image preprocess ----------
def preprocess_image(image_bytes, target_size=(224, 224)):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = img.resize(target_size)
    img_array = np.array(img) / 255.0
    return np.expand_dims(img_array, axis=0)

# ---------- Prediction ----------
def predict_damage(image_bytes):
    if use_mock or model is None:
        import random
        idx = random.randint(0, len(CLASS_NAMES) - 1)
        class_name = CLASS_NAMES[idx]
        confidence = round(random.uniform(0.65, 0.95), 2)
        top5 = [
            {"class": cn, "confidence": round(random.uniform(0.1, 0.9), 2)}
            for cn in random.sample(CLASS_NAMES, min(5, len(CLASS_NAMES)))
        ]
        return {
            "damage_class": class_name,
            "confidence": confidence,
            "top_predictions": top5
        }
    else:
        processed = preprocess_image(image_bytes)
        predictions = model.predict(processed)[0]
        top_idx = int(np.argmax(predictions))
        confidence = float(predictions[top_idx])
        class_name = CLASS_NAMES[top_idx]
        top5_indices = np.argsort(predictions)[-5:][::-1]
        top5 = [{"class": CLASS_NAMES[i], "confidence": float(predictions[i])} for i in top5_indices]
        return {
            "damage_class": class_name,
            "confidence": confidence,
            "top_predictions": top5
        }

# ---------- Routes ----------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "mock_mode": use_mock,
        "model": "bug_bite_classifier",
        "cloudinary": "configured" if os.getenv("CLOUDINARY_CLOUD_NAME") else "missing",
        "mongodb": "connected" if mongo_client else "error"
    })

@app.route("/predict", methods=["POST"])
def predict():
    session_id = get_session_id()
    if not session_id:
        return jsonify({"error": "Missing session ID. Please refresh the page."}), 400

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
            folder="bug_bite_scans",
            transformation={"width": 800, "height": 800, "crop": "limit", "quality": "auto"}
        )
        image_url = upload_result["secure_url"]
        public_id = upload_result["public_id"]

        # 2. Predict damage type
        pred = predict_damage(image_bytes)

        # 3. Get solution
        solution = get_solution(pred["damage_class"])

        # 4. Save to MongoDB
        scan_doc = {
            "image_url": image_url,
            "cloudinary_public_id": public_id,
            "damage_class": pred["damage_class"],
            "damage_display": solution["display_name"],
            "severity": solution["severity"],
            "likely_pests": solution["likely_pests"],
            "confidence": pred["confidence"],
            "top_predictions": pred["top_predictions"],
            "treatment": {
                "organic": solution["organic"],
                "chemical": solution["chemical"],
                "cultural": solution["cultural"]
            },
            "urgency": solution["urgency"],
            "session_id": session_id,
            "created_at": datetime.utcnow()
        }
        inserted = scans_collection.insert_one(scan_doc)

        return jsonify({
            "success": True,
            "scan_id": str(inserted.inserted_id),
            "image_url": image_url,
            "damage_class": pred["damage_class"],
            "damage_display": solution["display_name"],
            "severity": solution["severity"],
            "likely_pests": solution["likely_pests"],
            "confidence": pred["confidence"],
            "top_predictions": pred["top_predictions"],
            "treatment": {
                "organic": solution["organic"],
                "chemical": solution["chemical"],
                "cultural": solution["cultural"]
            },
            "urgency": solution["urgency"],
            "mock_mode": use_mock
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/history", methods=["GET"])
def get_history():
    session_id = get_session_id()
    if not session_id:
        return jsonify({"error": "Missing session ID"}), 400

    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 10))
    skip = (page - 1) * limit

    filter_query = {"session_id": session_id}
    total = scans_collection.count_documents(filter_query)
    scans = list(scans_collection.find(filter_query, {"cloudinary_public_id": 0})
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
    session_id = get_session_id()
    if not session_id:
        return jsonify({"error": "Missing session ID"}), 400

    try:
        doc = scans_collection.find_one({"_id": ObjectId(scan_id), "session_id": session_id})
        if not doc:
            return jsonify({"error": "Scan not found or not owned by this session"}), 404
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