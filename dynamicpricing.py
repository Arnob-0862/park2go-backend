import numpy as np



def clamp(value, min_val, max_val):
    """
    Clamps a value between a minimum and maximum bound.
    """
    return max(min_val, min(value, max_val))


def calc_sc_d1(requests_per_min, Rmax):
    """
    Calculates SC_D1: Real-time request rate score.
    - requests_per_min: Current requests per minute for the area.
    - Rmax: Estimated maximum requests per minute (e.g., 5).
    """
    if Rmax == 0:
        return 0.0
    score = min(1.0, requests_per_min / Rmax)
    return score

def calc_sc_d2(avg_occupied_slots_hist, total_slots):
    """
    Calculates SC_D2: Historical peak occupancy score.
    - avg_occupied_slots_hist: Avg occupied slots during this hour in past 30 days.
    - total_slots: Total slots in the area.
    """
    if total_slots == 0:
        return 0.0
    occupancy_ratio = avg_occupied_slots_hist / total_slots
    score = clamp(occupancy_ratio, 0.0, 1.0) # Ensure score is [0, 1]
    return score

def calc_sc_d3(bookings_last_hour, views_last_hour):
    """
    Calculates SC_D3: Booking conversion rate score.
    - bookings_last_hour: Number of bookings in the last hour.
    - views_last_hour: Number of views/searches in the last hour.
    """
    if views_last_hour == 0:
        return 0.0
    score = bookings_last_hour / views_last_hour
    return clamp(score, 0.0, 1.0)



def calc_sc_s1(free_slots, total_slots):
    """
    Calculates SC_S1: Available slots ratio score.
    - free_slots: Current number of free slots.
    - total_slots: Total slots in the area.
    """
    if total_slots == 0:
        return 1.0  # If no slots, treat as 'full' (max score)
    score = 1.0 - (free_slots / total_slots)
    return clamp(score, 0.0, 1.0)

def calc_sc_s2(successful_bookings_30d, accepted_bookings_30d):
    """
    Calculates SC_S2: Owner reliability score.
    - successful_bookings_30d: Fulfilled bookings in last 30 days.
    - accepted_bookings_30d: Total accepted bookings in last 30 days.
    """
    if accepted_bookings_30d == 0:
        return 0.0  # No data, assume 0 reliability for pricing
    score = successful_bookings_30d / accepted_bookings_30d
    return clamp(score, 0.0, 1.0)



def calc_sc_t1(avg_speed, free_flow_speed):
    """
    Calculates SC_T1: Speed index score.
    - avg_speed: Average speed (km/h) on nearby roads.
    - free_flow_speed: Free flow speed (km/h) on those roads.
    """
    if free_flow_speed == 0:
        return 1.0  # Cannot move, max congestion
    score = clamp(1.0 - (avg_speed / free_flow_speed), 0.0, 1.0)
    return score

def calc_sc_t2(vehicle_density, DensityMax):
    """
    Calculates SC_T2: Vehicle density score.
    - vehicle_density: Vehicles per km.
    - DensityMax: Estimated max density (e.g., 200).
    """
    if DensityMax == 0:
        return 0.0
    score = min(1.0, vehicle_density / DensityMax)
    return score



def calc_sc_a1(local_congestion_value, adjacent_congestion_values):
    """
    Calculates SC_A1: Adjacent congestion average score.
    - local_congestion_value: A congestion metric for the current area (e.g., SC_T1 or a composite).
    - adjacent_congestion_values: A list of congestion values for adjacent areas.
    """
    if not adjacent_congestion_values:
        return 0.0  # No adjacent areas, no differential
    
    mean_adj_congestion = np.mean(adjacent_congestion_values)
    local_val_safe = max(local_congestion_value, 0.01) # Avoid division by zero
    
    # Per PDF: "if positive: s = min(1, (localCongesionValue - Mean congestion of adjacent zones)/ local CongesionValue)"
    diff = local_congestion_value - mean_adj_congestion
    
    if diff > 0:
        # Local area is more congested than neighbors
        score = min(1.0, diff / local_val_safe)
    else:
        # Local area is less congested
        score = 0.0 # Per PDF: "if negative: s=0"
        
    return score

