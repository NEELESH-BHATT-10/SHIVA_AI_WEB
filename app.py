import os
import re
import html
import requests

from flask import Flask, request, jsonify, Response

app = Flask(**name**)

# --------------------------------------------------

# SHIVA AI CONFIGURATION

# --------------------------------------------------

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
AI_MODEL = "openrouter/free"

# India state-boundary GeoJSON data

INDIA_GEOJSON_URL = (
"https://raw.githubusercontent.com/geohacker/india/master/state/india_state.geojson"
)

# --------------------------------------------------

# HOME PAGE

# --------------------------------------------------

@app.route("/")
def home():
try:
with open("index.html", "r", encoding="utf-8") as file:
return file.read()
except FileNotFoundError:
return "SHIVA AI: index.html was not found.", 404

# --------------------------------------------------

# HEALTH CHECK

# --------------------------------------------------

@app.route("/health")
def health():
return jsonify({
"status": "online",
"app": "SHIVA AI",
"creator": "Neelesh Bhatt"
})

# --------------------------------------------------

# CREATOR QUESTION DETECTION

# --------------------------------------------------

def is_creator_question(message):
text = message.lower()

```
patterns = [
    r"\bwho\s+(made|created|built|developed|designed)\s+(you|shiva|shiva ai)\b",
    r"\bwho\s+is\s+(your|the)\s+(creator|developer|owner|founder|maker)\b",
    r"\bwho\s+is\s+behind\s+(you|shiva|shiva ai)\b",
    r"\bwho\s+owns\s+(you|shiva|shiva ai)\b",
    r"\bwho\s+developed\s+(you|shiva|shiva ai)\b",
    r"\bwho\s+is\s+your\s+boss\b",
    r"\bwho\s+made\s+shiva ai\b",
    r"\bwho\s+created\s+shiva ai\b"
]

return any(re.search(pattern, text) for pattern in patterns)
```

# --------------------------------------------------

# AI CHAT API

# --------------------------------------------------

@app.route("/api/chat", methods=["POST"])
def chat():
data = request.get_json(silent=True) or {}
message = str(data.get("message", "")).strip()

```
if not message:
    return jsonify({"error": "Please enter a message."}), 400

if len(message) > 4000:
    return jsonify({"error": "Message is too long."}), 400

# Answer creator questions directly
if is_creator_question(message):
    return jsonify({
        "reply": "Neelesh Bhatt."
    })

# Check API key
if not OPENROUTER_API_KEY:
    return jsonify({
        "error": "AI service is not configured. Add OPENROUTER_API_KEY in Render environment variables."
    }), 503

headers = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://shiva-ai-neelesh.onrender.com/",
    "X-Title": "SHIVA AI"
}

payload = {
    "model": AI_MODEL,
    "messages": [
        {
            "role": "system",
            "content": (
                "You are SHIVA AI, a helpful AI assistant created by "
                "Neelesh Bhatt. Be clear, respectful, accurate and "
                "helpful. If you are unsure about something, say so. "
                "Do not claim to have performed actions you cannot perform."
            )
        },
        {
            "role": "user",
            "content": message
        }
    ],
    "temperature": 0.7
}

try:
    response = requests.post(
        OPENROUTER_URL,
        headers=headers,
        json=payload,
        timeout=60
    )

    if response.status_code != 200:
        try:
            error_data = response.json()
            error_message = error_data.get("error", {}).get(
                "message", "AI provider returned an error."
            )
        except (ValueError, AttributeError):
            error_message = "AI provider returned an error."

        app.logger.error(
            "OpenRouter error %s: %s",
            response.status_code,
            error_message
        )

        return jsonify({
            "error": "AI service error: " + str(error_message)
        }), 502

    result = response.json()

    reply = (
        result.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )

    if isinstance(reply, list):
        reply = " ".join(
            item.get("text", "")
            for item in reply
            if isinstance(item, dict)
        )

    reply = str(reply).strip()

    if not reply:
        return jsonify({
            "error": "The AI returned an empty response. Please try again."
        }), 502

    return jsonify({"reply": reply})

except requests.Timeout:
    return jsonify({
        "error": "The AI service took too long to respond. Please try again."
    }), 504

except requests.RequestException:
    app.logger.exception("OpenRouter connection failed")
    return jsonify({
        "error": "Could not connect to the AI service."
    }), 502

except (ValueError, KeyError, IndexError, TypeError):
    app.logger.exception("Invalid AI response")
    return jsonify({
        "error": "The AI service returned an unexpected response."
    }), 502
```

# --------------------------------------------------

# BHARAT EXPLORER - PYTHON GENERATED INDIA MAP

# --------------------------------------------------

@app.route("/bharat-map")
def bharat_map():
try:
response = requests.get(
INDIA_GEOJSON_URL,
timeout=30
)
response.raise_for_status()

