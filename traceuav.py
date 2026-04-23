# -*- coding: utf-8 -*-
"""
Created on Thu Apr 23 11:51:23 2026

@author: mcgil
"""

from flask import Flask, jsonify
import threading, time, math, smtplib, csv, os, requests
from threading import Lock
import spidev
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import RPi.GPIO as GPIO
from picamera2 import Picamera2
from datetime import datetime
import time
print(dir(ADS))

PORT = 5000
EMAIL_ENABLED = True
EMAIL_SENDER = "mcgillivrayjulia@gmail.com"
EMAIL_PASSWORD = "pmbs qcnm xnmm ccqm"
EMAIL_RECIPIENT = "j.kusner@gwu.edu"

CSV_FILE = "trace-uav-log.csv"
photo_dir = "photos"

CO2_WARN = 1000 #ppm
CO2_DANGER = 2000

csv_file = "trace-uav-log.csv"
mcp_channel = 0

POLL_SECONDS = 2

app = Flask(__name__)

sensor_lock = Lock()
system_enabled = True
logging_enabled = True

sensor_data = {
    "co2_raw": None,
    "co2_est": None,
    "gas_raw": None,
    "noxious_gas": None,
    "timestamp": None,
    "photo": None
    }

alerts_sent = {
    "warn": False,
    "danger": False
    }

i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
chan1 = AnalogIn(ads, 1)
chan2 = AnalogIn(ads, 0)
def read_ads1115():
    return chan1.value, chan1.voltage, chan2.value, chan2.voltage

def estimate_co2(voltage):
    return int(400+(voltage/5.0)*1600)

def estimate_noxious(voltage):
    return round((voltage/5.0)*100, 1)

picam2 = Picamera2()
camera_config = picam2.create_still_configuration()

def capture_photo():
    os.makedirs(PHOTO_DIR, exist_ok = True)
    filename = datetime.now().strftme("alert_%Y%m%d_%H%M%S.jpg")
    filepath = os.path.join(PHOTO_DIR, filename)
   
    picam2.configure(camera_config)
    picam2.start()
    time.sleep(1)
    picam2.capture_file(filepath)
    picam2.stop()
   
    return filepath
       
       
#method of mapping ppm:
        #for (int x = 0;x<10;x++){                     //add samples together
         #zzz=zzz + co2now[x];
   
  #}
  #co2raw = zzz/10;                            //divide samples by 10
  #co2comp = co2raw - co2Zero;                 //get compensated value
  #co2ppm = map(co2comp,0,1023,400,5000);
        #c11 ?
             
# ──────────────────────────────────────────────
def send_email(subject, body, attachment_path=None):
    if not EMAIL_ENABLED:
        print(f"[ALERT] (email disabled) {subject}: {body}")
        return
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECIPIENT
        msg.set_content(body)
       
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                data = f.read()
            msg.add_attachment(
                data,
                maintype="image",
                subtype="jpeg",
                filename=os.path.basename(attachment_path)
            )
           
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
            smtp.send_message(msg)
           
        print("[EMAIL SENT]", subject)
       
    except Exception as e:
        print("[EMAIL ERROR]", e)

def init_csv():
        with open(CSV_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp",
                "co2_raw",
                "co2_voltage",
                "co2_est",
                "gas_raw",
                "gas_voltage",
                "noxious_gas",
                "photo"
                ])
           
def append_csv(row):
    with open(CSV_FILE, "a", newline="") as f:
              writer = csv.writer(f)
              writer.writerow(row)

def check_and_alert(co2_raw, co2_est, gas_raw, noxious_gas):
    photo_path = None
   
    if co2_est >= CO2_DANGER and not alerts_sent["danger"]:
        photo_path = capture_photo()
        send_email(
            "CO2 Danger Alert",
            f"CO2 estimate reached {co2_est} ppm. \n Raw ADC: {raw_adc} \nNoxious gas index: {noxious_gas}",
            photo_path
        )
        alerts_sent["danger"]=True
        alerts_sent["warn"]=True
       
    elif co2_est >= CO2_WARN and not alerts_sent["warn"]:
        photo_path = capture_photo()
        send_email(
            "CO2 Warning Alert",
            f"CO2 estimate reached {co2_est} ppm. \n Raw ADC: {co2_raw} \nNoxious gas index: {noxious_gas}",
            photo_path
        )
        alerts_sent["warn"] = True
       
    elif co2_est < CO2_WARN:
        alerts_sent["warn"] = False
        alerts_sent["danger"] = False
       
    return photo_path    
       
def sensor_loop():
    global sensor_data
   
    init_csv()
   
    while True:
        try:
            if system_enabled:
                co2_raw, co2_voltage, gas_raw, gas_voltage = read_ads1115()
                co2_est = estimate_co2(co2_voltage)
                noxious_gas = estimate_noxious(gas_voltage)
                ts = datetime.now().strftime("%Y-%m-%d %H: %M: %S")
               
                photo_path = check_and_alert(co2_raw, co2_est, gas_raw, noxious_gas)
               
                with sensor_lock:
                    sensor_data["co2_raw"] = co2_raw
                    sensor_data["co2_voltage"] = co2_voltage
                    sensor_data["co2_est"] = co2_est
                    sensor_data["gas_raw"] = gas_raw
                    sensor_data["gas_voltage"] = gas_voltage
                    sensor_data["noxious_gas"] = noxious_gas
                    sensor_data["timestamp"] = ts
                    sensor_data["photo"] = photo_path
                   
                if logging_enabled:
                    append_csv([ts, co2_raw, co2_voltage, co2_est, gas_raw, gas_voltage, noxious_gas, photo_path])
                   
                print(f"[DATA] {ts} raw={co2_raw} co2={co2_est} gas={noxious_gas}")
            time.sleep(POLL_SECONDS)
                     
        except Exception as e:
            print("[SENSOR LOOP ERROR}", e)
            time.sleep(2)
       
app = Flask(__name__)

@app.route("/")
def dashboard():
    # Serve the HTML file (put index.html in templates/ folder)
    try:
        with open("/home/pi/Desktop/traceuav/templates/traceuav.html", "r") as f:
            return f.read()
    except FileNotFoundError:
        return "<h2>Error: templates/index.html not found</h2><p>Make sure index.html is in a 'templates' folder next to app.py</p>", 404
   
@app.route("/data")
def data():
    with sensor_lock:
        return jsonify(sensor_data)

if __name__ == "__main__":
    # Start sensor reading in background thread
    t = threading.Thread(target=sensor_loop, daemon=True)
    t.start()

    print("\n====================================")
    print("  System running!")
    print("  Open browser → http://localhost:5000")
    print("  On same WiFi → http://10.130.1.218:5000")
    print("  Get Pi IP with: hostname -I")
    print("====================================\n")

    app.run(host="0.0.0.0", port=5000, debug=False)