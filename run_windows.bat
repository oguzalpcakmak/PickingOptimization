@echo off
setlocal

cd /d "%~dp0"

set "BASE_PYTHON="
set "BASE_PYTHON_ARGS="
set "PYTHON_EXE="
set "PYTHON_ARGS="
set "REQ_FILE="

if exist "requirements.txt" set "REQ_FILE=requirements.txt"
if not defined REQ_FILE if exist "requirements-windows.txt" set "REQ_FILE=requirements-windows.txt"
if not defined REQ_FILE if exist "requirements-win.txt" set "REQ_FILE=requirements-win.txt"

if exist ".venv\Scripts\python.exe" (
  set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
  echo No local .venv found.
  choice /C YN /N /M "Create .venv now? [Y/N] "
  if errorlevel 2 goto choose_system_python

  call :find_python
  if not defined BASE_PYTHON (
    echo Could not find a base Python interpreter.
    echo Please install Python 3 for Windows first, then run this file again.
    goto end_fail
  )

  echo Creating virtual environment with:
  echo   %BASE_PYTHON% %BASE_PYTHON_ARGS%
  "%BASE_PYTHON%" %BASE_PYTHON_ARGS% -m venv .venv
  if errorlevel 1 (
    echo Failed to create .venv.
    goto end_fail
  )

  set "PYTHON_EXE=.venv\Scripts\python.exe"
  echo Virtual environment created.

  if defined REQ_FILE (
    echo Found dependency file: %REQ_FILE%
    choice /C YN /N /M "Install dependencies now? [Y/N] "
    if errorlevel 2 goto launcher

    "%PYTHON_EXE%" -m pip install --upgrade pip
    if errorlevel 1 (
      echo Failed while upgrading pip.
      goto end_fail
    )

    "%PYTHON_EXE%" -m pip install -r "%REQ_FILE%"
    if errorlevel 1 (
      echo Failed while installing dependencies from %REQ_FILE%.
      goto end_fail
    )
  ) else (
    echo No requirements file found. Skipping package installation.
    echo For the current heuristic solvers, this is usually fine.
  )
)

:choose_system_python
if not defined PYTHON_EXE (
  call :find_python
  if defined BASE_PYTHON (
    set "PYTHON_EXE=%BASE_PYTHON%"
    set "PYTHON_ARGS=%BASE_PYTHON_ARGS%"
  ) else (
    set "PYTHON_EXE=python"
    set "PYTHON_ARGS="
  )
)

:launcher
echo Starting Windows solver launcher...
echo.
"%PYTHON_EXE%" %PYTHON_ARGS% windows_solver_launcher.py
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%EXIT_CODE%"=="0" (
  echo Launcher finished with exit code %EXIT_CODE%.
) else (
  echo Launcher finished successfully.
)
echo.
pause
exit /b %EXIT_CODE%

:find_python
if exist ".venv\Scripts\python.exe" (
  set "BASE_PYTHON=.venv\Scripts\python.exe"
  set "BASE_PYTHON_ARGS="
  goto :eof
)
where py >nul 2>nul
if not errorlevel 1 (
  set "BASE_PYTHON=py"
  set "BASE_PYTHON_ARGS=-3"
  goto :eof
)
where python >nul 2>nul
if not errorlevel 1 (
  set "BASE_PYTHON=python"
  set "BASE_PYTHON_ARGS="
  goto :eof
)
set "BASE_PYTHON="
set "BASE_PYTHON_ARGS="
goto :eof

:end_fail
echo.
pause
exit /b 1
