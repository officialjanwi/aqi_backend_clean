# AQI Smart Project

This project is a smart system designed to reduce air pollution (AQI) using traffic control, IoT simulation, ML-based decision making, and Unity visualization.

The system detects pollution spikes and responds with actions such as traffic rerouting, speed control, and water sprinkler simulation.

---

## Live Backend

[https://airsense-n6nq.onrender.com](https://airsense-n6nq.onrender.com)

## API Documentation

[https://airsense-n6nq.onrender.com/docs](https://airsense-n6nq.onrender.com/docs)

---

## System Overview

This project integrates multiple components into a single pipeline:

* Traffic monitoring system
* Emission estimation based on vehicle flow
* ML-based decision engine for AQI detection
* Traffic control recommendations
* Water sprinkler simulation using Unity
* IoT sensor simulation using Wokwi / ESP32
* FastAPI backend deployed on Render

---

## What the Project Does

* Simulates environmental response using Unity (water sprinklers)
* Accepts IoT sensor data through API endpoints
* Connects all modules via a live backend system
* Monitors traffic conditions such as vehicle count and speed
* Estimates emission levels based on traffic data
* Detects high pollution scenarios using a decision model

---

## Architecture Flow

IoT Sensors (Wokwi / ESP32)
→ FastAPI Backend (Render)
→ ML Decision System
→ Traffic Control Logic
→ Unity Simulation (Environmental Response)

---

## Project Structure

Aqi_backend_clean/
├── app/
│   ├── core/
│   ├── models/
│   ├── routers/
│   ├── services/
│   └── main.py
├── traffic_module/
├── Unity/
├── wokwi/
├── requirements.txt
├── Dockerfile
└── README.md

---

## Running Locally

### Install dependencies

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

### Run backend

uvicorn app.main:app --reload

Open: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## Traffic Module

This module simulates traffic flow and emission estimation.

How to open and run
Open terminal / command prompt
Navigate to project folder:
cd traffic_module
Run the main script:
python traffic_integration.py
Output includes:
Traffic analysis
Emission estimation
Pollution detection

### Requirements

Install:
pip install numpy pandas scikit-learn and 
pip install matplotlib
---

## Unity Simulation

Used for visualizing environmental response (water sprinklers).

Steps:

* Open Unity Hub
* Open `Unity/` folder
* Run main scene
* Click Play

---

## IoT Simulation (Wokwi)

Used to simulate sensor input data.

Steps:

* Open `wokwi/` folder
* Import into wokwi.com
* Run simulation
* Send data to backend API

---

## API Endpoints

/
Root status

/docs
API documentation

/iot
IoT data input

/decision
Decision engine

/live_decision
Real-time processing

/gov_aqi
Government AQI integration

---

## Future Improvements

* Real-time traffic simulation using SUMO
* Advanced ML-based AQI prediction
* Live ESP32 hardware integration
* Automated Unity environment control
* Dashboard frontend

---

## Project Status

Backend deployed and live
API endpoints active
IoT simulation integrated
Unity visualization ready
Decision system functional
