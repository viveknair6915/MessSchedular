from flask import Flask, render_template, jsonify 
from flask_cors import CORS
import os
import google.generativeai as genai
import json
from datetime import datetime
import requests  # For fetching remote image

# Configure the Gemini API
genai.configure(api_key="AIzaSyCGUeuP3xrtfNfNWy_oCVpWUvNBOnbzTss")

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash-8b",
    generation_config = genai.GenerationConfig(**generation_config)
)

# Flask App Initialization
app = Flask(__name__)
CORS(app)

# Meal Schedule Configuration
MEAL_SCHEDULE = {
    "Monday-Saturday": {
        "Breakfast": (7, 9),
        "Lunch": (12, 14),
        "Dinner": (19.5, 21.5),
    },
    "Sunday": {
        "Breakfast": (7, 9.5),
        "Lunch": (12, 14.5),
        "Dinner": (19.5, 21.5),
    }
}

# JSON File for Cached Meal Data
meal_data_file = "meal_data.json"


# Load Meal Data from File
def load_meal_data():
    if os.path.exists(meal_data_file):
        with open(meal_data_file, 'r') as file:
            return json.load(file)
    return None

# Save Meal Data to File
def save_meal_data(data):
    with open(meal_data_file, 'w') as file:
        json.dump(data, file, indent=4)

@app.route('/')
def index():
    return render_template('front.html') 

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

# Route: Get Menu
@app.route('/get_menu', methods=['GET'])
def get_menu():
    try:
        meal_data = load_meal_data()

        if not meal_data:
            # Fetch Image from Remote URL
            image_url = "https://github.com/life2harsh/MessSchedular/blob/main/messmenu.jpg?raw=true"

            response = requests.get(image_url)
            if response.status_code != 200:
                raise ValueError("Failed to download image from the provided URL.")

            image_data = response.content  # Get raw image data from the response

            # Send Image to Gemini Model
            response = model.start_chat(history=[]).send_message([
                {
                    "text": "Analyze the following image and extract all text from it in JSON format. "
                            "Use keys: 'Day', 'Breakfast', 'Lunch', 'Dinner'. If details are missing, use 'N/A'."
                },
                {
                    "mime_type": "image/jpeg",
                    "data": image_data
                }
            ])

            response_text = response.text.strip('`json').strip('`')
            try:
                parsed_response = json.loads(response_text)
            except json.JSONDecodeError:
                raise ValueError("AI response is not a valid JSON object.")

            if not isinstance(parsed_response, dict):
                raise ValueError("Parsed response is not a dictionary.")

            save_meal_data(parsed_response)
            meal_data = parsed_response

        # Determine the current day and time
        current_time = datetime.now()
        day = current_time.strftime('%A')
        hour = current_time.hour + current_time.minute / 60

        day_schedule = MEAL_SCHEDULE.get("Sunday") if day == "Sunday" else MEAL_SCHEDULE.get("Monday-Saturday")

        current_meal = None
        next_meal = None
        meal_keys = list(day_schedule.keys())

        for i, (meal, (start, end)) in enumerate(day_schedule.items()):
            if start <= hour <= end:
                current_meal = meal
                next_meal = meal_keys[(i + 1) % len(meal_keys)]
                break
            elif hour < start and not next_meal:
                next_meal = meal

        if not current_meal and not next_meal:
            next_meal = meal_keys[0]

        days = meal_data.get("Day", [])
        if day not in days:
            raise ValueError(f"No meal data found for {day}. Check AI response structure.")

        day_index = days.index(day)

        meal_details = {
            "Breakfast": meal_data.get("Breakfast", [])[day_index] if day_index < len(meal_data.get("Breakfast", [])) else "N/A",
            "Lunch": meal_data.get("Lunch", [])[day_index] if day_index < len(meal_data.get("Lunch", [])) else "N/A",
            "Dinner": meal_data.get("Dinner", [])[day_index] if day_index < len(meal_data.get("Dinner", [])) else "N/A"
        }

        meal_data_response = {
            "Day": day,
            "Current Meal": current_meal if current_meal else "No Current Meal",
            "Meal Details": meal_details.get(current_meal, "N/A") if current_meal else "N/A",
            "Next Meal": next_meal if next_meal else "No Next Meal",
            "Next Meal Details": meal_details.get(next_meal, "N/A") if next_meal else "N/A"
        }

        return jsonify(meal_data_response)

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 500
    except Exception as e:
        return jsonify({"error": "Internal Server Error"}), 500

# Run Flask App
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
