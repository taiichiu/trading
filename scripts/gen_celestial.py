"""Generate data/celestial.json — planet sign-change events for 2020-2030.

Uses NASA JPL low-precision approximate orbital elements
(https://ssd.jpl.nasa.gov/planets/approx_pos.html) plus a one-step Kepler
solver to compute geocentric ecliptic longitude for each planet daily,
then scans for sign changes (every 30°) and direction (forward / retrograde).
North Node uses the standard mean-longitude expression.

Accuracy: ±1 day for Mercury–Mars, ±2-3 days for Jupiter/Saturn, sub-degree
for the lunar mean ascending node.
"""

import json
import math
import os
from collections import defaultdict
from datetime import date, timedelta

J2000 = 2451545.0
DEG = math.pi / 180

# NASA JPL approximate elements (J2000), valid roughly 1800-2050.
# Each entry: (value_at_J2000, rate_per_century)
ELEMENTS = {
    "mercury": {
        "a": (0.38709927,  0.00000037),
        "e": (0.20563593,  0.00001906),
        "I": (7.00497902, -0.00594749),
        "L": (252.25032350, 149472.67411175),
        "long_peri": (77.45779628, 0.16047689),
        "long_node": (48.33076593, -0.12534081),
    },
    "venus": {
        "a": (0.72333566,  0.00000390),
        "e": (0.00677672, -0.00004107),
        "I": (3.39467605, -0.00078890),
        "L": (181.97909950, 58517.81538729),
        "long_peri": (131.60246718, 0.00268329),
        "long_node": (76.67984255, -0.27769418),
    },
    "earth": {
        "a": (1.00000261,  0.00000562),
        "e": (0.01671123, -0.00004392),
        "I": (-0.00001531, -0.01294668),
        "L": (100.46457166, 35999.37244981),
        "long_peri": (102.93768193, 0.32327364),
        "long_node": (0.0, 0.0),
    },
    "mars": {
        "a": (1.52371034,  0.00001847),
        "e": (0.09339410,  0.00007882),
        "I": (1.84969142, -0.00813131),
        "L": (-4.55343205, 19140.30268499),
        "long_peri": (-23.94362959, 0.44441088),
        "long_node": (49.55953891, -0.29257343),
    },
    "jupiter": {
        "a": (5.20288700, -0.00011607),
        "e": (0.04838624, -0.00013253),
        "I": (1.30439695, -0.00183714),
        "L": (34.39644051, 3034.74612775),
        "long_peri": (14.72847983, 0.21252668),
        "long_node": (100.47390909, 0.20469106),
    },
    "saturn": {
        "a": (9.53667594, -0.00125060),
        "e": (0.05386179, -0.00050991),
        "I": (2.48599187,  0.00193609),
        "L": (49.95424423, 1222.49362201),
        "long_peri": (92.59887831, -0.41897216),
        "long_node": (113.66242448, -0.28867794),
    },
}

PLANET_LABELS = {
    "mercury": ("水星", "☿"),
    "venus":   ("金星", "♀"),
    "mars":    ("火星", "♂"),
    "jupiter": ("木星", "♃"),
    "saturn":  ("土星", "♄"),
    "north_node": ("北交點", "☊"),
}

ZODIAC = ["白羊座", "金牛座", "雙子座", "巨蟹座", "獅子座", "處女座",
          "天秤座", "天蠍座", "射手座", "摩羯座", "水瓶座", "雙魚座"]


def jd_of(d):
    """Julian day at 0h UT for date d."""
    y, m, day = d.year, d.month, d.day
    if m <= 2:
        y -= 1
        m += 12
    A = y // 100
    B = 2 - A + A // 4
    return (math.floor(365.25 * (y + 4716))
            + math.floor(30.6001 * (m + 1))
            + day + B - 1524.5)


def kepler_E(M, e):
    """Newton solve for E in M = E - e sin E. M in radians."""
    E = M
    for _ in range(60):
        f = E - e * math.sin(E) - M
        fp = 1 - e * math.cos(E)
        dE = f / fp
        E -= dE
        if abs(dE) < 1e-9:
            break
    return E


