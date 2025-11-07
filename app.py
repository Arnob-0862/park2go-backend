import os, math, sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify
from dynamicpricing import (
    get_base_price, get_global_weights, calculate_all_scores, calculate_dynamic_price
)

DB_PATH = "slot_timeseries_full_dhaka.db"
PORT = int(os.environ.get("PORT", 10000))

app = Flask(__name__)

# --- Helper functions ---

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2)
    return 2 * R * math.asin(math.sqrt(a))

# Dhaka location map
GEO_MAP = {
    "gulshan": (23.7925, 90.4078),
    "banani": (23.7934, 90.4043),
    "bashundhara": (23.8103, 90.4316),
    "dhanmondi": (23.7465, 90.3760),
    "mirpur": (23.8151, 90.3630),
    "uttara": (23.8740, 90.3976),
    "tejgaon": (23.7807, 90.4120),
    "mohakhali": (23.7805, 90.3925),
    "farmgate": (23.7570, 90.3910),
    "motijheel": (23.7323, 90.4160),
    "lalbagh": (23.7189, 90.3880),
    "shahbagh": (23.7386, 90.3954),
    "khilgaon": (23.7465, 90.4320),
    "rampura": (23.7638, 90.4245),
    "badda": (23.7805, 90.4262),
    "mohammadpur": (23.7589, 90.3580),
    "agargaon": (23.7780, 90.3750),
    "kalyanpur": (23.7888, 90.3582),
    "pallabi": (23.8295, 90.3654),
    "kamalapur": (23.7380, 90.4240),
}

def geocode_location(q: str):
    if not q:
        return None
    key = q.strip().lower()
    for name, coords in GEO_MAP.items():
        if name in key:
            return coords
    return None

def round_to_half_hour(dt):
    minute = 0 if dt.minute < 30 else 30
    return f"{dt.hour:02d}:{minute:02d}"

# --- API route ---
@app.route("/recommendations")
def recommendations():
    qloc = request.args.get("location")
    if qloc:
        coords = geocode_location(qloc)
        if not coords:
            return jsonify({"error": f"Unknown location '{qloc}'"}), 400
        user_lat, user_lon = coords
    else:
        try:
            user_lat = float(request.args["lat"])
            user_lon = float(request.args["lon"])
        except:
            return jsonify({"error": "Provide ?location=Dhaka area OR lat/lon"}), 400

    vehicle_pref = request.args.get("vehicle_type")
    booking_pref = request.args.get("booking_type")
    alpha = float(request.args.get("alpha", 0.5))
    delta_bar = float(request.args.get("delta_bar", 0.55))

    now = datetime.now(ZoneInfo("Asia/Dhaka"))
    day = now.strftime("%A")
    hhmm = round_to_half_hour(now)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    sql = "SELECT * FROM slot_timeseries WHERE day_of_week=? AND timestamp=?"
    params = [day, hhmm]
    if vehicle_pref:
        sql += " AND vehicle_type=?"
        params.append(vehicle_pref)
    rows = cur.execute(sql, params).fetchall()
    conn.close()

    weights = get_global_weights()
    results = []
    for r in rows:
        lat, lon = float(r["latitude"]), float(r["longitude"])
        dist = haversine_km(user_lat, user_lon, lat, lon)
        if dist > 2.0:
            continue

        vt = (r["vehicle_type"] or "").lower()
        vt_model = "motorcycle" if "bike" in vt else "car"
        bt = (r["booking_type"] or "Regular").lower()
        base_price = get_base_price(bt, vt_model)

        inputs = {
            "requests_per_min": float(r["requests_per_min"]),
            "Rmax": float(r["Rmax"]),
            "avg_occupied_slots_hist": float(r["avg_occupied_slots_hist"]),
            "total_slots": int(r["total_slots"]),
            "bookings_last_hour": int(r["bookings_last_hour"]),
            "views_last_hour": int(r["views_last_hour"]),
            "free_slots": int(r["free_slots"]),
            "successful_bookings_30d": int(r["successful_bookings_30d"]),
            "accepted_bookings_30d": int(r["accepted_bookings_30d"]),
            "avg_speed": float(r["avg_speed"]),
            "free_flow_speed": float(r["free_flow_speed"]),
            "vehicle_density": float(r["vehicle_density"]),
            "DensityMax": float(r["DensityMax"]),
            "local_average_price": float(r["local_average_price"]),
            "rain_mm_last_30min": float(r["rain_mm_last_30min"]),
            "rain_max_mm": float(r["rain_max_mm"]),
            "is_waterlogged": bool(int(r["is_waterlogged"])),
            "current_hour": int(r["current_hour"]),
            "is_holiday_or_event": bool(int(r["is_holiday_or_event"])),
            "cctv_coverage_percent": float(r["cctv_coverage_percent"]),
            "road_width_m": float(r["road_width_m"]),
            "max_width_for_score": float(r["max_width_for_score"]),
            "adjacent_areas": []
        }

        scores = calculate_all_scores(inputs)
        dyn_price, delta_i, mult = calculate_dynamic_price(
            base_price, scores, weights, alpha, delta_bar
        )

        results.append({
            "unique_id": r["unique_id"],
            "location_name": r["location_name"],
            "distance_km": round(dist, 3),
            "vehicle_type": r["vehicle_type"],
            "booking_type": r["booking_type"],
            "adjusted_price": round(dyn_price, 2),
            "free_slots": int(r["free_slots"]),
            "safety_point": float(r["safety_point"]),
        })

    results.sort(key=lambda x: (x["adjusted_price"], x["distance_km"]))
    return jsonify({
        "query": {"location": qloc, "lat": user_lat, "lon": user_lon, "day": day, "time": hhmm},
        "results": results[:5]
    })

@app.route("/")
def home():
    return jsonify({"message": "Park2Go API is running!"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
