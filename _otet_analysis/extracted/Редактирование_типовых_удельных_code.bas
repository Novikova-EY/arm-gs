Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Option Compare Database

Private Sub filter1_Change()
With typelist.Form
If filter1 = "Все" Then
.FilterOn = False
Else
If filter1 = "ПГУ-К" Then f = "type=""ПГУ"" or type=""ПГУ(ГУ)"""
If filter1 = "ПГУ-Т" Then f = "type=""ПГУ(Т)"" or type=""ПГУ(ГУ.Т)"""
If filter1 = "ГТУ-К" Then f = "type=""ГТ"""
If filter1 = "ГТУ-Т" Then f = "type=""ГТ(Т)"""
If filter1 = "ПГУ" Then f = "type like ""*ПГУ*"""
If filter1 = "ГТУ" Then f = "type like ""*ГТ*"""
.Filter = f
.FilterOn = True
End If
.OrderBy = "ordtype,nmin"
.OrderByOn = True
End With
End Sub

Private Sub Кнопка7_Click()
typelist.Form.Requery
End Sub

Private Sub Справка_Click()
txt = "Для ПГУ-К" & Chr(13) & "bk задается для 6500 часов" & Chr(13)
txt = txt & "bk для h часов:bkh=bk+Kh*(6500-h)/1000"
bm = MsgBox(txt, vbOKOnly, "справка")
End Sub