"""
MRT network data and commute time calculations for Taipei apartment search.

This module provides:
- Pre-calculated MRT travel times between stations
- Station coordinate lookup
- Commute time calculations (MRT and bike)
"""

from math import radians, cos, sin, sqrt, atan2
import re
from config import get_reference_coords, load_config

# Walking pace: 80m/min (about 4.8 km/h)
WALK_PACE_M_PER_MIN = 80

# MRT speed: ~2 min per station on average
MRT_MIN_PER_STATION = 2

# Transfer time at interchange stations
TRANSFER_TIME_MIN = 5

# Bike speed: ~15 km/h average in urban Taipei
# Street distance factor: 1.3x haversine (accounting for road layout)
BIKE_SPEED_KMH = 15
STREET_FACTOR = 1.3

# Walking time from reference station to reference point (configured in setup)
# Default assumes 4 min walk from station - update via config
WALK_FROM_REF_STATION_MIN = 4


def get_reference_station() -> str:
    """Get the reference MRT station from config."""
    config = load_config()
    return config["reference_location"].get("station", "台北車站")


# MRT Station coordinates (lat, lon)
# Covers major stations in Taipei
MRT_STATION_COORDS = {
    # Brown Line (Wenhu)
    "動物園": (24.9983, 121.5805),
    "木柵": (24.9983, 121.5730),
    "萬芳社區": (24.9991, 121.5704),
    "萬芳醫院": (25.0015, 121.5586),
    "辛亥": (25.0074, 121.5420),
    "麟光": (25.0157, 121.5505),
    "六張犁": (25.0235, 121.5536),
    "科技大樓": (25.0260, 121.5432),
    "大安": (25.0332, 121.5435),
    "忠孝復興": (25.0416, 121.5439),
    "忠孝新生": (25.0420, 121.5330),
    "南京復興": (25.0520, 121.5443),
    "中山國中": (25.0606, 121.5440),
    "松山機場": (25.0630, 121.5510),
    "大直": (25.0790, 121.5460),
    "劍南路": (25.0845, 121.5550),
    "西湖": (25.0820, 121.5670),
    "港墘": (25.0800, 121.5740),
    "文德": (25.0785, 121.5830),
    "內湖": (25.0840, 121.5940),
    "大湖公園": (25.0835, 121.6035),
    "葫洲": (25.0720, 121.6110),
    "東湖": (25.0670, 121.6120),
    "南港軟體園區": (25.0600, 121.6160),
    "南港展覽館": (25.0555, 121.6180),

    # Orange Line (Zhonghe-Xinlu)
    "南勢角": (24.9905, 121.5085),
    "景安": (24.9938, 121.5050),
    "永安市場": (25.0007, 121.5102),
    "頂溪": (25.0130, 121.5150),
    "古亭": (25.0263, 121.5227),
    "東門": (25.0340, 121.5290),
    "松江南京": (25.0520, 121.5328),
    "行天宮": (25.0597, 121.5333),
    "中山國小": (25.0630, 121.5265),
    "民權西路": (25.0635, 121.5190),
    "大橋頭": (25.0630, 121.5120),
    "台北橋": (25.0630, 121.5000),
    "菜寮": (25.0595, 121.4915),
    "三重": (25.0560, 121.4850),
    "先嗇宮": (25.0450, 121.4705),
    "頭前庄": (25.0390, 121.4615),
    "新莊": (25.0355, 121.4520),
    "輔大": (25.0335, 121.4355),
    "丹鳳": (25.0370, 121.4205),
    "迴龍": (25.0385, 121.4105),

    # Blue Line (Bannan)
    "頂埔": (24.9600, 121.4200),
    "永寧": (24.9665, 121.4360),
    "土城": (24.9730, 121.4435),
    "海山": (24.9850, 121.4500),
    "亞東醫院": (24.9980, 121.4525),
    "府中": (25.0080, 121.4590),
    "板橋": (25.0145, 121.4635),
    "新埔": (25.0240, 121.4680),
    "江子翠": (25.0305, 121.4740),
    "龍山寺": (25.0350, 121.4995),
    "西門": (25.0420, 121.5080),
    "台北車站": (25.0478, 121.5170),
    "善導寺": (25.0445, 121.5257),
    "忠孝敦化": (25.0416, 121.5513),
    "國父紀念館": (25.0410, 121.5580),
    "市政府": (25.0408, 121.5670),
    "永春": (25.0408, 121.5760),
    "後山埤": (25.0445, 121.5820),
    "昆陽": (25.0500, 121.5920),
    "南港": (25.0520, 121.6070),

    # Green Line (Songshan-Xindian)
    "松山": (25.0497, 121.5779),
    "南京三民": (25.0516, 121.5547),
    "台北小巨蛋": (25.0510, 121.5508),
    "中山": (25.0528, 121.5207),
    "北門": (25.0490, 121.5110),
    "小南門": (25.0340, 121.5100),
    "中正紀念堂": (25.0330, 121.5180),
    "台大醫院": (25.0412, 121.5170),
    "公館": (25.0150, 121.5340),
    "萬隆": (25.0017, 121.5350),
    "景美": (24.9935, 121.5405),
    "大坪林": (24.9830, 121.5415),
    "七張": (24.9755, 121.5430),
    "新店區公所": (24.9670, 121.5410),
    "新店": (24.9580, 121.5380),

    # Red Line (Tamsui-Xinyi)
    "象山": (25.0269, 121.5687),
    "台北101/世貿": (25.0330, 121.5654),
    "信義安和": (25.0332, 121.5531),
    "大安森林公園": (25.0330, 121.5350),
    "雙連": (25.0580, 121.5210),
    "圓山": (25.0715, 121.5200),
    "劍潭": (25.0845, 121.5250),
    "士林": (25.0935, 121.5260),
    "芝山": (25.1030, 121.5230),
    "明德": (25.1100, 121.5195),
    "石牌": (25.1170, 121.5150),
    "唭哩岸": (25.1240, 121.5080),
    "奇岩": (25.1325, 121.5030),
    "北投": (25.1375, 121.4990),
    "新北投": (25.1370, 121.5035),
    "復興崗": (25.1380, 121.4930),
    "忠義": (25.1320, 121.4730),
    "關渡": (25.1255, 121.4680),
    "竹圍": (25.1365, 121.4590),
    "紅樹林": (25.1540, 121.4565),
    "淡水": (25.1690, 121.4490),
}


