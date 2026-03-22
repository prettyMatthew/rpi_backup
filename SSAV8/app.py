from flask import Flask, render_template
from skyfield.api import load, EarthSatellite, Topos
import plotly.graph_objects as go
import numpy as np
import os

app = Flask(__name__)

# ================================
# 위성 TLE 예시
# ================================
import requests

# ================================
# TLE 자동 다운로드 함수
# ================================
def load_tle(url, limit=50):
    r = requests.get(url)
    r.encoding = "utf-8"
    lines = r.text.strip().split("\n")

    sats = []
    for i in range(0, len(lines), 3):
        if i + 2 >= len(lines):
            break

        name = lines[i].strip()
        line1 = lines[i+1].strip()
        line2 = lines[i+2].strip()

        sats.append((name, line1, line2))

        if len(sats) >= limit:
            break

    return sats


# ================================
# GPS + Starlink 최신 TLE 불러오기
# ================================
gps_url = "https://celestrak.org/NORAD/elements/gps-ops.txt"
starlink_url = "https://celestrak.org/NORAD/elements/starlink.txt"

gps_sats = load_tle(gps_url, limit=32)
starlink_sats = load_tle(starlink_url, limit=50)

ts = load.timescale()
t = ts.now()

# ================================
# Ground Station (Seoul)
# ================================
ground_station = Topos(
    latitude_degrees=37.5665,
    longitude_degrees=126.9780
)

# ================================
# Plot 생성
# ================================
def build_plot():
    fig = go.Figure()

    # 🌍 Earth Sphere
    R = 6371
    u, v = np.mgrid[0:2*np.pi:50j, 0:np.pi:25j]
    x = R * np.cos(u) * np.sin(v)
    y = R * np.sin(u) * np.sin(v)
    z = R * np.cos(v)

    fig.add_trace(go.Surface(
        x=x, y=y, z=z,
        opacity=0.4,
        showscale=False
    ))

    # 📍 Ground Station
    gs = ground_station.at(t).position.km

    fig.add_trace(go.Scatter3d(
        x=[gs[0]], y=[gs[1]], z=[gs[2]],
        mode="markers+text",
        text=["Ground Station"],
        textposition="top center",
        marker=dict(size=6),
        name="Ground Station"
    ))

    # 🛰 Satellites
    all_sats = gps_sats + starlink_sats


    for name, l1, l2 in all_sats:
        sat = EarthSatellite(l1, l2, name, ts)
        pos = sat.at(t).position.km

        fig.add_trace(go.Scatter3d(
            x=[pos[0]], y=[pos[1]], z=[pos[2]],
            mode="markers+text",
            text=[name],
            textposition="top center",
            marker=dict(size=4),
            name=name
        ))

    fig.update_layout(
        title="Matthew Satellite Tracker",
        margin=dict(l=0, r=0, b=0, t=40),
        scene=dict(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            zaxis=dict(visible=False)
        )
    )

    return fig.to_html(full_html=False, include_plotlyjs="cdn")



# ================================
# Flask Route
# ================================
@app.route("/")
def home():
    plot_html = build_plot()
    return render_template("index.html", plot_html=plot_html)


# ================================
# Run Server
# ================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
