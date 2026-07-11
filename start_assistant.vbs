' start_assistant.vbs
' Double-click this file to start the voice assistant completely silently
' - no console window, no VS Code needed.
'
' HOW TO USE:
' 1. Save this file directly inside your project folder:
'      C:\voice-vscode-assistant\start_assistant.vbs
' 2. Edit the two paths below (PYTHONW_PATH and SCRIPT_PATH) if your
'    Python install location or project folder is different.
' 3. Double-click it. The assistant starts in the background, tray icon
'    appears, no window flashes on screen.
' 4. To auto-start on login: press Win+R, type shell:startup, Enter,
'    then drop a shortcut to this .vbs file in that folder.
' start_assistant.vbs

Set objShell = CreateObject("WScript.Shell")

PYTHONW_PATH = "C:\voice-vscode-assistant\venv\Scripts\pythonw.exe"
SCRIPT_PATH  = "C:\voice-vscode-assistant\main.py"

objShell.Run """" & PYTHONW_PATH & """ """ & SCRIPT_PATH & """", 0, False