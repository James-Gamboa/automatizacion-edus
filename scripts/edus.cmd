@echo off
REM Always use the project venv Python (avoids Hermes/system Pillow mismatches)
set ROOT=%~dp0..
"%ROOT%\.venv\Scripts\python.exe" "%ROOT%\scripts\edus_cli.py" %*
