import numpy as np
import matplotlib.pyplot as plt
import requests

from skyfield.api import load, EarthSatellite
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.animation import FuncAnimation

# ===============================
# SPACE FORCE SSA v4
# GPS FULL CONSTELLATION + ANIMATION
# ===============================

# -------------------------------
# GPS 위성 TLE 다운로드
# -------------------------------
print("Downloading GPS satellite catalog...")

url = "https://celestrak.org/NORAD/elements/gps-ops.txt"
data = requests.get(url).text.splitlines()

satellites = []

for i in range(0, len(data), 3):
    name = data[i].strip()
    line1 = data[i+1].strip()
    line2 = data[i+2].strip()

    sat = EarthSatellite(line1, line2, name)
    satellites.append(sat)

print(f"Loaded {len(satellites)} GPS satellites.\n")

# -------------------------------
# 시간 설정
# -------------------------------
ts = load.timescale()

# -------------------------------
# 3D Plot 생성
# -------------------------------
fig = plt.figure(figsize=(10, 10))
ax = fig.add_subplot(111, projection="3d")

plt.title("SPACE FORCE SSA v4 - GPS LIVE ORBIT TRACKER", fontsize=14)

# -------------------------------
# 지구 Sphere 생성
# -------------------------------
earth_radius = 6371  # km

u = np.linspace(0, 2 * np.pi, 80)
v = np.linspace(0, np.pi, 80)

x = earth_radius * np.outer(np.cos(u), np.sin(v))
y = earth_radius * np.outer(np.sin(u), np.sin(v))
z = earth_radius * np.outer(np.ones(np.size(u)), np.cos(v))

ax.plot_surface(x, y, z, alpha=0.25)

# -------------------------------
# 위성 점 + 텍스트 저장
# -------------------------------
points = []
labels = []

for sat in satellites:
    point = ax.scatter([], [], [], s=30)
    label = ax.text(0, 0, 0, "", fontsize=6)

    points.append(point)
    labels.append(label)

# -------------------------------
# 보기 설정
# -------------------------------
ax.set_xlim(-30000, 30000)
ax.set_ylim(-30000, 30000)
ax.set_zlim(-30000, 30000)

ax.set_xlabel("X (km)")
ax.set_ylabel("Y (km)")
ax.set_zlabel("Z (km)")

ax.set_box_aspect([1, 1, 1])

# -------------------------------
# 애니메이션 업데이트 함수
# -------------------------------
def update(frame):
    ax.set_title(f"SPACE FORCE SSA v4 - Time Step {frame}", fontsize=13)

    # 시간 흐름 (프레임마다 +2분)
    t = ts.now() + frame * (2 / 1440)

    for i, sat in enumerate(satellites):
        geocentric = sat.at(t)
        pos = geocentric.position.km

        xs, ys, zs = pos[0], pos[1], pos[2]

        # 점 업데이트
        points[i]._offsets3d = ([xs], [ys], [zs])

        # 이름 업데이트
        labels[i].set_position((xs, ys))
        labels[i].set_3d_properties(zs)
        labels[i].set_text(sat.name[:8])

    return points

# -------------------------------
# 애니메이션 실행
# -------------------------------
ani = FuncAnimation(fig, update, frames=200, interval=200)

plt.show()
