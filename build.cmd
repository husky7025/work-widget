@echo off
rem 업무위젯 묶음 만들기/올리기 — 키트 파이썬으로 build.py 를 실행한다 (서명 열쇠를 자격 증명 관리자에서 읽음)
chcp 65001 >nul
"%LOCALAPPDATA%\neis-automation-kit\.venv\Scripts\python.exe" "%~dp0build.py" %*
