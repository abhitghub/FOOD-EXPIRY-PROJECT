from flask import Flask, request, jsonify
import os
import sqlite3
from datetime import datetime, timedelta
import pytesseract
from PIL import Image
import requests

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
DB_FILE = "food_expiry.db"
API_KEY = "b8589f8fd46f43ef8203cc211929074f"  # Replace with your API key

# Configure Tesseract (Modify path if needed)
pytesseract.pytesseract.tesseract_cmd = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

# Initialize Database
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS food_items (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT,
                            expiry_date TEXT
                        )''')
        conn.commit()

init_db()

# Debugging Route
@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "API is running!"})

# Extract text from image
def extract_text_from_image(image_path):
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception as e:
        print(f"❌ Error extracting text: {str(e)}")
        return None

# Add Food Item with OCR & Store in Database
@app.route("/food", methods=["POST"])
def add_food():
    print("🚀 Request received for /food")  # Debugging log
    try:
        if "image" not in request.files:
            return jsonify({"error": "No image provided"}), 400
        
        image = request.files["image"]
        if image.filename == "":
            return jsonify({"error": "No file selected"}), 400
        
        image_path = os.path.join(UPLOAD_FOLDER, image.filename)
        image.save(image_path)
        print(f"✅ Image saved at {image_path}")  # Debugging log
        
        extracted_text = extract_text_from_image(image_path)
        if not extracted_text:
            return jsonify({"error": "Could not extract food details from image"}), 400
        
        print(f"📄 Extracted text: {extracted_text}")  # Debugging log
        
        lines = extracted_text.split("\n")
        name, expiry_date = None, None
        
        for line in lines:
            if "Food Name:" in line:
                name = line.split(":")[-1].strip()
            elif "Expiry Date:" in line:
                expiry_date = line.split(":")[-1].strip()
        
        if not name or not expiry_date:
            return jsonify({"error": "Could not extract valid food details"}), 400
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO food_items (name, expiry_date) VALUES (?, ?)", (name, expiry_date))
            conn.commit()
        
        return jsonify({"message": "Food item added successfully", "name": name, "expiry_date": expiry_date})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Get All Food Items
@app.route("/food", methods=["GET"])
def get_items():
    print("📥 Fetching all food items")  # Debugging log
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM food_items")
            items = [{"id": row[0], "name": row[1], "expiry_date": row[2]} for row in cursor.fetchall()]
        return jsonify(items)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Get Expiring Soon Items
@app.route("/food/expiring", methods=["GET"])
def expiring_soon():
    print("⚠️ Checking expiring soon items")  # Debugging log
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        threshold_date = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
        
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, expiry_date FROM food_items WHERE expiry_date <= ?", (threshold_date,))
            items = []
            for row in cursor.fetchall():
                status = "Safe to eat" if row[1] >= today else "Expired"
                items.append({"name": row[0], "expiry_date": row[1], "status": status})
        
        return jsonify({"expiring_soon": items})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Get Recipe Suggestions
@app.route("/recipes", methods=["POST"])
def get_recipes():
    print("🍽️ Fetching recipe suggestions")  # Debugging log
    try:
        data = request.json
        ingredients = ",".join(data.get("ingredients", []))
        if not ingredients:
            return jsonify({"error": "No ingredients provided"}), 400
        
        url = f"https://api.spoonacular.com/recipes/findByIngredients?ingredients={ingredients}&apiKey={API_KEY}"
        response = requests.get(url)
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({"error": "Failed to fetch recipes"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Run Flask App
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
