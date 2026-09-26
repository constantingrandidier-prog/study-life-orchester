Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
rootDir = fso.GetParentFolderName(scriptDir)
pythonwPath = rootDir & "\.venv\Scripts\pythonw.exe"
agentPath = scriptDir & "\anki_sync_agent.py"
WshShell.CurrentDirectory = rootDir
WshShell.Run """" & pythonwPath & """ """ & agentPath & """", 0, False
