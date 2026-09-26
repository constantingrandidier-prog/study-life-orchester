@echo off
cd /d "%~dp0\.."
start "" "%~dp0..\.venv\Scripts\pythonw.exe" "%~dp0anki_sync_agent.py"
exit
