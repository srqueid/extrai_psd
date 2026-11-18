@echo off
title Extrator de PSD
chcp 65001 > nul
cls
echo ===================================================================
echo             EXTRATOR DE IMAGENS E CAMADAS PSD (PHOTOSHOP)
echo ===================================================================
echo.
echo Escolha qual interface deseja abrir:
echo.
echo   [1] Interface Web Moderna (Recomendado - Navegador com Drag & Drop)
echo   [2] Interface Desktop Nativa (Janela Windows Tkinter)
echo   [3] Gerar novo PSD de exemplo para testes (banner_exemplo.psd)
echo   [4] Sair
echo.
set /p opcao="Digite o número da opção (1, 2, 3 ou 4) [Padrão: 1]: "

if "%opcao%"=="" set opcao=1
if "%opcao%"=="1" goto web
if "%opcao%"=="2" goto desktop
if "%opcao%"=="3" goto exemplo
if "%opcao%"=="4" goto fim

:web
echo.
echo Iniciando Interface Web...
python app.py
goto fim

:desktop
echo.
echo Iniciando Interface Desktop...
python gui_desktop.py
goto fim

:exemplo
echo.
echo Gerando PSD de exemplo...
python gerar_psd_exemplo.py
echo.
pause
goto fim

:fim
