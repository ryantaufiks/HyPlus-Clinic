@echo off
cd /d "%~dp0monolith"
call venv\Scripts\activate.bat
start http://127.0.0.1:8002
python manage.py runserver 0.0.0.0:8002
