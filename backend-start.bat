@echo on
REM Activate conda env and start backend from project root

REM 1) Activate conda environment
call conda activate "C:\Users\adeel\OneDrive\100_Knowledge\203_TextCAD\Code\09_SimpltPrompt_Codex_mesh_n_shape2d_occ_mid_iso_drawwithzones_dimension_final"

REM 2) Set FreeCAD environment
set "FREECAD_LIB=C:\Program Files\FreeCAD 1.0\lib"
set "FREECAD_BIN=C:\Program Files\FreeCAD 1.0\bin"
set "PYTHONPATH=%FREECAD_LIB%;%PYTHONPATH%"
set "PATH=%FREECAD_BIN%;%PATH%"

REM 3) Run backend
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
