@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  Scout - gerador de executavel
echo ============================================
echo.

rem localiza um uv utilizavel: PATH, modulo do python ou instalacao por usuario.
rem A instalacao no Python do sistema pode ficar sem o uv.exe - antivirus ou
rem falta de admin bloqueiam a gravacao em C:\Python311\Scripts - por isso a
rem instalacao de fallback e sempre --user, que nao depende de permissao.
set "UV="
uv --version >nul 2>&1
if not errorlevel 1 set "UV=uv"
if not defined UV python -m uv --version >nul 2>&1
if not defined UV if not errorlevel 1 set "UV=python -m uv"
if not defined UV if exist "%APPDATA%\Python\Python311\Scripts\uv.exe" set "UV=%APPDATA%\Python\Python311\Scripts\uv.exe"
if not defined UV (
    echo [0/2] Instalando uv no perfil do usuario...
    python -m pip install --quiet --user uv
)
if not defined UV if exist "%APPDATA%\Python\Python311\Scripts\uv.exe" set "UV=%APPDATA%\Python\Python311\Scripts\uv.exe"
if not defined UV (
    echo Nao foi possivel encontrar nem instalar o uv.
    echo Rode manualmente num terminal:  python -m pip install --user uv
    goto :erro
)

echo [1/2] Sincronizando dependencias (uv sync)...
%UV% sync --group dev
if errorlevel 1 goto :erro

echo.
echo [2/2] Gerando executavel (PyInstaller)...
%UV% run pyinstaller --onefile --console --clean --noconfirm --name scout src\scout\__main__.py
if errorlevel 1 goto :erro

echo.
echo ============================================
echo  OK! Executavel gerado em:
echo  %~dp0dist\scout.exe
echo.
echo  Teste rapido (num terminal):
echo  dist\scout.exe analisar ADSH11
echo ============================================
echo.
pause
exit /b 0

:erro
echo.
echo *** BUILD FALHOU - veja as mensagens acima. ***
echo.
pause
exit /b 1
