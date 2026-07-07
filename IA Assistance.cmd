@echo off
set ELECTRON_RUN_AS_NODE=
cd /d "%~dp0app-electron"
start "" "node_modules\electron\dist\electron.exe" .
