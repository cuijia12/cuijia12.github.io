@echo off
chcp 65001 >nul
cd /d "%~dp0"
start "" pythonw serial_assistant.py
