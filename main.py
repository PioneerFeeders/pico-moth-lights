print("main.py started – moth lights controller running")

from machine import Pin
import time

# ==============================
# CONFIG
# ==============================

CYCLE_LENGTH_DAYS = 24

# Cage offsets in *days* within the 24-day cycle:
CAGE_OFFSETS = {
    1: 0,
    2: 6,
    3: 12,
    4: 18,
}

# ====== CYCLE ANCHOR ======
# Re-anchor so:
#   TODAY (2025-12-16) = Cage #1 Day 5 (GREEN)
#
# Cage #1 offset = 0 => cage_day == global_day
# Day 5 (1-based) => cage_day = 4 (0-based) => global_day must be 4 today.
REFERENCE_YEAR  = 2025
REFERENCE_MONTH = 12
REFERENCE_DAY   = 16

REFERENCE_GLOBAL_DAY = 4


# ==============================
# PIN MAP (YOUR TRAFFIC LIGHT MODULES)
# ==============================

CAGES = {
    1: {  # Cage #1
        "R": Pin(2, Pin.OUT),
        "Y": Pin(3, Pin.OUT),
        "G": Pin(4, Pin.OUT),
    },
    2: {  # Cage #2
        "R": Pin(5, Pin.OUT),
        "Y": Pin(6, Pin.OUT),
        "G": Pin(7, Pin.OUT),
    },
    3: {  # Cage #3
        "R": Pin(28, Pin.OUT),
        "Y": Pin(27, Pin.OUT),
        "G": Pin(26, Pin.OUT),
    },
    4: {  # Cage #4
        "R": Pin(21, Pin.OUT),
        "Y": Pin(20, Pin.OUT),
        "G": Pin(19, Pin.OUT),
    },
}

LED_ON = 1   # change to 0 if your module is active-LOW
LED_OFF = 0


# ==============================
# HELPERS
# ==============================

def set_cage_color(cage_num, color):
    """Turn exactly one color on for the cage, others off."""
    cage = CAGES[cage_num]

    # Turn all off first
    for pin in cage.values():
        pin.value(LED_OFF)

    if color == "red":
        cage["R"].value(LED_ON)
    elif color == "yellow":
        cage["Y"].value(LED_ON)
    elif color == "green":
        cage["G"].value(LED_ON)
    else:
        print("Unknown color for cage", cage_num, ":", color)


def color_for_cage_day(cage_day):
    """
    cage_day: 0–23 for that cage's own 24-day cycle.

    0–5   -> GREEN  (Days 1–6)
    6–19  -> YELLOW (Days 7–20)
    20–23 -> RED    (Days 21–24)
    """
    if 0 <= cage_day <= 5:
        return "green"
    elif 6 <= cage_day <= 19:
        return "yellow"
    else:
        return "red"


def days_since_reference():
    """Number of full calendar days since the reference date."""
    now = time.localtime()
    now_secs = time.mktime(now)

    ref_tuple = (REFERENCE_YEAR, REFERENCE_MONTH, REFERENCE_DAY, 0, 0, 0, 0, 0)
    ref_secs = time.mktime(ref_tuple)

    return int((now_secs - ref_secs) // (24 * 60 * 60))


def current_global_day():
    """Calculate current global day (0–23) in the 24-day cycle."""
    d = days_since_reference()
    return (REFERENCE_GLOBAL_DAY + d) % CYCLE_LENGTH_DAYS


def update_lights_for_global_day(global_day):
    """For each cage, compute its local day and set its solid color."""
    print("Using global_day:", global_day)

    for cage_num, offset in CAGE_OFFSETS.items():
        cage_day = (global_day - offset) % CYCLE_LENGTH_DAYS
        color = color_for_cage_day(cage_day)
        set_cage_color(cage_num, color)
        print(f"Cage {cage_num}: cage_day={cage_day} (Day {cage_day+1}), color={color}")


# ==============================
# MAIN LOOP
# ==============================

# Start with all LEDs OFF
for c in CAGES:
    for pin in CAGES[c].values():
        pin.value(LED_OFF)

last_global_day = None

while True:
    try:
        gday = current_global_day()

        # Only update when the logical day changes
        if gday != last_global_day:
            print("=== NEW LOGICAL DAY:", gday, "===")
            update_lights_for_global_day(gday)
            last_global_day = gday

        time.sleep(30)

    except Exception as e:
        print("Error in main loop:", e)
        time.sleep(5)
