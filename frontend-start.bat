@echo on
REM Start frontend from project root

setlocal EnableExtensions EnableDelayedExpansion

pushd "%~dp0"

set "RUNTIME_DIR=%CD%\.rapiddev"
set "BACKEND_RUNTIME_FILE=%RUNTIME_DIR%\backend-runtime.cmd"
set "FRONTEND_PORT="
set "BACKEND_HEALTH_STATE="

call :pick_free_port 5173 FRONTEND_PORT
if errorlevel 1 (
  echo Failed to determine an open frontend port.
  popd
  endlocal
  exit /b 1
)

if defined VITE_API_BASE_URL (
  echo Using preconfigured VITE_API_BASE_URL=!VITE_API_BASE_URL!.
) else (
  if not exist "!BACKEND_RUNTIME_FILE!" (
    echo No local backend runtime file found at !BACKEND_RUNTIME_FILE!.
    echo Run backend-start.bat from this RapidDraft folder first.
    popd
    endlocal
    exit /b 1
  )

  call "!BACKEND_RUNTIME_FILE!"
  if not defined RAPIDDRAFT_BACKEND_PORT (
    echo Backend runtime file is missing RAPIDDRAFT_BACKEND_PORT.
    echo Delete !BACKEND_RUNTIME_FILE! and run backend-start.bat from this folder again.
    popd
    endlocal
    exit /b 1
  )
  if not defined RAPIDDRAFT_BACKEND_URL (
    echo Backend runtime file is missing RAPIDDRAFT_BACKEND_URL.
    echo Delete !BACKEND_RUNTIME_FILE! and run backend-start.bat from this folder again.
    popd
    endlocal
    exit /b 1
  )

  echo Waiting for backend health at !RAPIDDRAFT_BACKEND_URL!/health ...
  for /f %%S in ('powershell -NoProfile -Command "$url = $env:RAPIDDRAFT_BACKEND_URL + '/health'; $deadline = (Get-Date).AddSeconds(12); $healthy = $false; while ((Get-Date) -lt $deadline) { try { $response = Invoke-RestMethod -Uri $url -TimeoutSec 2; if ($response.status -eq 'ok') { $healthy = $true; break } } catch { }; Start-Sleep -Milliseconds 500 }; if ($healthy) { 'READY' } else { 'NOT_READY' }"') do set "BACKEND_HEALTH_STATE=%%S"
  if /I not "!BACKEND_HEALTH_STATE!"=="READY" (
    echo Backend runtime points to !RAPIDDRAFT_BACKEND_URL!, but /health did not become ready.
    echo Start backend-start.bat from this RapidDraft folder again or remove !BACKEND_RUNTIME_FILE! if it is stale.
    popd
    endlocal
    exit /b 1
  )

  set "VITE_API_BASE_URL=!RAPIDDRAFT_BACKEND_URL!"
  echo Using backend from this folder: !VITE_API_BASE_URL!
)

cd web

call npm install
if errorlevel 1 (
  echo npm install failed.
  popd
  endlocal
  exit /b 1
)

echo Starting frontend on port !FRONTEND_PORT!.
call npm run dev -- --host --port !FRONTEND_PORT!
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
