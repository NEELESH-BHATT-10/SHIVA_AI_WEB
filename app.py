import os
import json
import re
import html
import requests

from flask import Flask, request, jsonify, Response

app = Flask(__name__)

# =============================
# SHIVA AI CONFIGURATION
# =============================

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openrouter/free"


# =============================
# FUNNY COMEBACKS
# =============================

def get_funny_comeback(message):
    text = message.lower().strip()

    funny_phrases = [
        "potty khale", "potty kha le",
        "tatti khale", "tatti kha le",
        "eat shit", "eat poop",
        "gu khale", "gū khale",
        "gobar khale", "gobar kha le"
    ]

    for phrase in funny_phrases:
        if phrase in text:
            return "Tu khale 😂"

    return None


# =============================
# CREATOR IDENTIFICATION
# =============================

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

    return any(
        re.search(pattern, message, re.IGNORECASE)
        for pattern in patterns
    )


# =============================
# HOME PAGE
# =============================

@app.route("/")
def home():
    try:
        with open(
            os.path.join(app.root_path, "index.html"),
            "r",
            encoding="utf-8"
        ) as file:
            return file.read()

    except FileNotFoundError:
        return "index.html was not found.", 404


# =============================
# HEALTH CHECK
# =============================

@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "app": "SHIVA AI"
    })


# =============================
# AI CHAT API
# =============================