def build_time_table(reference_station: str) -> dict:
    """
    Build a lookup table of MRT travel times to the reference station.

    This is a simplified calculation based on station distances.
    For more accurate times, you could manually define routes.

    Returns:
        Dict mapping station names to (minutes, stops, transfers, route_description)
    """
    # Get reference station coords
    if reference_station not in MRT_STATION_COORDS:
        return {}

    ref_coords = MRT_STATION_COORDS[reference_station]
    time_table = {}

    for station, coords in MRT_STATION_COORDS.items():
        if station == reference_station:
            time_table[station] = (0, 0, 0, "At reference station")
            continue

        # Estimate travel time based on distance
        # This is a rough approximation - actual MRT routing would be more complex
        distance_km = haversine_distance(coords[0], coords[1], ref_coords[0], ref_coords[1])

        # Rough estimate: 25 km/h average including stops
        minutes = int(distance_km / 25 * 60)

        # Estimate stops (roughly 1 stop per 800m)
        stops = max(1, int(distance_km / 0.8))

        # Assume 0 transfers for simplicity (actual routing would check lines)
        transfers = 0
        route = "Estimated"

        time_table[station] = (minutes, stops, transfers, route)

    return time_table


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in km."""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371 * 2 * atan2(sqrt(a), sqrt(1 - a))


def parse_mrt_info(mrt_text: str) -> tuple:
    """
    Parse MRT station info from listing text.
    Returns (station_name, distance_meters).

    Examples:
    - "市政府站 (77m)" -> ("市政府", 77)
    - "距後山埤站 (266m)" -> ("後山埤", 266)
    """
    if not mrt_text:
        return None, None

    cleaned = re.sub(r'^(距|近|本房屋近|捷運)', '', mrt_text.strip())

    station_match = re.search(r'([\u4e00-\u9fff]+)(?:站|捷運站)?', cleaned)
    station_name = station_match.group(1) if station_match else None

    if station_name:
        for suffix in ['火車站', '捷運站', '站']:
            if station_name.endswith(suffix):
                station_name = station_name[:-len(suffix)]
                break

    distance_match = re.search(r'\((\d+)\s*m?\)', mrt_text)
    distance_m = int(distance_match.group(1)) if distance_match else None

    return station_name, distance_m


def calculate_mrt_time(station_name: str, distance_to_station_m: int = None) -> dict:
    """
    Calculate MRT commute time from a station to the reference location.

    Args:
        station_name: MRT station name (Chinese)
        distance_to_station_m: Distance from apartment to station in meters

    Returns:
        dict with: mrt_time_min, stops, transfers, route, walk_to_station_min
    """
    if not station_name:
        return None

    # Get reference station
    reference_station = get_reference_station()
    time_table = build_time_table(reference_station)

    # Look up station
    station_data = time_table.get(station_name)

    if not station_data:
        for suffix in ['站', '捷運站', '火車站']:
            if station_name.endswith(suffix):
                station_data = time_table.get(station_name[:-len(suffix)])
                if station_data:
                    break

    if not station_data:
        return None

    mrt_time, stops, transfers, route = station_data

    walk_to_station_min = 0
    if distance_to_station_m:
        walk_to_station_min = distance_to_station_m / WALK_PACE_M_PER_MIN

    total_mrt_time = walk_to_station_min + mrt_time + WALK_FROM_REF_STATION_MIN

    return {
        "mrt_time_min": round(total_mrt_time, 1),
        "mrt_ride_min": mrt_time,
        "walk_to_station_min": round(walk_to_station_min, 1),
        "stops": stops,
        "transfers": transfers,
        "route": route,
    }


def calculate_bike_time(lat: float = None, lon: float = None,
                        station_name: str = None) -> dict:
    """
    Calculate bike time from apartment location to reference location.

    Uses either direct coordinates or station coordinates as fallback.
    """
    ref_coords = get_reference_coords()

    if lat and lon:
        apt_coords = (lat, lon)
    elif station_name and station_name in MRT_STATION_COORDS:
        apt_coords = MRT_STATION_COORDS[station_name]
    else:
        return None

    distance_km = haversine_distance(
        apt_coords[0], apt_coords[1],
        ref_coords[0], ref_coords[1]
    )

    street_distance_km = distance_km * STREET_FACTOR
    bike_time_min = (street_distance_km / BIKE_SPEED_KMH) * 60

    return {
        "bike_time_min": round(bike_time_min, 1),
        "distance_km": round(distance_km, 2),
        "street_distance_km": round(street_distance_km, 2),
    }


def calculate_commute_time(mrt_text: str, apt_lat: float = None, apt_lon: float = None) -> dict:
    """
    Calculate best commute time to reference location.

    Args:
        mrt_text: Raw MRT station text from listing (e.g., "市政府站 (77m)")
        apt_lat: Apartment latitude (optional, for bike calculation)
        apt_lon: Apartment longitude (optional, for bike calculation)

    Returns:
        dict with:
        - commute_time_min: Best commute time (min of MRT and bike)
        - transport_mode: "MRT" or "Bike"
        - mrt_details: MRT route info
        - bike_details: Bike route info
        - station_name: Parsed station name
        - distance_to_station_m: Parsed distance to station
    """
    station_name, distance_to_station_m = parse_mrt_info(mrt_text)

    mrt_result = calculate_mrt_time(station_name, distance_to_station_m)
    bike_result = calculate_bike_time(apt_lat, apt_lon, station_name)

    mrt_time = mrt_result["mrt_time_min"] if mrt_result else float('inf')
    bike_time = bike_result["bike_time_min"] if bike_result else float('inf')

    if mrt_time == float('inf') and bike_time == float('inf'):
        return {
            "commute_time_min": None,
            "transport_mode": None,
            "mrt_details": None,
            "bike_details": None,
            "station_name": station_name,
            "distance_to_station_m": distance_to_station_m,
        }

    if mrt_time <= bike_time:
        best_time = mrt_time
        best_mode = "MRT"
    else:
        best_time = bike_time
        best_mode = "Bike"

    return {
        "commute_time_min": round(best_time, 1),
        "transport_mode": best_mode,
        "mrt_details": mrt_result,
        "bike_details": bike_result,
        "station_name": station_name,
        "distance_to_station_m": distance_to_station_m,
    }


def get_station_coords(station_name: str) -> tuple:
    """Get coordinates for a station by name."""
    if station_name in MRT_STATION_COORDS:
        return MRT_STATION_COORDS[station_name]

    for suffix in ['站', '捷運站', '火車站']:
        if station_name.endswith(suffix):
            clean_name = station_name[:-len(suffix)]
            if clean_name in MRT_STATION_COORDS:
                return MRT_STATION_COORDS[clean_name]

    return None


if __name__ == "__main__":
    # Test the module
    test_cases = [
        "市政府站 (77m)",
        "後山埤站 (266m)",
        "象山站 (591m)",
        "忠孝復興站 (100m)",
        "大安站 (200m)",
    ]

    print("Testing commute time calculations:\n")
    for mrt_text in test_cases:
        result = calculate_commute_time(mrt_text)
        print(f"Input: {mrt_text}")
        print(f"  Station: {result['station_name']}")
        print(f"  Distance to station: {result['distance_to_station_m']}m")
        if result['commute_time_min']:
            print(f"  Commute time: {result['commute_time_min']} min ({result['transport_mode']})")
            if result['mrt_details']:
                mrt = result['mrt_details']
                print(f"    MRT: {mrt['mrt_time_min']} min ({mrt['stops']} stops)")
            if result['bike_details']:
                bike = result['bike_details']
                print(f"    Bike: {bike['bike_time_min']} min ({bike['distance_km']} km)")
        else:
            print(f"  No route found")
        print()
