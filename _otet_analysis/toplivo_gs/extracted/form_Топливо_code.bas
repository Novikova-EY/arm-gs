Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Option Compare Database

Private Sub Form_Close()
DoCmd.Close acForm, "Топливо(станции)"
End Sub

Private Sub Form_Current()
DoCmd.OpenForm "Топливо(станции)", acFormDS, , seltopl(toplcode) & ">0"
End Sub
Function seltopl(code)
If code = 6 Then seltopl = "don"
If code = 7 Then seltopl = "podm"
If code = 8 Then seltopl = "vork"
If code = 9 Then seltopl = "intin"
If code = 10.1 Then seltopl = "kuznt"
If code = 10.2 Then seltopl = "kuznss"
If code = 10.3 Then seltopl = "kuzngd"
If code = 10.4 Then seltopl = "kuznun"
If code = 11 Then seltopl = "sver"
If code = 12 Then seltopl = "chel"
If code = 13 Then seltopl = "kizel"
If code = 14 Then seltopl = "bashk"
If code = 15 Then seltopl = "ekib"
If code = 16 Then seltopl = "karag"
If code = 17 Then seltopl = "nazar"
If code = 18 Then seltopl = "ibor"
If code = 19 Then seltopl = "berez"
If code = 19.1 Then seltopl = "per"
If code = 20 Then seltopl = "hak"
If code = 21 Then seltopl = "tuv"
If code = 22 Then seltopl = "azey"
If code = 23 Then seltopl = "cher"
If code = 24 Then seltopl = "gusin"
If code = 25 Then seltopl = "tugn"
If code = 26 Then seltopl = "chit"
'If code = 27 Then seltopl = "ner"
If code = 27 Then seltopl = "yakut"
If code = 28 Then seltopl = "prim"
If code = 29 Then seltopl = "amur"
If code = 30 Then seltopl = "urg"
If code = 31 Then seltopl = "luch"
If code = 32 Then seltopl = "mag"
If code = 33 Then seltopl = "sah"
End Function

Private Sub Form_Open(Cancel As Integer)
filter = "toplcode<>0 and toplcode<>10"
FilterOn = True
End Sub

Private Sub Годы_Click()
With Forms("Топливо(станции)")
If Список_лет <> "Все" Then
filterall = .filter
.filter = filterall & " and year=" & Список_лет
Else
.filter = filterall
End If
.FilterOn = True
End With
End Sub

Private Sub Итог_Click()
sqlt = "Select year,sum(" & seltopl(toplcode) & ") as Сумма from [" & Forms("Топливо(станции)").RecordSource & "] group by year;"
Application.DoCmd.OpenForm "Итог", acFormDS
Forms("Итог").RecordSource = sqlt
Forms("Итог").Requery
End Sub