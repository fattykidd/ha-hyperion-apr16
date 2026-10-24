"""Volume conversion mapping for AudioControl Hyperion APR-16."""

# Lower erratic zone lookup table (0% to 19%)
LOWER_VOLUME_MAP = {
    0: -127.5,
    1: -121.5,
    2: -115.0,
    3: -108.5,
    4: -102.5,
    5: -96.0,
    6: -89.5,
    7: -83.5,
    8: -77.0,
    9: -70.5,
    10: -64.0,
    11: -63.5,
    12: -63.0,
    13: -62.0,
    14: -61.5,
    15: -60.5,
    16: -60.0,
    17: -59.0,  # estimated intermediate step
    18: -58.0,  # estimated intermediate step
    19: -57.5,  # estimated intermediate step
}

def percent_to_db(percent: float) -> float:
    """Convert Home Assistant percentage (0-100) to Hyperion dB scale."""
    p_clamped = max(0.0, min(100.0, percent))
    
    # 0% to 19%: Use the explicit lower lookup table
    if p_clamped < 20:
        floor_p = int(p_clamped)
        return LOWER_VOLUME_MAP.get(floor_p, -127.5)
        
    # 100%: Exactly 0 dB
    if p_clamped >= 100.0:
        return 0.0
        
    # 20% to 95%: Clean linear slope (-57.0 dB at 20% up to -4.0 dB at 95%)
    # Formula: -57.0 + ((percent - 20) / (95 - 20)) * (-4.0 - (-57.0))
    if p_clamped <= 95.0:
        return -57.0 + ((p_clamped - 20.0) / 75.0) * 53.0
        
    # 95% to 100%: Final hop from -4.0 dB to 0.0 dB
    return -4.0 + ((p_clamped - 95.0) / 5.0) * 4.0

def db_to_percent(db: float) -> float:
    """Convert Hyperion dB scale back to Home Assistant percentage (0-100)."""
    db_clamped = max(-127.5, min(0.0, db))
    
    if db_clamped >= 0.0:
        return 100.0
    if db_clamped <= -127.5:
        return 0.0
        
    # If in the upper clean range (-57.0 dB to 0.0 dB)
    if db_clamped >= -57.0:
        if db_clamped >= -4.0:
            # 95% to 100% range
            return 95.0 + ((db_clamped - (-4.0)) / 4.0) * 5.0
        else:
            # 20% to 95% range
            return 20.0 + ((db_clamped - (-57.0)) / 53.0) * 75.0
            
    # Otherwise, find the closest match in the lower erratic table
    closest_p = 0
    min_diff = float("inf")
    for p, val in LOWER_VOLUME_MAP.items():
        diff = abs(val - db_clamped)
        if diff < min_diff:
            min_diff = diff
            closest_p = p
            
    return float(closest_p)