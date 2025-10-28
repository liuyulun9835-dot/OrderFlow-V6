# Placeholder: rely on ATAS auto-restore last workspace. No GUI automation yet.
# Configure Windows Task Scheduler to run this file at logon/startup if needed.
$exe = "C:\Program Files\ATAS\ATAS.exe"
if (!(Get-Process -Name "ATAS" -ErrorAction SilentlyContinue)) { Start-Process -FilePath $exe }