@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True) or {}
        message = str(data.get("message", "")).strip()

        if not message:
            return jsonify({
                "reply": "Please enter a message."
            }), 400

        comeback = get_funny_comeback(message)

        if comeback:
            return jsonify({"reply": comeback})

        if is_creator_question(message):
            return jsonify({
                "reply": "SHIVA AI was created by Neelesh Bhatt."
            })

        if not OPENROUTER_API_KEY:
            return jsonify({
                "reply": "AI service is not configured. Check OPENROUTER_API_KEY on Render."
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
                        "You are SHIVA AI, a helpful assistant "
                        "created by Neelesh Bhatt. "
                        "Give clear and accurate answers."
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

        response.raise_for_status()

        result = response.json()
        reply = result["choices"][0]["message"]["content"]

        return jsonify({
            "reply": reply or "Please try again."
        })

    except requests.exceptions.Timeout:
        return jsonify({
            "reply": "The AI service timed out. Please try again."
        }), 504

    except requests.exceptions.RequestException:
        app.logger.exception("OpenRouter request failed")

        return jsonify({
            "reply": "The AI service is temporarily unavailable."
        }), 502

    except Exception:
        app.logger.exception("Chat error")

        return jsonify({
            "reply": "Something went wrong. Please try again."
        }), 500


# =============================
# INDIA MAP HELPERS
# =============================

def get_feature_name(feature, number):
    properties = feature.get("properties", {})

    for key in ("name", "NAME_1", "NAME", "st_nm", "state", "State"):
        value = properties.get(key)

        if value:
            return str(value)

    return f"Region {number}"


def collect_rings(geometry):
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


def make_map_path(ring, min_lon, max_lon, min_lat, max_lat):
    points = []

    lon_range = max(max_lon - min_lon, 0.000001)
    lat_range = max(max_lat - min_lat, 0.000001)

    width = 900
    height = 800

    scale = min(840 / lon_range, 740 / lat_range)

    offset_x = (width - lon_range * scale) / 2
    offset_y = (height - lat_range * scale) / 2

    for coordinate in ring:
        if len(coordinate) < 2:
            continue

        lon, lat = coordinate[0], coordinate[1]

        x = offset_x + (lon - min_lon) * scale
        y = offset_y + (max_lat - lat) * scale

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


# =============================
# DISTRICT DATA API
# =============================

@app.route("/map-data/districts")
def district_data():
    try:
        district_file = os.path.join(
            app.root_path,
            "map_data",
            "india_districts_clean.geojson"
        )

        with open(
            district_file,
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)

        return jsonify(data)

    except Exception:
        app.logger.exception("Could not load district map data")

        return Response(
            "District data unavailable",
            status=500,
            mimetype="text/plain"
        )


# =============================
# BHARAT MAP
# =============================

@app.route("/bharat-map")
def bharat_map():

    try:
        map_file = os.path.join(
            app.root_path,
            "map_data",
            "india_states.geojson"
        )

        with open(
            map_file,
            "r",
            encoding="utf-8"
        ) as file:
            geojson = json.load(file)

        features = geojson.get("features", [])

        if not features:
            raise ValueError("No map regions found.")

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
            raise ValueError("No valid map coordinates.")

        min_lon = min(point[0] for point in all_coordinates)
        max_lon = max(point[0] for point in all_coordinates)

        min_lat = min(point[1] for point in all_coordinates)
        max_lat = max(point[1] for point in all_coordinates)

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
                    f'<title>{safe_name}</title></path>'
                )

        svg_content = "\n".join(map_shapes)

        # =============================
        # HTML PAGE
        # =============================

        page = f"""
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

#india-map {{
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
}}

.state-shape:hover {{
    fill: #16834a;
}}

.district-shape {{
    fill: rgba(0,255,100,0.08);
    stroke: #ffffff;
    stroke-width: 1.2;
    vector-effect: non-scaling-stroke;
    cursor: pointer;
}}

.district-shape:hover {{
    fill: rgba(0,255,100,0.35);
}}

#locate-me,
#reset-map {{
    background: #00ff66;
    color: #050505;
    border: none;
    border-radius: 8px;
    padding: 12px 20px;
    font-size: 15px;
    font-weight: bold;
    cursor: pointer;
    margin: 10px;
}}

#locate-me:disabled {{
    opacity: 0.5;
    cursor: wait;
}}

#location-result {{
    color: white;
    margin: 12px auto;
    max-width: 700px;
    line-height: 1.6;
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

<h1>BHARAT EXPLORER</h1>

<p class="subtitle">
Explore India's states, union territories and districts.
</p>

<button id="locate-me" type="button">
📍 Find my location
</button>

<button id="reset-map" type="button">
↩ Back to India
</button>

<div id="location-result" aria-live="polite">
Your location has not been detected yet.
</div>

<div class="map-container">

<svg
    id="india-map"
    viewBox="0 0 900 900"
    role="img"
    aria-label="Map of India showing state boundaries"
    data-min-lon="{min_lon}"
    data-max-lon="{max_lon}"
    data-min-lat="{min_lat}"
    data-max-lat="{max_lat}"
>

{svg_content}

<g id="district-layer"></g>

<circle
    id="location-marker"
    cx="0"
    cy="0"
    r="0"
    fill="#ff3333"
    stroke="white"
    stroke-width="3"
    style="display:none; pointer-events:none;"
/>

</svg>

</div>

<div id="state-name">
Select a region on the map.
</div>

<p class="note">
Map data: Survey of India source files.
District information is based on the supplied district dataset.
</p>

<script>

// =============================
// MAP ELEMENTS
// =============================

const map = document.getElementById("india-map");

const districtLayer = document.getElementById("district-layer");

const locateButton = document.getElementById("locate-me");

const resetButton = document.getElementById("reset-map");

const locationResult = document.getElementById("location-result");

const marker = document.getElementById("location-marker");

const stateNameDisplay = document.getElementById("state-name");

const originalViewBox = map.getAttribute("viewBox");

let districtData = null;


// =============================
// NAME NORMALISATION
// =============================

function normaliseName(name) {{
    return (name || "")
        .toUpperCase()
        .replace(/[^A-Z0-9]/g, "");
}}


// =============================
// COORDINATE PROJECTION
// =============================

function projectPoint(lon, lat) {{

    const minLon = Number(map.dataset.minLon);
    const maxLon = Number(map.dataset.maxLon);

    const minLat = Number(map.dataset.minLat);
    const maxLat = Number(map.dataset.maxLat);

    const lonRange = Math.max(maxLon - minLon, 0.000001);
    const latRange = Math.max(maxLat - minLat, 0.000001);

    const scale = Math.min(840 / lonRange, 740 / latRange);

    const offsetX = (900 - lonRange * scale) / 2;
    const offsetY = (800 - latRange * scale) / 2;

    return [
        offsetX + (lon - minLon) * scale,
        offsetY + (maxLat - lat) * scale
    ];
}}


// =============================
// GEOJSON TO SVG
// =============================

function ringToPath(ring) {{

    const points = ring.map(point =>
        projectPoint(point[0], point[1])
    );

    if (points.length < 3) return "";

    return "M " + points.map(point =>
        point[0].toFixed(2) + " " +
        point[1].toFixed(2)
    ).join(" L ") + " Z";
}}


function geometryToPath(geometry) {{

    const paths = [];

    function addPolygon(polygon) {{

        polygon.forEach(ring => {{

            const path = ringToPath(ring);

            if (path) paths.push(path);

        }});
    }}

    if (geometry.type === "Polygon") {{

        addPolygon(geometry.coordinates);

    }} else if (geometry.type === "MultiPolygon") {{

        geometry.coordinates.forEach(addPolygon);

    }}

    return paths.join(" ");
}}


// =============================
// LOAD DISTRICT DATA
// =============================

async function loadDistrictData() {{

    if (districtData) return districtData;

    const response = await fetch("/map-data/districts");

    if (!response.ok) {{
        throw new Error("Could not load district data.");
    }}

    districtData = await response.json();

    if (!districtData.features) {{
        throw new Error("Invalid district data.");
    }}

    return districtData;
}}


// =============================
// RESET MAP
// =============================

function resetMap() {{

    map.setAttribute("viewBox", originalViewBox);

    districtLayer.innerHTML = "";

    stateNameDisplay.textContent =
        "Select a region on the map.";

    marker.style.display = "none";

    marker.setAttribute("r", "0");
}}

resetButton.addEventListener("click", resetMap);


// =============================
// STATE CLICK AND ZOOM
// =============================

document.querySelectorAll(".state-shape").forEach(function(shape) {{

    shape.addEventListener("click", async function() {{

        const stateName = this.getAttribute("data-name");

        stateNameDisplay.textContent =
            "Loading " + stateName + "...";

        try {{

            const data = await loadDistrictData();

            const selectedName = normaliseName(stateName);

            const districts = data.features.filter(feature =>

                normaliseName(feature.properties.state) === selectedName

            );

            districtLayer.innerHTML = "";

            if (districts.length === 0) {{

                stateNameDisplay.textContent =
                    stateName + " — No matching district records found.";

                return;
            }}

            districts.forEach(function(feature) {{

                const path = document.createElementNS(
                    "http://www.w3.org/2000/svg",
                    "path"
                );

                path.setAttribute(
                    "d",
                    geometryToPath(feature.geometry)
                );

                path.setAttribute("class", "district-shape");

                path.setAttribute(
                    "data-district",
                    feature.properties.district
                );

                path.addEventListener("click", function(event) {{

                    event.stopPropagation();

                    stateNameDisplay.textContent =
                        stateName + " — " +
                        feature.properties.district;

                }});

                districtLayer.appendChild(path);

            }});

            // Zoom into selected state

            const box = this.getBBox();

            const padding = Math.max(
                box.width,
                box.height
            ) * 0.12;

            const newViewBox = [
                box.x - padding,
                box.y - padding,
                box.width + padding * 2,
                box.height + padding * 2
            ].join(" ");

            map.setAttribute("viewBox", newViewBox);

            stateNameDisplay.textContent =
                stateName + " — " +
                districts.length + " district records";

        }} catch (error) {{

            stateNameDisplay.textContent =
                "Could not load districts for " + stateName + ".";

            console.error(error);

        }}
    }});

}});


// =============================
// LOCATION DETECTION
// =============================

function pointInRing(point, ring) {{

    const x = point[0];
    const y = point[1];

    let inside = false;

    for (
        let i = 0, j = ring.length - 1;
        i < ring.length;
        j = i++
    ) {{

        const xi = ring[i][0];
        const yi = ring[i][1];

        const xj = ring[j][0];
        const yj = ring[j][1];

        if (
            (yi > y) !== (yj > y) &&
            x < (xj - xi) * (y - yi) / (yj - yi) + xi
        ) {{
            inside = !inside;
        }}
    }}

    return inside;
}}


function pointInGeometry(lon, lat, geometry) {{

    const point = [lon, lat];

    if (geometry.type === "Polygon") {{

        const rings = geometry.coordinates;

        if (!pointInRing(point, rings[0])) return false;

        for (let i = 1; i < rings.length; i++) {{

            if (pointInRing(point, rings[i])) return false;

        }}

        return true;
    }}

    if (geometry.type === "MultiPolygon") {{

        return geometry.coordinates.some(polygon =>

            pointInGeometry(lon, lat, {{
                type: "Polygon",
                coordinates: polygon
            }})

        );
    }}

    return false;
}}


// =============================
// FIND MY LOCATION
// =============================

locateButton.addEventListener("click", function() {{

    if (!navigator.geolocation) {{

        locationResult.textContent =
            "Your browser does not support location detection.";

        return;
    }}

    locateButton.disabled = true;

    locationResult.textContent =
        "Detecting your current location...";

    navigator.geolocation.getCurrentPosition(

        async function(position) {{

            try {{

                const lon = position.coords.longitude;
                const lat = position.coords.latitude;

                const data = await loadDistrictData();

                const district = data.features.find(function(feature) {{

                    return pointInGeometry(
                        lon,
                        lat,
                        feature.geometry
                    );

                }});

                const point = projectPoint(lon, lat);

                marker.setAttribute("cx", point[0]);
                marker.setAttribute("cy", point[1]);

                marker.setAttribute("r", "9");

                marker.style.display = "block";

                if (district) {{

                    const properties = district.properties;

                    locationResult.textContent =
                        "📍 State/UT: " + properties.state +
                        " | District: " + properties.district +
                        " | GPS accuracy: approximately " +
                        Math.round(position.coords.accuracy) +
                        " metres.";

                    stateNameDisplay.textContent =
                        properties.state + " — " +
                        properties.district;

                }} else {{

                    locationResult.textContent =
                        "Location detected, but no matching district was found.";

                }}

            }} catch (error) {{

                locationResult.textContent =
                    "Location lookup failed: " + error.message;

                console.error(error);

            }} finally {{

                locateButton.disabled = false;

            }}
        }},

        function(error) {{

            locationResult.textContent =
                "Location unavailable. Please allow browser location permission.";

            locateButton.disabled = false;

        }},

        {{
            enableHighAccuracy: true,
            timeout: 20000,
            maximumAge: 0
        }}
    );
}});

</script>

</body>
</html>
"""

        return Response(page, mimetype="text/html")

    except Exception:

        app.logger.exception("Bharat map error")

        return Response(
            "<h2>Something went wrong while creating the map.</h2>",
            status=500,
            mimetype="text/html"
        )


# =============================
# RUN SHIVA AI
# =============================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )