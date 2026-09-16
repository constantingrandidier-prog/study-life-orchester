Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\Constantin Grandidie\OneDrive - Universit?t Z?rich UZH\Desktop\Study-life-orcherster"
WshShell.Run """C:\Users\Constantin Grandidie\OneDrive - Universit?t Z?rich UZH\Desktop\Study-life-orcherster\.venv\Scripts\pythonw.exe"" bin\anki_sync_agent.py", 0, False
