"""
mic_diagnostic.py
Standalone diagnostic — lists every audio input device Windows/PyAudio can see,
then tries to actually open each one to find out which (if any) works.
Run this BEFORE going back to listener.py or main.py.
"""

import speech_recognition as sr
import pyaudio


def list_devices():
    print("=" * 60)
    print("STEP 1: Listing all microphones PyAudio can detect")
    print("=" * 60)
    names = sr.Microphone.list_microphone_names()
    if not names:
        print("NO MICROPHONES FOUND AT ALL. This means either:")
        print("  - No microphone is physically connected, OR")
        print("  - PyAudio / its underlying driver (PortAudio) isn't installed correctly, OR")
        print("  - Windows is blocking access at the driver level")
        return []

    for i, name in enumerate(names):
        print(f"  Index {i}: {name}")
    return names


def find_working_device(names):
    print("\n" + "=" * 60)
    print("STEP 2: Trying to actually open each device")
    print("=" * 60)
    working = []
    for i in range(len(names)):
        try:
            mic = sr.Microphone(device_index=1)
            with mic as source:
                pass  # if this doesn't throw, the device opened successfully
            print(f"  Index {i} ({names[i]}): OPENED OK")
            working.append(i)
        except Exception as e:
            print(f"  Index {i} ({names[i]}): FAILED -> {type(e).__name__}: {e}")
    return working


def show_default_device():
    print("\n" + "=" * 60)
    print("STEP 3: Checking PyAudio's default input device")
    print("=" * 60)
    p = pyaudio.PyAudio()
    try:
        info = p.get_default_input_device_info()
        print(f"  Default input device: Index {info['index']} - {info['name']}")
    except IOError as e:
        print(f"  NO DEFAULT INPUT DEVICE SET: {e}")
        print("  This is very likely the root cause — Windows has no default recording device selected.")
    p.terminate()


if __name__ == "__main__":
    names = list_devices()
    if names:
        working = find_working_device(names)
        show_default_device()

        print("\n" + "=" * 60)
        print("RESULT")
        print("=" * 60)
        if working:
            print(f"These device indexes work: {working}")
            print(f"\nUse this in listener.py by changing sr.Microphone() to:")
            print(f"    sr.Microphone(device_index={working[0]})")
        else:
            print("No device could be opened successfully. Next steps:")
            print("  1. Right-click the speaker icon in Windows taskbar -> Sound settings")
            print("  2. Under Input, make sure a microphone is listed and selected")
            print("  3. Click 'Test your microphone' there and confirm the bar moves when you talk")
            print("  4. Settings -> Privacy & Security -> Microphone -> ensure both toggles are ON")
            print("     ('Microphone access' AND 'Let desktop apps access your microphone')")
            print("  5. If using a laptop with both a built-in mic and a USB/Bluetooth mic, try "
                  "disabling the one you're not using")
    else:
        print("\nFix device detection first (see causes above) before anything else will work.")