def calc_sc_a2(local_average_price, adjacent_average_prices):
    """
    Calculates SC_A2: Price differential score.
    - local_average_price: The average price in the current area.
    - adjacent_average_prices: A list of average prices for adjacent areas.
    """
    if not adjacent_average_prices:
        return 0.0 # No adjacent areas, no differential
    
    mean_adj_price = np.mean(adjacent_average_prices)
    local_price_safe = max(local_average_price, 0.01) # Avoid division by zero
    
    # Following logic of SC_A1: "mapped similar to SC_A1"
    # PDF formula has a typo (mentions congestion), applying price logic instead.
    diff = local_average_price - mean_adj_price
    
    if diff > 0:
        # Local area is MORE expensive than neighbors
        # This should *decrease* demand, so score should be 0 (or negative if we didn't clamp at 0)
        # Let's re-read the PDF for SC_A1: "increases price to nudge away"
        # This implies a high score (local > adj) *increases* the price.
        # So the logic from SC_A1 is correct.
        score = min(1.0, diff / local_price_safe)
    else:
        # Local area is LESS expensive than neighbors
        score = 0.0
        
    return score



def calc_sc_w1(rain_mm_last_30min, rain_max_mm):
    """
    Calculates SC_W1: Rain intensity score.
    - rain_mm_last_30min: Rain intensity in mm/hr (measured over last 30 min).
    - rain_max_mm: Intensity considered "heavy rain" (e.g., 20 mm/hr).
    """
    if rain_max_mm == 0:
        return 0.0
    score = clamp(rain_mm_last_30min / rain_max_mm, 0.0, 1.0)
    return score

def calc_sc_w2(is_waterlogged):
    """
    Calculates SC_W2: Waterlogging flag.
    - is_waterlogged: Boolean flag from reports.
    """
    return 1.0 if is_waterlogged else 0.0



def calc_sc_time1(current_hour, peak_hours):
    """
    Calculates SC_Time1: Hour category score.
    - current_hour: The current hour (0-23).
    - peak_hours: A list of tuples defining peak hour ranges, e.g., [(8, 10), (17, 20)].
      Ranges are inclusive at the start, exclusive at the end.
    """
    is_peak = False
    for start, end in peak_hours:
        if start <= current_hour < end:
            is_peak = True
            break
    return 1.0 if is_peak else 0.0

def calc_sc_time2(is_holiday_or_event):
    """
    Calculates SC_Time2: Holiday / Event flag.
    - is_holiday_or_event: Boolean flag.
    """
    return 1.0 if is_holiday_or_event else 0.0



def calc_sc_sa1(cctv_coverage_percent):
    """
    Calculates SC_SA1: CCTV coverage score.
    - cctv_coverage_percent: % of slot area visual coverage (0-100).
    """
    score = cctv_coverage_percent / 100.0
    return clamp(score, 0.0, 1.0)

def calc_sc_sa2(road_width_m, max_width_for_score):
    """
    Calculates SC_SA2: Road accessibility score.
    - road_width_m: Width of the road in meters.
    - max_width_for_score: Width (e.g., 10m) at which score becomes 0.
    """
    if max_width_for_score == 0:
        return 1.0 # Narrowest possible
    # "narrow roads raise complexity and thus price" -> high score for narrow road
    score = clamp(1.0 - (road_width_m / max_width_for_score), 0.0, 1.0)
    return score




BASE_PRICES = {
    "regular": {
        "car": 70.0,
        "motorcycle": 50.0
    },
    "premium": {
        "car": 100.0,
        "motorcycle": 70.0
    },
    "prebooked": {
        "car": 80.0,
        "motorcycle": 60.0
    }
}

def get_base_price(booking_type, vehicle_type):
    """
    Retrieves the base price from the BASE_PRICES dictionary.
    """
    try:
        return BASE_PRICES[booking_type.lower()][vehicle_type.lower()]
    except KeyError:
        print(f"Warning: Price not found for {booking_type}/{vehicle_type}. Defaulting to 70.0")
        return 70.0 # Default fallback

def get_global_weights():
    """
    Returns the AHP global weights from the PDF document (page 8).
    """
    return {
        "SC_D1": 0.1312,
        "SC_D2": 0.0775,
        "SC_D3": 0.0411,
        "SC_S1": 0.0659,
        "SC_S2": 0.0220,
        "SC_T1": 0.1187,
        "SC_T2": 0.0593,
        "SC_A1": 0.0984,
        "SC_A2": 0.0492,
        "SC_W1": 0.0491,
        "SC_W2": 0.0327,
        "SC_Time1": 0.0843,
        "SC_Time2": 0.0211,
        "SC_SA1": 0.0816,
        "SC_SA2": 0.0680,
    }

def calculate_all_scores(inputs):
    """
    Calculates all 15 scores from the raw inputs dictionary.
    """
    scores = {}
    
    # 1. Demand
    scores["SC_D1"] = calc_sc_d1(inputs["requests_per_min"], inputs["Rmax"])
    scores["SC_D2"] = calc_sc_d2(inputs["avg_occupied_slots_hist"], inputs["total_slots"])
    scores["SC_D3"] = calc_sc_d3(inputs["bookings_last_hour"], inputs["views_last_hour"])
    
    # 2. Supply
    scores["SC_S1"] = calc_sc_s1(inputs["free_slots"], inputs["total_slots"])
    scores["SC_S2"] = calc_sc_s2(inputs["successful_bookings_30d"], inputs["accepted_bookings_30d"])
    
    # 3. Traffic
    scores["SC_T1"] = calc_sc_t1(inputs["avg_speed"], inputs["free_flow_speed"])
    scores["SC_T2"] = calc_sc_t2(inputs["vehicle_density"], inputs["DensityMax"])
    
    # 4. Adjacent Areas
    # User provides a list of dicts for adjacent areas
    adj_areas = inputs.get("adjacent_areas", []) # e.g., [{"congestion": 0.4, "price": 80}, {"congestion": 0.6, "price": 85}]
    adj_congestion = [area["congestion"] for area in adj_areas if "congestion" in area]
    adj_prices = [area["price"] for area in adj_areas if "price" in area]

    # For SC_A1, we need a "local_congestion_value". Let's use SC_T1 as a proxy.
    local_congestion_for_A1 = scores["SC_T1"]
    scores["SC_A1"] = calc_sc_a1(local_congestion_for_A1, adj_congestion)
    scores["SC_A2"] = calc_sc_a2(inputs["local_average_price"], adj_prices)

    # 5. Weather
    scores["SC_W1"] = calc_sc_w1(inputs["rain_mm_last_30min"], inputs["rain_max_mm"])
    scores["SC_W2"] = calc_sc_w2(inputs["is_waterlogged"])
    
    # 6. Time & Day
    peak_hours = inputs["peak_hours"] # Now directly from inputs
    scores["SC_Time1"] = calc_sc_time1(inputs["current_hour"], peak_hours)
    scores["SC_Time2"] = calc_sc_time2(inputs["is_holiday_or_event"])
    
    # 7. Safety & Accessibility
    scores["SC_SA1"] = calc_sc_sa1(inputs["cctv_coverage_percent"])
    scores["SC_SA2"] = calc_sc_sa2(inputs["road_width_m"], inputs["max_width_for_score"])
    
    return scores

def calculate_dynamic_price(base_price, scores, weights, alpha, delta_bar):
    """
    Calculates the final dynamic price.
    - base_price: The base rate for the vehicle/booking type.
    - scores: Dictionary of calculated scores.
    - weights: Dictionary of global AHP weights.
    - alpha: Sensitivity coefficient (e..g, 0.4 to 0.6).
    - delta_bar: Citywide or zone-average composite score.
    """
    
    # Calculate Composite dynamic price adjustment factor (Delta_i)
    delta_i = 0.0
    for key in weights:
        delta_i += weights[key] * scores.get(key, 0.0)
        
    # Calculate Price Multiplier (M_i)
    multiplier = 1.0 + (alpha * (delta_i - delta_bar))
    
    # Calculate Final Dynamic Price
    dynamic_price = base_price * multiplier
    
    return dynamic_price, delta_i, multiplier


