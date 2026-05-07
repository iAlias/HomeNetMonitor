' ============================================================
' HomeNetMonitor — silent launcher
'
' Double-click this .vbs file to start HomeNetMonitor without
' any visible terminal / console window.
'
' The script locates launch.bat (in the same folder) and
' executes it hidden so that only the PyQt6 GUI window appears.
' Administrator privileges are handled inside launch.bat via
' PowerShell Start-Process -Verb RunAs.
' ============================================================

Dim oFSO, oShell, sScriptDir, sBatPath

Set oFSO   = CreateObject("Scripting.FileSystemObject")
Set oShell = CreateObject("WScript.Shell")

' Resolve the directory that contains this script
sScriptDir = oFSO.GetParentFolderName(WScript.ScriptFullName)
sBatPath   = sScriptDir & "\launch.bat"

If Not oFSO.FileExists(sBatPath) Then
    MsgBox "launch.bat not found at:" & vbCrLf & sBatPath, vbCritical, "HomeNetMonitor"
    WScript.Quit 1
End If

' Run hidden (0) — no console window is shown.
' The third argument (False) means this script does not wait for
' launch.bat to complete; the GUI runs independently.
oShell.Run Chr(34) & sBatPath & Chr(34), 0, False
