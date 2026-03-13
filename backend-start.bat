@echo on
REM Activate conda env and start backend from project root

setlocal EnableExtensions EnableDelayedExpansion
pushd "%~dp0"

REM 1) Activate conda environment
set "CONDA_ENV_NAME=textcad"
call conda activate "%CONDA_ENV_NAME%"
if errorlevel 1 (
  echo Failed to activate conda environment "%CONDA_ENV_NAME%".
  popd
  endlocal
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

REM 4) Pick a backend port, preferring 8000 and falling forward if needed
set "BACKEND_PORT="
call :pick_free_port 8000 BACKEND_PORT
if errorlevel 1 (
  echo Failed to determine an open backend port.
  popd
  endlocal
  exit /b 1
)

set "RUNTIME_DIR=%CD%\.rapiddev"
set "BACKEND_RUNTIME_FILE=%RUNTIME_DIR%\backend-runtime.cmd"
set "RAPIDDRAFT_BACKEND_PORT=!BACKEND_PORT!"
set "RAPIDDRAFT_BACKEND_URL=http://127.0.0.1:!BACKEND_PORT!"

if "!BACKEND_PORT!"=="8000" (
  echo Starting backend on port !BACKEND_PORT!.
) else (
  echo Port 8000 is already in use. Starting backend on port !BACKEND_PORT!.
)

if not exist "!RUNTIME_DIR!" mkdir "!RUNTIME_DIR!"
(
  echo @set RAPIDDRAFT_BACKEND_PORT=!RAPIDDRAFT_BACKEND_PORT!
  echo @set RAPIDDRAFT_BACKEND_URL=!RAPIDDRAFT_BACKEND_URL!
) > "!BACKEND_RUNTIME_FILE!"
echo Recorded backend runtime in !BACKEND_RUNTIME_FILE!.

REM 5) Run backend
python -m uvicorn server.main:app --host 0.0.0.0 --port !BACKEND_PORT! --reload
set "EXIT_CODE=!ERRORLEVEL!"

popd
endlocal & exit /b %EXIT_CODE%

:pick_free_port
set "START_PORT=%~1"
set "TARGET_VAR=%~2"
set /a "CANDIDATE_PORT=%START_PORT%"
:pick_free_port_loop
set "PORT_STATE="
for /f %%S in ('powershell -NoProfile -Command "try { $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, !CANDIDATE_PORT!); $listener.Start(); $listener.Stop(); 'FREE' } catch { 'BUSY' }"') do set "PORT_STATE=%%S"
if /I "!PORT_STATE!"=="FREE" (
  set "%TARGET_VAR%=!CANDIDATE_PORT!"
  exit /b 0
)
set /a "CANDIDATE_PORT+=1"
goto pick_free_port_loop
