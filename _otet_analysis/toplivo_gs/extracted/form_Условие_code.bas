Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Option Compare Database
Private Sub Кнопка7_Click()
Dim list As ListBox, i As Integer, j As Integer, wtext As String
Dim wtext1 As String, field As String, condtext As String
Dim oldlist As ListBox
wtext1 = ""
savecond = ""
For j = 0 To Группы_условий.Pages.Count - 1
Set list = Группы_условий.Pages(j).Controls(0)
If list.ItemsSelected.Count > 0 Then
If savecond <> "" Then savecond = savecond & ";"
savecond = savecond & Группы_условий.Pages(j).Name
wtext = ""
For i = 0 To list.ListCount - 1
If list.Selected(i) Then
savecond = savecond & "," & i
field = list.Column(1, i)
condtext = list.Column(3, i)
If wtext <> "" Then wtext = wtext & IIf(Группы_условий.Pages(j).Name = "прочее", " AND ", " OR ")
If list.Column(3, i) = "query" Then
wtext = wtext & list.Column(2, i) & "=" & Format(list.Column(1, i), "0")
Else
If InStr(condtext, ";") > 0 Then
modif = Группы_условий.Pages(j).Controls("modif").Value
acond = split(condtext, ";")
condtext = acond(modif - 1)
savecond = savecond & ":" & modif
End If
wtext = wtext & repstring(condtext, "#", field)
If InStr(wtext, "@1") > 0 Then
Debug.Print "param" & Группы_условий.Pages(j).Name
wtext = Replace(wtext, "@1", Группы_условий.Pages(j).Controls("param" & Группы_условий.Pages(j).Name))
savecond = savecond & ":" & Группы_условий.Pages(j).Controls("param" & Группы_условий.Pages(j).Name)
End If
If InStr(wtext, "@2") > 0 Then
With Группы_условий.Pages(j).Controls("listrestr")
For i1 = 0 To .ListCount - 1
If .Column(0, i1) = list.Column(0, i) Then
restrtxt = .Column(1, i1)
savecond = savecond & ":" & restrtxt
restrtxt = Replace(restrtxt, "&", " and " & field)
wtext = Replace(wtext, "@2", restrtxt)
End If
Next i1
End With
End If ' @
End If
End If
Next
If wtext1 <> "" Then wtext1 = wtext1 & " AND "
tnot = ""
For ictrl = 0 To Группы_условий.Pages(j).Controls.Count - 1
If Группы_условий.Pages(j).Controls(ictrl).Name = "fnot" Then
If Группы_условий.Pages(j).Controls("fnot") Then tnot = " not "
End If
Next ictrl
wtext1 = wtext1 & tnot & "(" & wtext & ")"
End If
Next
Forms(OpenArgs)!cond = wtext1
If OpenArgs = "Справка" Then Forms(OpenArgs)!savecond = savecond
DoCmd.Close
End Sub