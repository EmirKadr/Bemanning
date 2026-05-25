@echo off
set ASSIGN_DB_PATH=%~dp0data\database\Database.db
cd /d "%~dp0"
py run.py
