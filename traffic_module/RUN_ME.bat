@echo off
title Delhi AQI Simulation (SUMO)
color 0A
echo.
echo  ============================================================
echo   Delhi AQI Traffic Simulation  --  SUMO
echo   Major Dhyan Chand Nagar / India Gate / Rajpath
echo  ============================================================
echo.

REM Check SUMO exists
if not exist "C:\Program Files (x86)\Eclipse\Sumo\bin\sumo-gui.exe" (
    if not exist "C:\Program Files\Eclipse\Sumo\bin\sumo-gui.exe" (
        if "%SUMO_HOME%"=="" (
            echo [ERROR] SUMO not found!
            echo.
            echo Install SUMO from: https://eclipse.dev/sumo/
            echo Then set: setx SUMO_HOME "C:\Program Files (x86)\Eclipse\Sumo"
            echo Open a NEW command prompt after setting SUMO_HOME.
            echo.
            pause
            exit /b 1
        )
    )
)

echo [OK] SUMO found

REM First-time setup
if not exist city\city.net.xml (
    echo.
    echo [SETUP] Running setup_map.py (downloads map, builds network)...
    echo This takes 2-5 minutes. Please wait.
    echo.
    python setup_map.py
    if errorlevel 1 (
        echo.
        echo [ERROR] Setup failed. See messages above.
        pause
        exit /b 1
    )
)

echo [OK] Network ready
echo.
echo Starting simulation...
echo.
python run_simulation.py --both --duration 600
echo.
echo ============================================================
echo Done! Check the output\ folder for your chart.
echo ============================================================
echo.
pause
