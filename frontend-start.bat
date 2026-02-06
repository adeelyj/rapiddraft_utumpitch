@echo on
REM Start frontend from project root

pushd "%~dp0"
cd web

npm install
npm run dev -- --host

popd
