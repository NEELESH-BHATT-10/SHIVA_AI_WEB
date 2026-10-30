import os
import re
import html
import requests

from flask import Flask, request, jsonify, Response

app = Flask(**name**)

# -----------------------------

# OPENROUTER AI CONFIGURATION

# -----------------------------

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openrouter/free"

# -----------------------------

# CREATOR IDENTIFICATION

# -----------------------------

def is_creator_question(message):
patterns = [
r"\bwho\s+(made|created|built|developed|owns)\s+(you|this|shiva)\b",
r"\bwho\s+is\s+(your|the)\s+(creator|owner|developer|founder|maker)\b",
r"\bwho\s+is\s+behind\s+you\b",
r"\byour\s+creator\b",
r"\byour\s+owner\b",
r"\byour\s+developer\b",
r"\bwho\s+made\s+shiva\s*ai\b"
]

```
return any(re.search(pattern, message, re.IGNORECASE) for pattern in patterns)
```

# -----------------------------

# HOME PAGE

# -----------------------------

@app.route("/")
def home():
try:
with open("index.html", "r", encoding="utf-8") as file:
return file.read()
except FileNotFoundError:
return "index.html was not found. Please add it to your project.", 404

# -----------------------------

# HEALTH CHECK

# -----------------------------

@app.route("/health")
def health():
return jsonify({
"status": "online",
"app": "SHIVA AI"
})

# -----------------------------

# AI CHAT API

# -----------------------------

@app.route("/api/chat", methods=["POST"])
def chat():
try:
data = request.get_json(silent=True) or {}
message = str(data.get("message", "")).strip()

```
    if not message:
        return jsonify({"reply": "Please enter a message."}), 400

    # Identify the creator
    if is_creator_question(message):
        return jsonify({"reply": "Neelesh Bhatt."})

    # Check API key
    if not OPENROUTER_API_KEY:
        return jsonify({
            "reply": "AI service is not configured yet. Please check the OPENROUTER_API_KEY environment variable on Render."
        }), 503

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are SHIVA AI, a helpful and respectful AI assistant "
                    "created by Neelesh Bhatt. Give clear, useful answers. "
                    "Do not claim to have abilities you do not possess."
                )
            },
            {
                "role": "user",
                "content": message
            }
        ]
    }

    response = requests.post(
        OPENROUTER_URL,
        headers=headers,
        json=payload,
        timeout=60
    )

    if response.status_code != 200:
        return jsonify({
            "reply": "The AI service is temporarily unavailable. Please try again later."
        }), 502

    result = response.json()
    reply = result["choices"][0]["message"]["content"]

    # Some models may return content as a list
    if isinstance(reply, list):
        reply = " ".join(
            item.get("text", "")
            for item in reply
            if isinstance(item, dict)
        )

    if not reply:
        reply = "I couldn't generate a response. Please try again."

    return jsonify({"reply": str(reply)})

except requests.exceptions.Timeout:
    return jsonify({
        "reply": "The AI took too long to respond. Please try again."
    }), 504

except requests.exceptions.RequestException:
    return jsonify({
        "reply": "Could not connect to the AI service. Please try again later."
    }), 502

except (KeyError, IndexError, TypeError, ValueError):
    return jsonify({
        "reply": "The AI returned an unexpected response. Please try again."
    }), 502

except Exception:
    app.logger.exception("Unexpected error in chat route")
    return jsonify({
        "reply": "Something went wrong. Please try again."
    }), 500
```

# -----------------------------

# BHARAT EXPLORER MAP HELPERS

# -----------------------------

INDIA_GEOJSON_URL = (
"https://raw.githubusercontent.com/geohacker/india/master/state/india_state.geojson"
)

def get_feature_name(feature, number):
properties = feature.get("properties", {})

```
possible_names = [
    "name",
    "NAME_1",
    "NAME",
    "st_nm",
    "state",
    "State"
]

for key in possible_names:
    value = properties.get(key)
    if value:
        return str(value)

return f"Region {number}"
```

def collect_rings(geometry):
"""Return polygon rings from Polygon or MultiPolygon geometry."""

```
if not geometry:
    return []

geometry_type = geometry.get("type")
coordinates = geometry.get("coordinates", [])

if geometry_type == "Polygon":
    return coordinates

if geometry_type == "MultiPolygon":
    rings = []
    for polygon in coordinates:
        rings.extend(polygon)
    return rings

return []
```

def make_map_path(ring, min_lon, max_lon, min_lat, max_lat):
"""Convert geographic coordinates into an SVG path."""

