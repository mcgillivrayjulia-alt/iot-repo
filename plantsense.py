from flask import Flask, jsonify, render_template_string
import threading
import time
import math
import smtplib
import json
import os

import PCF8591 as ADC
import RPi.GPIO as GPIO
ON_PI = True
print("Running on Raspberry Pi - sensors active")
    
EMAIL_ENABLED   = True          
EMAIL_SENDER    = "mcgillivrayjulia@gmail.com"
EMAIL_PASSWORD  = ""   # Gmail App Password 
EMAIL_RECIPIENT = "j.kusner@gwmail.gwu.edu"

TEMP_MAX        = 33.0 
LIGHT_MIN       = 200    
MOISTURE_MAX    = 175

DO_PIN          = 17     # GPIO pin for temperature module digital out
ADC_ADDR        = 0x48   # PCF8591 I2C address

sensor_data = { #initialize all variables
    "temperature": None,
    "light": None,
    "moisture_raw": None,
    "moisture_pct": None,
    "moisture_level": "UNKNOWN",
    "timestamp": None
}
alerts_sent = {"temp": False, "light": False, "moisture": False}

def read_temperature():
    """Reads thermistor on ADC channel 0 via PCF8591"""
    try:
        analog_val = ADC.read(0)
        if analog_val in (0, 255):  
            return None
        Vr   = 5 * float(analog_val) / 255
        Rt   = 10000 * Vr / (5 - Vr)
        temp = 1 / (((math.log(Rt / 10000)) / 3950) + (1 / (273.15 + 25)))
        return round(temp - 273.15, 2)
    except Exception as e:
        print(f"[TEMP ERROR] {e}")
        return None

def read_light():
    """Reads photoresistor on ADC channel 1 via PCF8591 (0–255)"""
    try:
        raw = ADC.read(1)
        # Map 0–255 to approximate lux 0–1000
        lux = round(raw * (1000 / 255), 1)
        return lux
    except Exception as e:
        print(f"[LIGHT ERROR] {e}")
        return None

def read_moisture():
    """
    Reads soil moisture on ADC channel 3 via PCF8591.
    Your sensor: HIGH raw value = DRY, LOW = WET
    """
    try:
        # using PCF8591, channel 3 shown here
        raw = ADC.read(3)
        # Scale raw (0-255 for PCF8591) to percentage
        # For PCF8591: invert so 100% = wet, 0% = dry
        pct  = round((1 - raw / 255) * 100, 1)
        level = "DRY" if raw > (MOISTURE_MAX / 257) else "WET"  # Scaled threshold
        return raw, pct, level
    except Exception as e:
        print(f"[MOISTURE ERROR] {e}")
        return None, None, "UNKNOWN"

def send_email(subject, body):
    if not EMAIL_ENABLED:
        print(f"[ALERT] (email disabled) {subject}: {body}")
        return
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            message = f"Subject: {subject}\n\n{body}"
            server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, message)
        print(f"[EMAIL SENT] {subject}")
    except Exception as e:  
        print(f"[EMAIL ERROR] {e}")

def check_and_alert(temp, light, moisture_raw, moisture_level):
    global alerts_sent

    # Temperature too high
    if temp is not None:
        if temp > TEMP_MAX and not alerts_sent["temp"]:
            send_email(
                "PlantWatch: High Temperature Alert",
                f"Temperature is {temp}°C - above your threshold of {TEMP_MAX}°C.\nCheck on your plant!"
            )
            alerts_sent["temp"] = True
        elif temp <= TEMP_MAX:
            alerts_sent["temp"] = False

    # Light too low
    if light is not None:
        if light < LIGHT_MIN and not alerts_sent["light"]:
            send_email(
                "PlantWatch: Low Light Alert",
                f"Light level is {light} lux - below your minimum of {LIGHT_MIN} lux.\nYour plant may need more light!"
            )
            alerts_sent["light"] = True
        elif light >= LIGHT_MIN:
            alerts_sent["light"] = False
#your plant might need n=more light!!
    # Soil too dry
    if moisture_level == "DRY" and not alerts_sent["moisture"]:
        send_email(
            "PlantWatch: Soil Dry Alert",
            f"Soil moisture sensor reads DRY (raw: {moisture_raw}).Time to water your plant!"
        )
        alerts_sent["moisture"] = True
    elif moisture_level == "WET":
        alerts_sent["moisture"] = False

def sensor_loop():
    if ON_PI:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(DO_PIN, GPIO.IN)
        ADC.setup(ADC_ADDR)

    while True:
        try:
            temp  = read_temperature()
            light = read_light()
            raw_m, pct_m, level_m = read_moisture()

            sensor_data["temperature"]    = temp
            sensor_data["light"]          = light
            sensor_data["moisture_raw"]   = raw_m
            sensor_data["moisture_pct"]   = pct_m
            sensor_data["moisture_level"] = level_m
            sensor_data["timestamp"]      = time.time()

            print(f"[DATA] Temp={temp}°C  Light={light}lux  Moisture={pct_m}% ({level_m})")
            check_and_alert(temp, light, raw_m, level_m)

        except Exception as e:
            print(f"[SENSOR LOOP ERROR] {e}")

        time.sleep(3)   # Read every 3 seconds

app = Flask(__name__)

@app.route("/")
def dashboard():
    # from index.html in templates/ folder
    try:
        with open("templates/index.html", "r") as f:
            return f.read()
    except FileNotFoundError:
        return "<h2>Error: templates/index.html not found</h2><p>Make sure index.html is in a 'templates' folder next to app.py</p>", 404

@app.route("/data")
def data():
    """JSON endpoint the dashboard polls every 5 seconds"""
    return jsonify({
        "temperature": sensor_data["temperature"],
        "light":       sensor_data["light"],
        "moisture":    sensor_data["moisture_pct"],
        "moisture_raw": sensor_data["moisture_raw"],
        "moisture_level": sensor_data["moisture_level"],
        "timestamp":   sensor_data["timestamp"],
        "demo_mode":   not ON_PI
    })

@app.route("/status") #rewrites each status variable
def status():
    return jsonify({
        "on_pi": ON_PI,
        "email_enabled": EMAIL_ENABLED,
        "thresholds": {
            "temp_max": TEMP_MAX,
            "light_min": LIGHT_MIN,
            "moisture_threshold": MOISTURE_MAX
        }
    })

if __name__ == "__main__":
    t = threading.Thread(target=sensor_loop, daemon=True)
    t.start()

    print("\n====================================")
    print("  PlantSense running!")
    print("  Open browser → http://localhost:5000")
    print("  On same WiFi → http://<pi-ip>:5000")
    print("  Get Pi IP with: hostname -I")
    print("====================================\n")

    app.run(host="0.0.0.0", port=5000, debug=False)
