Option Explicit
Dim shell, fs, folder, python
Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
folder = fs.GetParentFolderName(WScript.ScriptFullName)
python = fs.BuildPath(folder, ".venv\Scripts\pythonw.exe")
If Not fs.FileExists(python) Then
  MsgBox "The local Python environment is missing. Complete the developer setup first.", 16, "Market View"
  WScript.Quit 1
End If
shell.CurrentDirectory = folder
shell.Run Chr(34) & python & Chr(34) & " -m market_view.server", 0, False
