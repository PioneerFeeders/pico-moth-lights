from machine import Pin
import time

# ==============================
# CONFIG
# ==============================

# How many seconds in one "logical day" of the cycle.
# For real-world use, set to: 86400  (24 * 60 * 60)
# For testing, you can use something small like 10.
DAY_SECONDS = 10   # <-- CHANGE TO 86400 WHEN YOU'RE READY

CYCLE_LENGTH_DAYS = 24

# We use one global 24-day cycle.
# Each cage has a 24-day pattern (G/Y/R) shifted in time.
#
# Offsets in *days* for when each cage starts its cycle:
#   Cage 1: Day 0   -> green days 1–6 correspond to global days 0–5
#   Cage 2: Day 6   -> first green at global day 6
#   Cage 3: Day 12  -> first green at global day 12
#   Cage 4: Day 18  -> first green at global day 18
CAGE_OFFSETS = {
    1: 0,
    2: 6,
    3: 12,
    4: 18,
}

# We also allow shifting the entire global cycle at boot.
# elapsed_days = 0 at boot, so:
#   START_DAY_OFFSET = 0   -> global_day = 0  at boot
#   START_DAY_OFFSET = 12  -> global_day = 12 at boot
#
# You said: "Cage #3 starting today as the 1st green day".
# Cage 3's first green day is at global_day = 12, so:
START_DAY_OFFSET = 12

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
# HELPER FUNCTIONS
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
        # Unknown color, leave off
        print("Unknown color for cage", cage_num, ":", color)


def color_for_cage_day(cage_day):
    """
    cage_day: 0–23 for that cage's own 24-day cycle.

    Your spec (1-based days):
      Days 1–6   -> GREEN
      Days 7–20  -> YELLOW
      Days 21–24 -> RED

    Converted to 0-based indexes:
      0–5   -> GREEN
      6–19  -> YELLOW
      20–23 -> RED
    """
    if 0 <= cage_day <= 5:
        return "green"
    elif 6 <= cage_day <= 19:
        return "yellow"
    else:  # 20–23
        return "red"


def update_lights(elapsed_seconds):
    """
    Compute current global day in the 24-day cycle,
    then compute each cage's position and set its color.
    """
    # Whole days since Pico boot (or since script started)
    elapsed_days = int(elapsed_seconds // DAY_SECONDS)

    # Global cycle day 0–23 (shifted by START_DAY_OFFSET)
    global_day = (elapsed_days + START_DAY_OFFSET) % CYCLE_LENGTH_DAYS

    print("elapsed_days:", elapsed_days, "global_day:", global_day)

    # For each cage, shift by its offset to get that cage's local day
    for cage_num, offset in CAGE_OFFSETS.items():
        cage_day = (global_day - offset) % CYCLE_LENGTH_DAYS
        color = color_for_cage_day(cage_day)
        set_cage_color(cage_num, color)
        print(f"Cage {cage_num}: cage_day={cage_day}, color={color}")


# ==============================
# MAIN LOOP
# ==============================

# Start with all LEDs OFF
for c in CAGES:
    for pin in CAGES[c].values():
        pin.value(LED_OFF)

start_time = time.time()
last_day_seen = -1  # so we only update on new "days"

while True:
    now = time.time()
    elapsed = now - start_time

    current_day = int(elapsed // DAY_SECONDS)

    # Only recalculate when we hit a new logical "day"
    if current_day != last_day_seen:
        last_day_seen = current_day
        print("=== NEW LOGICAL DAY:", current_day, "===")
        update_lights(elapsed)

    time.sleep(0.5)
