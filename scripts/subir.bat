@echo off
rem Atalho do subir.ps1: contorna a politica de execucao e a marca que o
rem Windows poe em arquivo vindo de .zip baixado. Aceita os mesmos
rem parametros: scripts\subir.bat -Rapido
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0subir.ps1" %*
