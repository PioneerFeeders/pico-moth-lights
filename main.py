print("main.py started – moth lights controller running")

from machine import Pin
import time

# ==============================
# CONFIG
# ==============================

CYCLE_LENGTH_DAYS = 24

# Cage offsets in *days* within the 24-day cycle:
#   Cage 1: offset 0   -> green days 1–6 at global days 0–5
#   Cage 2: offset 6   -> first green at global day 6
#   Cage 3: offset 12  -> first green at global day 12
#   Cage 4: offset 18  -> first green at global day 18
CAGE_OFFSETS = {
    1: 0,
    2: 6,
    3: 12,
    4: 18,
}

# ====== CYCLE ANCHOR ======
# We anchor the 24-day cycle to a real calendar date.
REFERENCE_YEAR  = 2025
REFERENCE_MONTH = 12
REFERENCE_DAY   = 3    # <-- set this to today's date on the day you flash this

# You chose this so that cage 3 is Day 2 green on that reference date.
REFERENCE_GLOBAL_DAY = 13

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
    """Turn exactly one color ON for the cage, others OFF."""
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


def set_cage_off(cage_num):
    """Turn all LEDs off for a cage."""
    cage = CAGES[cage_num]
    for pin in cage.values():
        pin.value(LED_OFF)


def color_for_cage_day(cage_day):
    """
    cage_day: 0–23 for that cage's own 24-day cycle.

      Days 1–6   -> GREEN
      Days 7–20  -> YELLOW
      Days 21–24 -> RED

    0-based:
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


def blink_count_for_cage_day(cage_day):
    """
    Return how many 1s-on / 1s-off blinks per cycle
    this cage should do on this cage_day (0–23).
    Days 21–24 (index 20–23) are solid red, no blink.
    """
    blink_table = [
        1,  # Day 1
        2,  # Day 2
        3,  # Day 3
        4,  # Day 4
        4,  # Day 5
        4,  # Day 6
        6,  # Day 7
        6,  # Day 8
        6,  # Day 9
        8,  # Day 10
        8,  # Day 11
        8,  # Day 12
        8,  # Day 13
        8,  # Day 14
        6,  # Day 15
        6,  # Day 16
        4,  # Day 17
        4,  # Day 18
        4,  # Day 19
        4,  # Day 20
        0,  # Day 21  -> solid red
        0,  # Day 22  -> solid red
        0,  # Day 23  -> solid red
        0,  # Day 24  -> solid red
    ]
    return blink_table[cage_day]


def days_since_reference():
    """
    Number of calendar days since the reference date.
    Uses the Pico's RTC (time.localtime()).
    """
    now = time.localtime()  # (year, month, mday, hour, min, sec, wday, yday)
    now_secs = time.mktime(now)

    ref_tuple = (REFERENCE_YEAR, REFERENCE_MONTH, REFERENCE_DAY,
                 0, 0, 0, 0, 0)
    ref_secs = time.mktime(ref_tuple)

    return int((now_secs - ref_secs) // (24 * 60 * 60))


def current_global_day():
    """
    Calculate which 0–23 'global day' we are in the 24-day cycle,
    based purely on calendar date. This will be the same even after reboots.
    """
    d = days_since_reference()
    global_day = (REFERENCE_GLOBAL_DAY + d) % CYCLE_LENGTH_DAYS
    return global_day


def compute_cage_runtime_for_global_day(global_day):
    """
    For this global_day, compute per-cage:
      - color
      - blink count for the day
      - initial blinking state
    Returns a dict cage_num -> runtime_state.
    """
    cage_runtime = {}

    print("Using global_day:", global_day)

    for cage_num, offset in CAGE_OFFSETS.items():
        cage_day = (global_day - offset) % CYCLE_LENGTH_DAYS
        color = color_for_cage_day(cage_day)
        blinks = blink_count_for_cage_day(cage_day)

        if blinks == 0:
            phase = "solid_only"   # always on, no blinking
        else:
            # Start in the 10-second solid phase between blink cycles
            phase = "solid_gap"

        cage_runtime[cage_num] = {
            "color": color,
            "blinks": blinks,
            "cage_day": cage_day,
            "phase": phase,     # "solid_only", "solid_gap", "blink_on", "blink_off"
            "timer": 0,         # seconds within current phase
            "blink_index": 0,   # completed blinks in this cycle
        }

        print(f"Cage {cage_num}: cage_day={cage_day}, color={color}, blinks={blinks}")

    return cage_runtime


def apply_blink_logic_one_tick(cage_runtime):
    """
    Advance blinking by 1 second for all cages.

    For cages with blinks > 0:
      - phase solid_gap: solid ON for 10 seconds, then start blink sequence
      - phase blink_on:  LED ON for 1 second, then blink_off
      - phase blink_off: LED OFF for 1 second, increment blink_index
        - if blink_index reaches blinks -> back to solid_gap for 10s
        - otherwise -> another blink_on

    For cages with blinks == 0:
      - always solid ON, no blinking
    """
    for cage_num, state in cage_runtime.items():
        color = state["color"]
        blinks = state["blinks"]
        phase = state["phase"]

        if blinks == 0:
            # Solid all day, no blink
            set_cage_color(cage_num, color)
            continue

        # There IS a blink pattern for this cage/day
        if phase == "solid_gap":
            # Solid ON during gap
            set_cage_color(cage_num, color)
            state["timer"] += 1
            if state["timer"] >= 10:
                # After 10s solid, start blinking cycle
                state["phase"] = "blink_on"
                state["timer"] = 0
                state["blink_index"] = 0

        elif phase == "blink_on":
            # 1 second ON
            set_cage_color(cage_num, color)
            state["timer"] += 1
            if state["timer"] >= 1:
                state["phase"] = "blink_off"
                state["timer"] = 0

        elif phase == "blink_off":
            # 1 second OFF
            set_cage_off(cage_num)
            state["timer"] += 1
            if state["timer"] >= 1:
                state["blink_index"] += 1
                state["timer"] = 0
                if state["blink_index"] >= blinks:
                    # Finished all blinks in this cycle -> 10s solid again
                    state["phase"] = "solid_gap"
                    state["blink_index"] = 0
                else:
                    # More blinks to do in this cycle
                    state["phase"] = "blink_on"


# ==============================
# MAIN LOOP
# ==============================

# Start with all LEDs OFF
for c in CAGES:
    for pin in CAGES[c].values():
        pin.value(LED_OFF)

last_global_day = None
cage_runtime = None

while True:
    try:
        gday = current_global_day()

        # If the logical day changed, recompute colors + blink counts
        if gday != last_global_day or cage_runtime is None:
            print("=== NEW LOGICAL DAY:", gday, "===")
            last_global_day = gday
            cage_runtime = compute_cage_runtime_for_global_day(gday)

        # Advance blink state by 1 second for all cages
        apply_blink_logic_one_tick(cage_runtime)

        # Tick = 1 second (we want 1s ON / 1s OFF)
        time.sleep(1)

    except Exception as e:
        print("Error in main loop:", e)
        time.sleep(5)
