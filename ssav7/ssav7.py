import numpy as np
import matplotlib.pyplot as plt
import requests

from skyfield.api import load, EarthSatellite, wgs84
from matplotlib.animation import FuncAnimation

# ===============================
# SPACE FORCE SSA v6.1 (FIXED)
# GPS + STARLINK + MY LOCATION
# ===============================

ts = load.timescale()

# ---------------------------------------------------
# ✅ SAFE TLE LOADER (Fixes IndexError permanently)
# ---------------------------------------------------
def load_tle(url, limit=None):
    print(f"Downloading: {url}")

    data = requests.get(url).text.splitlines()
    sats = []

    for i in range(0, len(data), 3):

        # ✅ Prevent out-of-range crash
        if i + 2 >= len(data):
            break

        name = data[i].strip()
        line1 = data[i + 1].strip()
        line2 = data[i + 2].strip()

        # ✅ Skip broken/empty entries
        if line1 == "" or line2 == "":
            continue

        try:
            sat = EarthSatellite(line1, line2, name)
            sats.append(sat)
        except:
            continue

        # Stop if limit reached
        if limit and len(sats) >= limit:
            break

    return sats


# ---------------------------------------------------
# 🛰️ LOAD SATELLITES
# ---------------------------------------------------
print("\nLoading GPS satellites...")
gps_sats = load_tle(
    "https://celestrak.org/NORAD/elements/gps-ops.txt"
)
print("GPS loaded:", len(gps_sats))

print("\nLoading Starlink satellites...")
starlink_sats = load_tle(
    "https://celestrak.org/NORAD/elements/starlink.txt",
    limit=50
)
print("Starlink loaded:", len(starlink_sats))

# Combine all
satellites = gps_sats + starlink_sats
print("\nTotal satellites loaded:", len(satellites))


# ---------------------------------------------------
# 🌍 YOUR LOCATION (Seoul)
# ---------------------------------------------------
my_lat = 37.5665
my_lon = 126.9780
my_location = wgs84.latlon(my_lat, my_lon)


# ---------------------------------------------------
# 🌎 3D EARTH SETUP
# ---------------------------------------------------
fig = plt.figure(figsize=(10, 10))
ax = fig.add_subplot(111, projection="3d")

earth_radius = 6371  # km

# Earth sphere mesh
u = np.linspace(0, 2 * np.pi, 100)
v = np.linspace(0, np.pi, 100)

x = earth_radius * np.outer(np.cos(u), np.sin(v))
y = earth_radius * np.outer(np.sin(u), np.sin(v))
z = earth_radius * np.outer(np.ones(np.size(u)), np.cos(v))

ax.plot_surface(x, y, z, alpha=0.25)


# ---------------------------------------------------
# 📍 MARK YOUR POSITION ON EARTH
# ---------------------------------------------------
lat_rad = np.radians(my_lat)
lon_rad = np.radians(my_lon)

mx = earth_radius * np.cos(lat_rad) * np.cos(lon_rad)
my = earth_radius * np.cos(lat_rad) * np.sin(lon_rad)
mz = earth_radius * np.sin(lat_rad)

ax.scatter(mx, my, mz, s=200)
ax.text(mx, my, mz, " YOU (Seoul)", fontsize=10)


# ---------------------------------------------------
# 🛰️ SATELLITE POINT OBJECTS
# ---------------------------------------------------
points = []

for sat in satellites:
    p = ax.scatter([], [], [], s=15)
    points.append(p)


# ---------------------------------------------------
# VIEW LIMITS
# ---------------------------------------------------
ax.set_xlim(-30000, 30000)
ax.set_ylim(-30000, 30000)
ax.set_zlim(-30000, 30000)

ax.set_xlabel("X (km)")
ax.set_ylabel("Y (km)")
ax.set_zlabel("Z (km)")

ax.set_box_aspect([1, 1, 1])


# ---------------------------------------------------
# 🔄 ANIMATION UPDATE FUNCTION
# ---------------------------------------------------
def update(frame):

    # Realistic speed: 20 seconds per frame
    t = ts.now() + frame * (20 / 86400)

    for i, sat in enumerate(satellites):

        pos = sat.at(t).position.km
        xs, ys, zs = pos[0], pos[1], pos[2]

        points[i]._offsets3d = ([xs], [ys], [zs])

    ax.set_title(
        "SPACE FORCE SSA v6.1 - GPS + Starlink + Ground Station",
        fontsize=13
    )

    return points


# ---------------------------------------------------
# ▶ RUN ANIMATION
# ---------------------------------------------------
ani = FuncAnimation(fig, update, frames=300, interval=200)

plt.show()
