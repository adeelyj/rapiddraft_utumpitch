@echo on
REM Activate conda env and start backend from project root

REM 1) Activate conda environment
call conda activate "C:\Users\adeel\OneDrive\100_Knowledge\203_TextCAD\Code\09_SimpltPrompt_Codex_mesh_n_shape2d_occ_mid_iso_drawwithzones_dimension_final"

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
