rom flask import Flask, jsonify, redirect, render_template_string
import socket

app = Flask(__name__)

OPENWEBRX_PORT = 8073
FLASK_PORT = 5050

HTML = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>SDR Control Panel</title>
    <style>
        body {
            font-family: Arial;
            background:#111;
            color:#eee;
            margin:40px;
        }
        .card {
            max-width:700px;
            margin:auto;
            padding:24px;
            background:#1b1b1b;
            border-radius:16px;
        }
        a {
            display:inline-block;
            margin:10px 10px 0 0;
            padding:10px 16px;
            background:#2d6cdf;
            color:white;
            border-radius:10px;
            text-decoration:none;
        }
        .status {
            margin-top:20px;
            font-size:18px;
        }
    </style>
</head>
<body>
<div class="card">
    <h1>SDR Control Panel</h1>
    <p>Flask: 5050 / OpenWebRX: 8073</p>

    <div class="status">
        SDR Status:
        {% if running %}
            <span style="color:#4cd137;">RUNNING</span>
        {% else %}
            <span style="color:#e84118;">STOPPED</span>
        {% endif %}
    </div>

    <a href="/sdr-status">Check Status</a>
    <a href="/start-sdr">Start SDR</a>
    <a href="/stop-sdr">Stop SDR</a>
    <a href="/go-sdr" target="_blank">Open SDR</a>
</div>
</body>
</html>
"""

def is_port_open(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", port))
        s.close()
        return True
    except:
        return False

@app.route("/")
def index():
    return render_template_string(HTML, running=is_port_open(OPENWEBRX_PORT))

@app.route("/sdr-status")
def status():
    return jsonify({
        "openwebrx_running": is_port_open(OPENWEBRX_PORT),
        "port": OPENWEBRX_PORT
    })

@app.route("/start-sdr")
def start():
    import subprocess
    subprocess.run(["docker", "start", "openwebrx"])
    return redirect("/")

@app.route("/stop-sdr")
def stop():
    import subprocess
    subprocess.run(["docker", "stop", "openwebrx"])
    return redirect("/")

@app.route("/go-sdr")
def go():
    return redirect(f"http://127.0.0.1:{OPENWEBRX_PORT}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
