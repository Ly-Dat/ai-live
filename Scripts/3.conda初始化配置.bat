@echo off

rem Get the current system user name
for /f %%i in ('whoami') do set "USERNAME=%%i"

rem If the user name cannot be obtained, default to "Administrator"
if "%USERNAME%"=="" set "USERNAME=Administrator"

rem Set the Conda config file path
set "CONDARC_PATH=C:\Users\%USERNAME%\.condarc"

rem Check whether the config file already exists
if exist "!CONDARC_PATH!" (
    echo Conda config file already exists, no initialization needed.
    exit /b
)

rem Create the Conda config file
echo Creating Conda config file...
echo channels: > "!CONDARC_PATH!"
echo   - defaults >> "!CONDARC_PATH!"

rem Initialize Conda
echo Initializing Conda...
conda init

echo Conda config initialization complete.