```
    geojson = response.json()
    features = geojson.get("features", [])

    if not features:
        raise ValueError("The map data contains no state features.")

    # SVG map dimensions
    width = 900
    height = 850
    padding = 35

    # Gather all coordinates to calculate map bounds
    all_points = []

    def collect_points(coords):
        if not isinstance(coords, list):
            return

        if (
            len(coords) >= 2
            and isinstance(coords[0], (int, float))
            and isinstance(coords[1], (int, float))
        ):
            lon, lat = coords[0], coords[1]

            # Ignore coordinates outside the broad India region
            if 60 <= lon <= 105 and 0 <= lat <= 42:
                all_points.append((lon, lat))
            return

        for item in coords:
            collect_points(item)

    for feature in features:
        geometry = feature.get("geometry") or {}
        collect_points(geometry.get("coordinates", []))

    if not all_points:
        raise ValueError("No usable India map coordinates were found.")

    min_lon = min(point[0] for point in all_points)
    max_lon = max(point[0] for point in all_points)
    min_lat = min(point[1] for point in all_points)
    max_lat = max(point[1] for point in all_points)

    lon_range = max(max_lon - min_lon, 0.001)
    lat_range = max(max_lat - min_lat, 0.001)

    # Keep the map proportional inside the SVG viewBox
    available_width = width - 2 * padding
    available_height = height - 2 * padding

    scale = min(
        available_width / lon_range,
        available_height / lat_range
    )

    drawn_width = lon_range * scale
    drawn_height = lat_range * scale

    offset_x = (width - drawn_width) / 2
    offset_y = (height - drawn_height) / 2

    def project(lon, lat):
        x = offset_x + (lon - min_lon) * scale
        y = height - offset_y - (lat - min_lat) * scale
        return x, y

    def make_ring_path(ring):
        points = []

        for coordinate in ring:
            if len(coordinate) < 2:
                continue

            lon, lat = coordinate[0], coordinate[1]

            if not (
                min_lon - 1 <= lon <= max_lon + 1
                and min_lat - 1 <= lat <= max_lat + 1
            ):
                continue

            x, y = project(lon, lat)
            points.append((x, y))

        if len(points) < 3:
            return ""

        commands = [
            f"M {points[0][0]:.2f} {points[0][1]:.2f}"
        ]

        for x, y in points[1:]:
            commands.append(f"L {x:.2f} {y:.2f}")

        commands.append("Z")
        return " ".join(commands)

    svg_shapes = []

    for feature in features:
        properties = feature.get("properties") or {}

        state_name = (
            properties.get("name")
            or properties.get("NAME_1")
            or properties.get("NAME")
            or properties.get("st_nm")
            or "Indian region"
        )

        geometry = feature.get("geometry") or {}
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates", [])

        if geometry_type == "Polygon":
            polygons = [coordinates]
        elif geometry_type == "MultiPolygon":
            polygons = coordinates
        else:
            continue

        for polygon in polygons:
            ring_paths = []

            for ring in polygon:
                path = make_ring_path(ring)
                if path:
                    ring_paths.append(path)

            if not ring_paths:
                continue

            safe_name = html.escape(str(state_name), quote=True)
            combined_path = " ".join(ring_paths)

            svg_shapes.append(
                f'<path d="{combined_path}" '
                f'fill="#103d25" '
                f'stroke="#35ff83" '
                f'stroke-width="1.4" '
                f'stroke-linejoin="round">'
                f'<title>{safe_name}</title>'
                f'</path>'
            )

    if not svg_shapes:
        raise ValueError("No state boundaries could be drawn.")

    svg = f"""
    <svg
        viewBox="0 0 {width} {height}"
        xmlns="http://www.w3.org/2000/svg"
        role="img"
        aria-label="Map of India showing state boundaries"
        style="width:100%;height:auto;display:block;background:#07120c"
    >
        <rect width="{width}" height="{height}" fill="#07120c"/>
        {''.join(svg_shapes)}
    </svg>
    """

    page = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>SHIVA AI - Bharat Explorer</title>
        <style>
            * {{ box-sizing:border-box; }}
            body {{
                margin:0;
                padding:16px;
                background:#07120c;
                color:#35ff83;
                font-family:Consolas,monospace;
                text-align:center;
            }}
            h2 {{ color:#ff3030; }}
            .map {{
                max-width:800px;
                margin:15px auto;
                border:1px solid #35ff83;
                border-radius:8px;
                overflow:hidden;
            }}
            .note {{
                color:#a5dcb5;
                font-size:12px;
                line-height:1.6;
            }}
        </style>
    </head>
    <body>
        <h2>BHARAT EXPLORER</h2>
        <p>Explore India's state boundaries</p>
        <div class="map">{svg}</div>
        <p class="note">
            State-boundary map generated by the SHIVA AI Python server.
            Map data is provided by its external GeoJSON source.
        </p>
        <p>SHIVA AI | BY NEELESH BHATT</p>
    </body>
    </html>
    """

    return Response(page, mimetype="text/html")

except requests.RequestException:
    app.logger.exception("Could not download India map data")
    return Response(
        "<h2>India map data could not be downloaded.</h2>"
        "<p>Please try again later.</p>",
        status=502,
        mimetype="text/html"
    )

except (ValueError, TypeError, KeyError):
    app.logger.exception("Could not create India map")
    return Response(
        "<h2>India map could not be created.</h2>"
        "<p>Please check the GeoJSON data source.</p>",
        status=500,
        mimetype="text/html"
    )
```

# --------------------------------------------------

# RUN LOCAL DEVELOPMENT SERVER

# --------------------------------------------------

if **name** == "**main**":
app.run(
host="0.0.0.0",
port=int(os.environ.get("PORT", 5000)),
debug=False
)