```
points = []

for coordinate in ring:
    if len(coordinate) < 2:
        continue

    lon = coordinate[0]
    lat = coordinate[1]

    x = 30 + ((lon - min_lon) / (max_lon - min_lon)) * 840
    y = 30 + ((max_lat - lat) / (max_lat - min_lat)) * 840

    points.append((x, y))

if len(points) < 3:
    return ""

commands = [f"M {points[0][0]:.2f} {points[0][1]:.2f}"]

for x, y in points[1:]:
    commands.append(f"L {x:.2f} {y:.2f}")

commands.append("Z")
return " ".join(commands)
```

# -----------------------------

# BHARAT EXPLORER PAGE

# -----------------------------

@app.route("/bharat-map")
def bharat_map():
try:
response = requests.get(
INDIA_GEOJSON_URL,
timeout=25
)
response.raise_for_status()

```
    geojson = response.json()
    features = geojson.get("features", [])

    if not features:
        raise ValueError("The map data contains no regions.")

    # Find the geographic boundaries
    all_coordinates = []

    for feature in features:
        geometry = feature.get("geometry", {})

        for ring in collect_rings(geometry):
            for coordinate in ring:
                if len(coordinate) >= 2:
                    lon, lat = coordinate[0], coordinate[1]

                    if -180 <= lon <= 180 and -90 <= lat <= 90:
                        all_coordinates.append((lon, lat))

    if not all_coordinates:
        raise ValueError("No valid map coordinates were found.")

    min_lon = min(point[0] for point in all_coordinates)
    max_lon = max(point[0] for point in all_coordinates)
    min_lat = min(point[1] for point in all_coordinates)
    max_lat = max(point[1] for point in all_coordinates)

    if max_lon == min_lon or max_lat == min_lat:
        raise ValueError("The map boundaries are invalid.")

    # Draw the SVG map
    map_shapes = []

    for number, feature in enumerate(features, start=1):
        name = get_feature_name(feature, number)
        safe_name = html.escape(name, quote=True)
        geometry = feature.get("geometry", {})

        paths = []

        for ring in collect_rings(geometry):
            path_data = make_map_path(
                ring,
                min_lon,
                max_lon,
                min_lat,
                max_lat
            )

            if path_data:
                paths.append(path_data)

        if paths:
            combined_path = " ".join(paths)

            map_shapes.append(
                f'<path d="{combined_path}" '
                f'class="state-shape" '
                f'data-name="{safe_name}">'
                f'<title>{safe_name}</title>'
                f'</path>'
            )

    svg_content = "\n".join(map_shapes)

    page = f"""
```

<!DOCTYPE html>

<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>SHIVA AI - Bharat Explorer</title>

<style>
* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    padding: 20px;
    background: #050505;
    color: #00ff66;
    font-family: Arial, sans-serif;
    text-align: center;
}}

h1 {{
    margin-bottom: 8px;
}}

.subtitle {{
    color: #b7b7b7;
    margin-bottom: 20px;
}}

.map-container {{
    width: 100%;
    max-width: 850px;
    margin: auto;
    padding: 12px;
    background: #101010;
    border: 1px solid #00ff66;
    border-radius: 12px;
}}

svg {{
    width: 100%;
    height: auto;
    display: block;
}}

.state-shape {{
    fill: #103d27;
    stroke: #00ff66;
    stroke-width: 1.2;
    stroke-linejoin: round;
    cursor: pointer;
    transition: fill 0.2s;
}}

.state-shape:hover {{
    fill: #16834a;
}}

#state-name {{
    margin-top: 15px;
    min-height: 28px;
    font-size: 18px;
    font-weight: bold;
}}

.note {{
    color: #aaa;
    font-size: 13px;
    margin-top: 15px;
}}
</style>

</head>

<body>

<h1>🇮🇳 BHARAT EXPLORER</h1>

<p class="subtitle">
Explore India's state boundaries
</p>

<div class="map-container">
    <svg viewBox="0 0 900 900"
         role="img"
         aria-label="Map of India showing state boundaries">

```
    {svg_content}

</svg>
```

</div>

<div id="state-name">
    Select a region on the map.
</div>

<p class="note">
Map boundaries are provided by an external GeoJSON data source.
</p>

<script>
document.querySelectorAll(".state-shape").forEach(function(shape) {{
    shape.addEventListener("click", function() {{
        document.getElementById("state-name").textContent =
            this.getAttribute("data-name");
    }});
}});
</script>

</body>
</html>
"""

```
    return Response(page, mimetype="text/html")

except requests.exceptions.RequestException:
    return Response(
        "<h2>Could not load India's map data. Please try again later.</h2>",
        status=502,
        mimetype="text/html"
    )

except Exception:
    app.logger.exception("Bharat map error")
    return Response(
        "<h2>Something went wrong while creating the map.</h2>",
        status=500,
        mimetype="text/html"
    )
```

# -----------------------------

# RUN LOCALLY

# -----------------------------

if **name** == "**main**":
app.run(
host="0.0.0.0",
port=int(os.environ.get("PORT", 5000)),
debug=False
)
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
