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
#
# Pick a calendar date and decide what "global day" it should be.
# Then the code calculates every other day from that.
#
# You said: "Today should be Day 2 green cage #3."
# For cage 3:
#   green days are cage_day 0–5
#   Day 2 green  -> cage_day = 1
# cage_day = (global_day - 12) % 24
# So we want: (global_day - 12) % 24 = 1  -> global_day = 13
#
# If TODAY’S calendar date should be that global_day=13, then:
REFERENCE_YEAR  = 2025
REFERENCE_MONTH = 12
REFERENCE_DAY   = 3    # <-- set this to today's date on the day you flash this

REFERENCE_GLOBAL_DAY = 13  # so that cage 3 is Day 2 green on that date


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


def days_since_reference():
    """
    Number of calendar days since the reference date.
    Uses the Pico's RTC (time.localtime()).
    """
    # current local time
    now = time.localtime()  # (year, month, mday, hour, min, sec, wday, yday)
    now_secs = time.mktime(now)

    # reference date at midnight
    ref_tuple = (REFERENCE_YEAR, REFERENCE_MONTH, REFERENCE_DAY,
                 0, 0, 0, 0, 0)
    ref_secs = time.mktime(ref_tuple)

    # whole days between reference date and now
    return int((now_secs - ref_secs) // (24 * 60 * 60))


def current_global_day():
    """
    Calculate which 0–23 'global day' we are in the 24-day cycle,
    based purely on calendar date. This will be the same even after reboots.
    """
    d = days_since_reference()
    # The reference date is defined to be REFERENCE_GLOBAL_DAY in the cycle,
    # so we just shift forward by d days.
    global_day = (REFERENCE_GLOBAL_DAY + d) % CYCLE_LENGTH_DAYS
    return global_day


def update_lights_for_global_day(global_day):
    """
    For each cage, compute its local day and set its color.
    """
    print("Using global_day:", global_day)

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

last_global_day = None

while True:
    try:
        gday = current_global_day()

        # Only update when the logical day changes
        if gday != last_global_day:
            print("=== NEW LOGICAL DAY:", gday, "===")
            update_lights_for_global_day(gday)
            last_global_day = gday

        # We don't need to check super often; once every 30–60 seconds is fine.
        # The "day change" will happen a little after local midnight.
        time.sleep(30)

    except Exception as e:
        # Don't let a transient error kill the loop
        print("Error in main loop:", e)
        time.sleep(5)
