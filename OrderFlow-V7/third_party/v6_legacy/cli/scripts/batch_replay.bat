@echo off
setlocal enabledelayedexpansion

set SYMBOL=%1
set START_DATE=%2
set END_DATE=%3

if "%SYMBOL%"=="" goto usage
if "%START_DATE%"=="" goto usage
if "%END_DATE%"=="" goto usage

if not exist logs mkdir logs
set LOG_FILE=logs\replay.log

echo [%%date%% %%time%%] Starting batch replay for %SYMBOL% from %START_DATE% to %END_DATE%>> %LOG_FILE%

for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "for($d=[datetime]::Parse('%START_DATE%'); $d -le [datetime]::Parse('%END_DATE%'); $d=$d.AddDays(1)){ $d.ToString('yyyy-MM-dd') }"`) do (
    echo Running ATAS replay for %%D >> %LOG_FILE%
    "C:\\Program Files\\ATAS\\atas.exe" --mode Replay --symbol %SYMBOL% --from %%D --to %%D --export-json >> %LOG_FILE% 2>&1
)

echo [%%date%% %%time%%] Batch replay completed for %SYMBOL%>> %LOG_FILE%

goto end

:usage
echo Usage: batch_replay.bat SYMBOL START_DATE END_DATE
exit /b 1

:end
endlocal
