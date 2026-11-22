@echo off
rem Uruchomienie prototypu #TuBijeAED na localhost (Windows).
rem   uruchom.bat         - start na http://localhost:8080/jury.html
rem   uruchom.bat reset   - najpierw usuwa baze demo i pliki z data\ (swiezy seed)
rem   set BEZ_PRZEGLADARKI=1 - nie otwieraj przegladarki
setlocal
chcp 65001 >nul
set "KORZEN=%~dp0"
set "APP=%KORZEN%2_prototyp_kod"
set "VENV=%KORZEN%.venv"
set "PORT=8080"
set "URL=http://localhost:%PORT%/jury.html"

if /i "%~1"=="reset" (
  echo ^>^> Reset: usuwam baze demo i pliki z "%APP%\data" ...
  if exist "%APP%\data" rmdir /s /q "%APP%\data"
  mkdir "%APP%\data"
)

set "PY="
where py >nul 2>nul && py -3 -c "import sys; sys.exit(0 if sys.version_info>=(3,11) else 1)" >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && python -c "import sys; sys.exit(0 if sys.version_info>=(3,11) else 1)" >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo BLAD: potrzebny jest Python 3.11 lub nowszy. Zainstaluj go z https://www.python.org/downloads/ ^(zaznacz "Add python.exe to PATH"^).
  exit /b 1
)
echo ^>^> Python znaleziony: %PY%

if not exist "%VENV%\Scripts\python.exe" (
  echo ^>^> Tworze srodowisko wirtualne w "%VENV%" ...
  %PY% -m venv "%VENV%"
  if errorlevel 1 (
    echo BLAD: nie udalo sie utworzyc .venv.
    exit /b 1
  )
)

echo ^>^> Instaluje zaleznosci ^(pierwsze uruchomienie moze potrwac^) ...
"%VENV%\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r "%APP%\requirements.txt"
if errorlevel 1 (
  echo BLAD: instalacja zaleznosci nie powiodla sie ^(sprawdz polaczenie z internetem^).
  exit /b 1
)

netstat -ano | findstr /r /c:":%PORT% .*LISTENING" >nul 2>nul
if not errorlevel 1 (
  echo BLAD: port %PORT% jest zajety. Zamknij dzialajacy serwer i sprobuj ponownie.
  exit /b 1
)

if not defined BEZ_PRZEGLADARKI (
  start "" /b cmd /c "timeout /t 3 /nobreak >nul & start "" %URL%"
)

echo ^>^> Start serwera: %URL%   ^(Ctrl+C zatrzymuje^)
cd /d "%APP%"
"%VENV%\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%
endlocal
