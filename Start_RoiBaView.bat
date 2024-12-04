@echo off
REM Open the Anaconda terminal, activate the environment, and run the script

REM Path to Anaconda installation
REM where conda
SET ANACONDA_PATH=C:\Users\Nils\miniconda3

REM Name of the Anaconda environment
SET ENV_NAME=viewer

REM Path to the Python script directory
SET SCRIPT_DIR=C:\UniFreiburg\Code\RoiBaView

REM Name of the Python script
SET SCRIPT_NAME=main.py

REM Activate the Anaconda environment
CALL "%ANACONDA_PATH%\Scripts\activate.bat" %ENV_NAME%

REM Change directory to the script location
CD /D %SCRIPT_DIR%

REM Run the Python script
python %SCRIPT_NAME%

REM Deactivate the environment (optional)
CALL conda deactivate

REM Exit the terminal automatically
EXIT