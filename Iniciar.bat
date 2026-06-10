@echo off
title Gestures Command V2 - Iniciando...
cls
echo ==========================================================
echo       GESTURES COMMAND V2 - INICIADOR AUTOMATICO
echo ==========================================================
echo.
echo [1/2] Verificando diretorio do projeto...
cd /d "%~dp0"

echo [2/2] Iniciando aplicacao via Ambiente Virtual (venv)...
echo.
echo ----------------------------------------------------------
echo -^> O Painel Web abrira no seu navegador: http://localhost:5123
echo -^> O icone de controle surgira na barra de tarefas (System Tray).
echo -^> Feche esta janela se desejar encerrar a aplicacao.
echo ----------------------------------------------------------
echo.

:: Execute the script using the local venv python interpreter
".\venv\Scripts\python.exe" -m src.gesture_keys

if %errorlevel% neq 0 (
    echo.
    echo [ERRO] Ocorreu um problema ao executar a aplicacao.
    echo Certifique-se de que as dependencias foram instaladas.
    pause
)
