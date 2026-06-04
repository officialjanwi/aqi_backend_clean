Delhi AQI SUMO Project - Full AI Training Version
================================================

This version trains a fresh road-action AI model from Phase 1 SUMO data on every run.

How it works:
1. Phase 1 runs baseline traffic.
2. Road snapshots are collected from SUMO and saved as output/road_action_training_data.csv
3. A RandomForestClassifier is trained on that dataset.
4. Training accuracy and report are saved in output/
5. Phase 2 uses the newly trained model for road-level decisions.

Run:
  python fix_routes.py
  python run_simulation.py --both --duration 600

Important:
- If your city folder is already working, do not run setup_map.py again.
- This build retrains the model every time you run the simulation.
