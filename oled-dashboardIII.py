#!/usr/bin/env python3
"""
Raspberry Pi OLED Dashboard
---------------------------
Displays system stats, WireGuard VPN status, network activity,
and MySQL replication cluster health on an SSD1306 OLED.

Writes RED/UV into /tmp/led_status so an external LED script
can show replication health. Shows full screen flashing alerts
if a MySQL server is unreachable or in error.
"""

import time
import subprocess
import psutil
import netifaces
import pymysql
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from luma.core.render import canvas
from PIL import ImageFont

# -------------------------------
# OLED setup
# -------------------------------
serial = i2c(port=1, address=0x3C)
device = ssd1306(serial)
font = ImageFont.load_default()

# -------------------------------
# MySQL credentials
# -------------------------------
MYSQL_USER = "scftool"
MYSQL_PASS = "tWHp6K23qLk4zsfn"

# -------------------------------
# MySQL servers
# -------------------------------
servers = {
    "CH": "10.196.58.15",   # Master
    "DF": "10.196.58.28",   # Slave
    "CM": "10.196.58.32",   # Slave
    "DF2": "127.0.0.1"      # Local Slave
}

# -------------------------------
# Collect MySQL cluster status
# -------------------------------
def get_mysql_status():
    results = []
    errors = []
    has_error = False

    for name, ip in servers.items():
        try:
            conn = pymysql.connect(
                host=ip,
                user=MYSQL_USER,
                password=MYSQL_PASS,
                connect_timeout=5,
                cursorclass=pymysql.cursors.DictCursor
            )
            with conn.cursor() as cur:
                cur.execute("SHOW REPLICA STATUS")
                row = cur.fetchone()

                if row:
                    lag = row.get("Seconds_Behind_Source")
                    io_running = row.get("Replica_IO_Running")
                    sql_running = row.get("Replica_SQL_Running")

                    if io_running != "Yes" or sql_running != "Yes":
                        msg = f"{name}: SLAVE STOPPED"
                        results.append(msg)
                        errors.append((name, "REPLICA STOPPED"))
                        has_error = True
                    elif lag is None:
                        msg = f"{name}: SLAVE NULLs ALERT!"
                        results.append(msg)
                        errors.append((name, "NULL LAG"))
                        has_error = True
                    elif lag > 30:
                        msg = f"{name}: SLAVE {lag}s ALERT!"
                        results.append(msg)
                        errors.append((name, f"LAG {lag}s"))
                        has_error = True
                    else:
                        results.append(f"{name}:SLAVE {lag}s")
                else:
                    cur.execute("SHOW MASTER STATUS")
                    row = cur.fetchone()
                    if row:
                        results.append(f"{name}:MASTER OK")
                    else:
                        msg = f"{name}: UNKNOWN"
                        results.append(msg)
                        errors.append((name, "UNKNOWN ROLE"))
                        has_error = True

        except Exception as e:
            msg = f"{name}: ERR"
            results.append(msg)
            errors.append((name, "SERVER DOWN"))
            has_error = True
            print(f"MySQL error for {name} ({ip}): {repr(e)}", flush=True)

    cluster_text = " | ".join(results)
    print("Cluster status:", cluster_text, "Error flag:", has_error, flush=True)
    return cluster_text, errors, has_error

# -------------------------------
# Update LED colour
# -------------------------------
def update_led_status(has_error):
    with open("/tmp/led_status", "w") as f:
        if has_error:
            f.write("RED")
        else:
            f.write("UV")

# -------------------------------
# OLED dashboard drawing
# -------------------------------
def dashboard(draw, offset, cluster_text):
    # VPN
    wg = subprocess.getoutput("wg show")
    try:
        wgip = netifaces.ifaddresses("wg0")[netifaces.AF_INET][0]['addr']
    except:
        wgip = "No IP"
    wg_status = f"VPN:{wgip}" if "interface:" in wg else "VPN: DOWN ALERT!"
    draw.text((0, 0), wg_status, font=font, fill=255)

    # LAN
    try:
        ip = netifaces.ifaddresses("eth0")[netifaces.AF_INET][0]['addr']
    except:
        ip = "No IP"
    draw.text((0, 10), f"LAN:{ip}", font=font, fill=255)

    # CPU/MEM/SSD/TEMP headers
    draw.text((0, 20),  "|CPU%", font=font, fill=255)
    draw.text((33, 20), "|MEM%", font=font, fill=255)
    draw.text((66, 20), "|SSD%", font=font, fill=255)
    draw.text((99, 20), "|T-C",  font=font, fill=255)

    # Values row
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent
    disk_ssd = psutil.disk_usage("/").percent
    temp = subprocess.getoutput("vcgencmd measure_temp | egrep -o '[0-9]*\\.[0-9]*'")

    draw.text((0, 30),  f"|{cpu:>3}", font=font, fill=255)
    draw.text((33, 30), f"|{mem:>3}", font=font, fill=255)
    draw.text((66, 30), f"|{disk_ssd:>3}", font=font, fill=255)
    draw.text((99, 30), f"|{temp}", font=font, fill=255)

    # Network TX/RX
    net = psutil.net_io_counters()
    tx = round(net.bytes_sent / (1024 * 1024), 1)
    rx = round(net.bytes_recv / (1024 * 1024), 1)
    draw.text((0, 40), f"TX/RX MB: {tx}/{rx}", font=font, fill=255)

    # MySQL cluster marquee
    draw_marquee(draw, cluster_text, offset, y=50, spacing=20)

def draw_marquee(draw, cluster_text, offset, y=50, spacing=10):
    text_w = draw.textbbox((0, 0), cluster_text, font=font)[2]
    total_w = text_w + spacing
    x = -(offset % total_w)
    draw.text((x, y), cluster_text, font=font, fill=255)
    draw.text((x + total_w, y), cluster_text, font=font, fill=255)

# -------------------------------
# Show full screen error (flashing inverted text)
# -------------------------------
def show_fullscreen_error(name, msg, flash_state=True):
    with canvas(device) as draw:
        W, H = device.width, device.height

        if flash_state:
            # Inverted (white background, black text)
            draw.rectangle(device.bounding_box, outline=255, fill=255)
            text_fill = 0
        else:
            # Normal (black background, white text)
            draw.rectangle(device.bounding_box, outline=255, fill=0)
            text_fill = 255

        # --- First line (server name) ---
        bbox = draw.textbbox((0, 0), name, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (W - text_w) // 2
        y = (H // 2) - text_h - 2
        draw.text((x, y), name, font=font, fill=text_fill)

        # --- Second line (error msg) ---
        bbox = draw.textbbox((0, 0), msg, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (W - text_w) // 2
        y = (H // 2) + 2
        draw.text((x, y), msg, font=font, fill=text_fill)

# -------------------------------
# Main loop
# -------------------------------
if __name__ == "__main__":
    scroll_offset = 0
    cluster_text, errors, has_error = get_mysql_status()
    update_led_status(has_error)
    last_update = time.time()

    flash_state = True

    while True:
        # Refresh MySQL cluster every 30s
        if time.time() - last_update > 30:
            cluster_text, errors, has_error = get_mysql_status()
            last_update = time.time()

        update_led_status(has_error)

        if errors:  # show fullscreen error pages
            for name, msg in errors:
                show_fullscreen_error(name, msg, flash_state)
                flash_state = not flash_state  # alternate inverted/normal
                time.sleep(1)  # flash cycle
        else:       # normal dashboard
            with canvas(device) as draw:
                dashboard(draw, scroll_offset, cluster_text)
            scroll_offset += 12
            time.sleep(0.02)
