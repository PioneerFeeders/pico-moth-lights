print("main.py started – moth lights controller running")

import time
import network
import ntptime
from machine import Pin

# ==============================
# WIFI + TIME (NTP)
# ==============================

WIFI_SSID = "TheHive"
WIFI_PASSWORD = "H0N3YB33"

def wifi_connect(timeout_s=20):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        t0 = time.time()
        while not wlan.isconnected() and (time.time() - t0) < timeout_s:
            time.sleep(0.5)
    return wlan.isconnected()

def us_dst_is_active(year, month, mday, wday, hour):
    """
    US DST rules (post-2007): starts 2nd Sunday in March, ends 1st Sunday in November.
    wday: Monday=0 ... Sunday=6
    """
    # Jan, Feb, Dec: no DST
    if month < 3 or month > 11:
        return False
    # Apr-Oct: DST
    if 3 < month < 11:
        return True

    # Helper: day-of-month of the nth Sunday in a month
    def nth_sunday(n, month_days_in_first_week_wday):
        # month_days_in_first_week_wday = wday of the 1st of the month (Mon=0..Sun=6)
        # Sunday index is 6
        first_sunday = 1 + ((6 - month_days_in_first_week_wday) % 7)
        return first_sunday + (n - 1) * 7

    # Compute wday of the 1st of this month:
    # We can get it by backing out from current date.
    # wday_current corresponds to (year, month, mday).
    wday_first = (wday - ((mday - 1) % 7)) % 7

    if month == 3:
        start_day = nth_sunday(2, wday_first)  # 2nd Sunday in March
        # DST starts at 2:00 local time on that Sunday
        if mday > start_day:
            return True
        if mday < start_day:
            return False
        return hour >= 2

    if month == 11:
        end_day = nth_sunday(1, wday_first)  # 1st Sunday in November
        # DST ends at 2:00 local time on that Sunday (clocks go back)
        if mday < end_day:
            return True
        if mday > end_day:
            return False
        return hour < 2

    return False

def detroit_utc_offset_hours(utc_tuple):
    """
    ntptime sets RTC to UTC. Convert UTC -> America/Detroit local offset (EST/EDT).
    utc_tuple: time.localtime() after ntptime.settime() (UTC)
    """
    year, month, mday, hour, minute, sec, wday, yday = utc_tuple
    # Detroit is UTC-5 normally. During DST it's UTC-4.
    # DST determination should be based on *local* time, so estimate local hour with standard offset first.
    est_hour = (hour - 5) % 24
    # For DST check we need local wday/mday consistency; using the UTC date with shifted hour is close enough
    # for day-based scheduling; edge cases around the transition hour are handled by hour logic above.
    dst = us_dst_is_active(year, month, mday, wday, est_hour)
    return -4 if dst else -5

def sync_time_ntp():
    """
    Sets Pico RTC to UTC via NTP. Returns True/False.
    """
    try:
        ntptime.settime()
        return True
    except Exception as e:
        print("NTP sync failed:", e)
        return False

def localtime_detroit():
    """
    Return Detroit-local time tuple using UTC RTC + computed offset.
    """
    utc = time.localtime()  # RTC is UTC after ntptime.settime()
    offset_h = detroit_utc_offset_hours(utc)
    local_secs = time.time() + offset_h * 3600
    return time.localtime(local_secs)


# ==============================
# CONFIG
# ==============================

CYCLE_LENGTH_DAYS = 24

CAGE_OFFSETS = {
    1: 0,
    2: 6,
    3: 12,
    4: 18,
}

# ====== CYCLE ANCHOR ======
# Today (Detroit local date) should be Cage #1 Day 5 (GREEN)
REFERENCE_YEAR  = 2025
REFERENCE_MONTH = 12
REFERENCE_DAY   = 16
REFERENCE_GLOBAL_DAY = 4  # Day 5 (1-based) => 4 (0-based)

# ==============================
# PIN MAP
# ==============================

CAGES = {
    1: {"R": Pin(2, Pin.OUT),  "Y": Pin(3, Pin.OUT),  "G": Pin(4, Pin.OUT)},
    2: {"R": Pin(5, Pin.OUT),  "Y": Pin(6, Pin.OUT),  "G": Pin(7, Pin.OUT)},
    3: {"R": Pin(28, Pin.OUT), "Y": Pin(27, Pin.OUT), "G": Pin(26, Pin.OUT)},
    4: {"R": Pin(21, Pin.OUT), "Y": Pin(20, Pin.OUT), "G": Pin(19, Pin.OUT)},
}

LED_ON = 1
LED_OFF = 0

# ==============================
# HELPERS
# ==============================

def set_cage_color(cage_num, color):
    cage = CAGES[cage_num]
    for pin in cage.values():
        pin.value(LED_OFF)

    if color == "red":
        cage["R"].value(LED_ON)
    elif color == "yellow":
        cage["Y"].value(LED_ON)
    elif color == "green":
        cage["G"].value(LED_ON)

def color_for_cage_day(cage_day):
    if 0 <= cage_day <= 5:
        return "green"
    elif 6 <= cage_day <= 19:
        return "yellow"
    else:
        return "red"

def days_since_reference():
    """
    Whole local calendar days since reference date, using Detroit local date.
    """
    now = localtime_detroit()  # (year, month, mday, hour, min, sec, wday, yday)
    now_midnight = (now[0], now[1], now[2], 0, 0, 0, 0, 0)
    now_secs = time.mktime(now_midnight)

    ref_midnight = (REFERENCE_YEAR, REFERENCE_MONTH, REFERENCE_DAY, 0, 0, 0, 0, 0)
    ref_secs = time.mktime(ref_midnight)

    return int((now_secs - ref_secs) // (24 * 60 * 60))

def current_global_day():
    d = days_since_reference()
    return (REFERENCE_GLOBAL_DAY + d) % CYCLE_LENGTH_DAYS

def update_lights_for_global_day(global_day):
    print("Using global_day:", global_day)
    for cage_num, offset in CAGE_OFFSETS.items():
        cage_day = (global_day - offset) % CYCLE_LENGTH_DAYS
        color = color_for_cage_day(cage_day)
        set_cage_color(cage_num, color)
        print(f"Cage {cage_num}: cage_day={cage_day} (Day {cage_day+1}), color={color}")

# ==============================
# BOOT: CONNECT + NTP
# ==============================

ok_wifi = wifi_connect()
print("Wi-Fi connected:", ok_wifi)

ok_ntp = False
if ok_wifi:
    ok_ntp = sync_time_ntp()
print("NTP synced:", ok_ntp)
print("UTC RTC:", time.localtime())
print("Detroit local:", localtime_detroit())

# ==============================
# MAIN LOOP
# ==============================

for c in CAGES:
    for pin in CAGES[c].values():
        pin.value(LED_OFF)

last_global_day = None

while True:
    try:
        gday = current_global_day()
        if gday != last_global_day:
            print("=== NEW LOGICAL DAY:", gday, "===")
            update_lights_for_global_day(gday)
            last_global_day = gday

        time.sleep(30)

    except Exception as e:
        print("Error in main loop:", e)
        time.sleep(5)
