import os
import ctypes

dll_dir = r"C:\voice-vscode-assistant\venv\Lib\site-packages\torch\lib"

print(f"Checking DLLs in: {dll_dir}\n")

for dll in os.listdir(dll_dir):
    if dll.lower().endswith(".dll"):
        path = os.path.join(dll_dir, dll)
        try:
            ctypes.WinDLL(path)
            print(f"[OK]     {dll}")
        except Exception as e:
            print(f"[FAILED] {dll}")
            print(e)
            print("-" * 50)