if __name__ == "__main__":
    
    print("--- Dynamic Parking Price Model Input ---")
    
    # You can change these default values to test the model
    # These inputs would come from your database, APIs, or user forms
    
    raw_inputs = {}

    # ---------------------------------------------------------------
    # --- 1. Model Configuration (Estimation Variables) ---
    # ---------------------------------------------------------------
    print("\n--- 1. Model Configuration (Set these based on your business logic) ---")
    
    try:
        raw_inputs["Rmax"] = float(input("SC_D1 - Rmax (Max Requests/min) [e.g., 5.0]: ") or 5.0)
        print("    -> This is your estimated 'busiest' request rate. If 5 req/min is 100% demand, set this to 5.")
        
        raw_inputs["DensityMax"] = float(input("SC_T2 - DensityMax (Max Vehicle Density) [e.g., 200.0]: ") or 200.0)
        print("    -> Vehicle density (veh/km) you consider 100% congested. This depends on road type.")

        raw_inputs["rain_max_mm"] = float(input("SC_W1 - Rain Max (mm/hr) [e.g., 20.0]: ") or 20.0)
        print("    -> Rain intensity (mm/hr) you consider 'heavy rain' (score 1.0). A light shower is ~2-3.")
        
        raw_inputs["max_width_for_score"] = float(input("SC_SA2 - Max Road Width (m) [e.g., 10.0]: ") or 10.0)
        print("    -> Road width (meters) at which accessibility is 'easy' (score 0.0). A narrow 3m road will get a high score.")

    except ValueError:
        print("Invalid input for configuration. Please restart and enter numbers.")
        exit()


    # ---------------------------------------------------------------
    # --- 2. GATHER ALL REAL-TIME INPUTS ---
    # ---------------------------------------------------------------
    print("\n--- 2. Real-time Data Input ---")
    
    try:
        print("\n--- 2a. Demand ---")
        raw_inputs["requests_per_min"] = float(input("Current requests/min (e.g., 2.5): ") or 2.5)
        raw_inputs["total_slots"] = int(input("Total parking slots (e.g., 50): ") or 50)
        raw_inputs["avg_occupied_slots_hist"] = int(input(f"Historical occupied slots (this hour, max {raw_inputs['total_slots']}) (e.g., 30): ") or 30)
        raw_inputs["bookings_last_hour"] = int(input("Bookings in last hour (e.g., 15): ") or 15)
        raw_inputs["views_last_hour"] = int(input("Views/searches in last hour (e.g., 100): ") or 100)

        print("\n--- 2b. Supply ---")
        raw_inputs["free_slots"] = int(input(f"Current free slots (max {raw_inputs['total_slots']}) (e.g., 10): ") or 10)
        raw_inputs["successful_bookings_30d"] = int(input("Successful bookings (last 30d) (e.g., 480): ") or 480)
        raw_inputs["accepted_bookings_30d"] = int(input("Accepted bookings (last 30d) (e.g., 500): ") or 500)

        print("\n--- 2c. Traffic ---")
        raw_inputs["avg_speed"] = float(input("Nearby avg speed (km/h) (e.g., 15): ") or 15)
        raw_inputs["free_flow_speed"] = float(input("Nearby free-flow speed (km/h) (e.g., 50): ") or 50)
        raw_inputs["vehicle_density"] = float(input("Vehicle density (veh/km) (e.g., 120): ") or 120)

        print("\n--- 2d. Adjacent Areas ---")
        raw_inputs["local_average_price"] = float(input("Local area average price (e.g., 80): ") or 80)
        
        adjacent_areas_list = []
        num_adj_areas = int(input("How many adjacent areas to add? (e.g., 2): ") or 2)
        
        for i in range(num_adj_areas):
            print(f"--- Area {i+1} ---")
            adj_congestion = float(input(f"  Area {i+1} congestion (0.0-1.0) (e.g., 0.4): ") or 0.4)
            adj_price = float(input(f"  Area {i+1} average price (e.g., 75): ") or 75)
            adjacent_areas_list.append({"congestion": adj_congestion, "price": adj_price})
                
        raw_inputs["adjacent_areas"] = adjacent_areas_list
        print(f"Adjacent area data: {raw_inputs['adjacent_areas']}")

        print("\n--- 2e. Weather ---")
        raw_inputs["rain_mm_last_30min"] = float(input("Rain (mm/hr) in last 30 min (e.g., 5): ") or 5)
        raw_inputs["is_waterlogged"] = (input("Is area waterlogged? (y/n) (e.g., n): ").lower() or 'n') == 'y'

        print("\n--- 2f. Time & Day ---")
        raw_inputs["current_hour"] = int(input("Current hour (0-23) (e.g., 18): ") or 18)
        
        peak_hours_str = input("Enter peak hours (comma-sep ranges, e.g., 8-10,17-20): ") or "8-10,17-20"
        peak_hours_list = []
        try:
            for part in peak_hours_str.split(','):
                if part.strip():
                    start, end = part.split('-')
                    peak_hours_list.append((int(start.strip()), int(end.strip())))
        except Exception:
            print(f"Invalid peak hours format '{peak_hours_str}', using default [(8, 10), (17, 20)]")
            peak_hours_list = [(8, 10), (17, 20)]
        raw_inputs["peak_hours"] = peak_hours_list
        print(f"Using peak hours: {raw_inputs['peak_hours']}")

        raw_inputs["is_holiday_or_event"] = (input("Is today a holiday or event? (y/n) (e.g., n): ").lower() or 'n') == 'y'

        print("\n--- 2g. Safety & Accessibility ---")
        raw_inputs["cctv_coverage_percent"] = float(input("CCTV coverage (0-100) (e.g., 80): ") or 80)
        raw_inputs["road_width_m"] = float(input("Road width (meters) (e.g., 4): ") or 4)

    except ValueError:
        print("Invalid data input. Please restart and enter valid numbers/text.")
        exit()

    
    
    print("\n--- 3. Pricing Parameters ---")
    try:
        # --- Get Booking and Vehicle Type ---
        booking_type = ""
        while booking_type not in ["regular", "premium", "prebooked"]:
            booking_type = input("Enter Booking Type (regular, premium, prebooked): ") or "regular"
            booking_type = booking_type.lower()
            if booking_type not in ["regular", "premium", "prebooked"]:
                print("Invalid type. Please enter 'regular', 'premium', or 'prebooked'.")

        vehicle_type = ""
        while vehicle_type not in ["car", "motorcycle"]:
            vehicle_type = input("Enter Vehicle Type (car, motorcycle): ") or "car"
            vehicle_type = vehicle_type.lower()
            if vehicle_type not in ["car", "motorcycle"]:
                print("Invalid type. Please enter 'car' or 'motorcycle'.")
        
        # --- Get Base Price from selection ---
        base_price = get_base_price(booking_type, vehicle_type)
        print(f"Selected Base Price for '{booking_type}' '{vehicle_type}': {base_price:.2f}")

        # Sensitivity coefficient (from PDF)
        alpha = float(input("Enter Alpha (sensitivity) [e.g., 0.5]: ") or 0.5) 
        print("    -> Controls how much the price changes. 0.5 is balanced. 0.8 is aggressive, 0.2 is conservative.")

        # City-wide average composite score (assumed value)
        delta_bar = float(input("Enter Delta-bar (city-wide avg score) [e.g., 0.55]: ") or 0.55) 
        print("    -> The 'normal' composite score for your city/zone. This is the baseline you are comparing against.")
        print("    -> You will need to calculate this average from all your areas over time.")

    except ValueError:
        print("Invalid pricing parameter. Please restart and enter numbers.")
        exit()

    #
    
    print("\n--- 4. Calculating... ---")

    # 1. Get AHP weights
    global_weights = get_global_weights()
    
    # 2. Calculate all 15 scores
    calculated_scores = calculate_all_scores(raw_inputs)
    
    print("\n--- Calculated Scores (0.0 - 1.0) ---")
    total_weight_check = 0.0
    for key, score in calculated_scores.items():
        weight = global_weights.get(key, 0.0)
        total_weight_check += weight
        print(f"{key:>10}: {score:6.4f} (Weight: {weight:6.4f})")
    print(f"--- (Total Weight: {total_weight_check:.4f}) ---") # Should be ~1.0

    # 3. Calculate final price
    dynamic_price, delta_i, multiplier = calculate_dynamic_price(
        base_price,
        calculated_scores,
        global_weights,
        alpha,
        delta_bar
    )
    
    print("\n--- Final Price Calculation ---")
    print(f"Booking Type:     {booking_type}")
    print(f"Vehicle Type:     {vehicle_type}")
    print(f"Base Price:       {base_price:.2f}")
    print(f"Composite Score (Delta_i): {delta_i:.4f}")
    print(f"City Avg Score  (Delta_bar): {delta_bar:.4f}")
    print(f"Sensitivity (Alpha):     {alpha:.2f}")
    print(f"Price Multiplier (M_i):    {multiplier:.4f}")
    print(f"-----------------------------------")
    print(f"Final Dynamic Price: {dynamic_price:.2f}")

