@echo off
title SADAK AI v3
cd /d "%~dp0"
pip install flask pyjwt==2.8.0 opencv-python-headless pillow numpy -q --target .
python app.py
pause