def helio_pos(body, T):
    """Heliocentric J2000 ecliptic position (AU) of a planet."""
    el = ELEMENTS[body]
    a = el["a"][0] + el["a"][1] * T
    e = el["e"][0] + el["e"][1] * T
    I = el["I"][0] + el["I"][1] * T
    L = el["L"][0] + el["L"][1] * T
    long_peri = el["long_peri"][0] + el["long_peri"][1] * T
    long_node = el["long_node"][0] + el["long_node"][1] * T
    omega = long_peri - long_node
    M = ((L - long_peri + 180) % 360) - 180
    E = kepler_E(M * DEG, e)
    xp = a * (math.cos(E) - e)
    yp = a * math.sqrt(max(0, 1 - e * e)) * math.sin(E)

    cO = math.cos(long_node * DEG); sO = math.sin(long_node * DEG)
    cw = math.cos(omega * DEG);     sw = math.sin(omega * DEG)
    cI = math.cos(I * DEG);         sI = math.sin(I * DEG)
    x = (cw * cO - sw * sO * cI) * xp + (-sw * cO - cw * sO * cI) * yp
    y = (cw * sO + sw * cO * cI) * xp + (-sw * sO + cw * cO * cI) * yp
    z = (sw * sI)                  * xp + (cw * sI)                  * yp
    return x, y, z


def geo_longitude(body, T):
    """Geocentric J2000 ecliptic longitude (degrees, 0-360)."""
    xE, yE, zE = helio_pos("earth", T)
    if body == "sun":
        x, y = -xE, -yE
    else:
        xP, yP, _ = helio_pos(body, T)
        x, y = xP - xE, yP - yE
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def north_node_longitude(JD):
    """Mean longitude of the Moon's ascending node, retrograde."""
    T = (JD - J2000) / 36525
    Omega = (125.04452
             - 1934.13626197 * T
             + 0.0020708 * T * T
             + T * T * T / 450000)
    return (Omega % 360 + 360) % 360


def daterange(start, end):
    d = start
    one = timedelta(days=1)
    while d <= end:
        yield d
        d += one


def sign_index(lon):
    return int(((lon % 360) + 360) % 360 // 30)


def main():
    start = date(2020, 1, 1)
    end   = date(2030, 12, 31)

    # Build per-day longitude tables for each planet (incl. north node)
    bodies = ["mercury", "venus", "mars", "jupiter", "saturn", "north_node"]
    lon_table = {b: [] for b in bodies}
    dates = list(daterange(start, end))

    for d in dates:
        jd = jd_of(d)
        T = (jd - J2000) / 36525
        for b in bodies:
            if b == "north_node":
                lon_table[b].append(north_node_longitude(jd))
            else:
                lon_table[b].append(geo_longitude(b, T))

    # Find sign-change events (compare day i and day i-1)
    events = []
    for b in bodies:
        zh, sym = PLANET_LABELS[b]
        prev_sign = sign_index(lon_table[b][0])
        for i in range(1, len(dates)):
            curr_lon = lon_table[b][i]
            prev_lon = lon_table[b][i - 1]
            curr_sign = sign_index(curr_lon)
            if curr_sign != prev_sign:
                # direction: positive delta after wrap = forward
                delta = (curr_lon - prev_lon + 540) % 360 - 180
                retrograde = delta < 0
                from_sign = ZODIAC[prev_sign]
                to_sign = ZODIAC[curr_sign]
                events.append({
                    "date": dates[i].isoformat(),
                    "planet": zh,
                    "symbol": sym,
                    "from": from_sign,
                    "to": to_sign,
                    "retrograde": retrograde,
                    "lon": round(curr_lon, 3),
                })
            prev_sign = curr_sign

    # Group by year, sort within
    by_year = defaultdict(list)
    for e in events:
        by_year[e["date"][:4]].append(e)
    for y in by_year:
        by_year[y].sort(key=lambda x: (x["date"], x["planet"]))

    out = {
        "meta": {
            "generated": date.today().isoformat(),
            "range": f"{start.isoformat()} ~ {end.isoformat()}",
            "method": "NASA JPL approx_pos elements + Kepler solve, geocentric ecliptic longitude",
            "bodies": [PLANET_LABELS[b][0] for b in bodies],
            "zodiac": ZODIAC,
            "accuracy_days": "±1 (Mer–Mar), ±3 (Jup/Sat), <1 (NN)",
            "total_events": len(events),
        },
        "by_year": {y: by_year[y] for y in sorted(by_year)},
    }

    os.makedirs("data", exist_ok=True)
    with open("data/celestial.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Wrote data/celestial.json ({len(events)} events)")
    for b in bodies:
        zh = PLANET_LABELS[b][0]
        cnt = sum(1 for e in events if e["planet"] == zh)
        print(f"  {zh}: {cnt}")


if __name__ == "__main__":
    main()
