@echo on
REM Activate conda env and start backend from project root

REM 1) Activate conda environment
set "CONDA_ENV_NAME=textcad"
call conda activate "%CONDA_ENV_NAME%"
if errorlevel 1 (
  echo Failed to activate conda environment "%CONDA_ENV_NAME%".
  exit /b 1
)

REM 2) Set FreeCAD environment
set "FREECAD_LIB=C:\Program Files\FreeCAD 1.0\lib"
set "FREECAD_BIN=C:\Program Files\FreeCAD 1.0\bin"
set "PYTHONPATH=%FREECAD_LIB%;%PYTHONPATH%"
set "PATH=%FREECAD_BIN%;%PATH%"

REM 3) Vision provider setup (Fireworks via OpenAI-compatible route)
REM Set FIREWORKS_API_KEY in your shell or system env, then this script maps it.
if defined FIREWORKS_API_KEY set "VISION_OPENAI_API_KEY=%FIREWORKS_API_KEY%"

REM Optional defaults for Fireworks (can still override in the UI fields)
if not defined VISION_OPENAI_BASE_URL set "VISION_OPENAI_BASE_URL=https://api.fireworks.ai/inference/v1"
if not defined VISION_OPENAI_MODEL set "VISION_OPENAI_MODEL=accounts/fireworks/models/qwen3-vl-30b-a3b-thinking"
if not defined VISION_OPENAI_USE_FIREWORKS_PRESET set "VISION_OPENAI_USE_FIREWORKS_PRESET=true"

REM 4) Run backend
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
