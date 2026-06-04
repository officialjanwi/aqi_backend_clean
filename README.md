# AQI Smart Project

This project is a simple attempt to reduce air pollution (AQI) using a combination of traffic control and water-based intervention.

The idea is to detect situations where pollution increases and then take small but practical actions like adjusting traffic flow or activating water sprinklers to bring it down.

---

## What this project does

* Monitors traffic conditions (vehicle count, speed)
* Estimates emission levels based on traffic
* Detects high pollution situations using a simple ML model
* Suggests traffic actions like rerouting or speed control
* Simulates water sprinklers (Unity) to reduce dust/pollution
* Can connect with IoT (ESP32 via Wokwi) for sensor data

---

## Project Structure

AQI-Smart-Project/
│
├── app/
├── traffic_module/
├── Unity/
├── wokwi/
├── README.md
├── requirements.txt

---

## How to run

### 1. Setup environment

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

---

### 2. Run backend

uvicorn app.main:app --reload

Open in browser:
http://127.0.0.1:8000/docs

---

## Traffic Module (how to run)

This module simulates traffic and estimates emission levels.

Steps:

1. Go to the folder:

   cd traffic_module

2. Run the main file:

   python traffic_integration.py

   (If file name is different, run the main script like `ai_model.py` or `aqi_module.py`)

3. Output:

   * Traffic data processed
   * Emission level calculated
   * High/normal pollution detected

---

## Water / Unity Module

This part shows how water sprinklers can help reduce pollution visually.

Steps:

1. Open Unity Hub
2. Click **Open Project**
3. Select the `Unity/` folder

After opening:

* Open the main scene (inside `Scenes/`)
* Click **Play**

This simulates water spraying or environmental change.

---

## IoT Simulation (Wokwi)

This simulates sensor data input.

Steps:

1. Open the `wokwi/` folder
2. Upload/open it on wokwi.com
3. Run the simulation

This generates environmental/sensor values that can be used by the backend.

---

## How everything connects

* Traffic module detects high emission
* Backend processes the condition
* System suggests:

  * Traffic control actions
  * Water spraying (via Unity simulation)

---

## Notes

* This is a student project, so some parts are simplified
* Focus is on idea + working flow, not perfect accuracy
* Each module can run independently

---

## Future Improvements

* Real-time traffic simulation (SUMO integration)
* Better ML models
* Real sensor data instead of simulation
* Automated control between modules

---

## Author

Made as part of a project on AQI reduction using traffic and water-based methods.
