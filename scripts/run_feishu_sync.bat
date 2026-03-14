@echo off
setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set SKILL_DIR=%SCRIPT_DIR%..
set ENV_FILE=%SKILL_DIR%\.feishu_sync.env

if not exist "%ENV_FILE%" (
  echo Missing env file: %ENV_FILE%
  exit /b 1
)

for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
  if not "%%A"=="" (
    if /I not "%%A:~0,1%"=="#" (
      set "%%A=%%B"
    )
  )
)

where python >nul 2>nul
if %errorlevel%==0 (
  set PYTHON_BIN=python
) else (
  where python3 >nul 2>nul
  if %errorlevel%==0 (
    set PYTHON_BIN=python3
  ) else (
    echo python or python3 was not found in PATH
    exit /b 1
  )
)

"%PYTHON_BIN%" "%SCRIPT_DIR%sync_feishu_bitable.py" --app-id "%APP_ID%" --app-secret "%APP_SECRET%" --app-token "%APP_TOKEN%"
