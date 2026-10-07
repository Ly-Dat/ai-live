@echo off

SET CONDA_PATH=.\Miniconda3

REM Activate the base environment
CALL %CONDA_PATH%\Scripts\activate.bat %CONDA_PATH%

cmd /k