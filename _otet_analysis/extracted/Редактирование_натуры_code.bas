Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Option Compare Database

Private Sub Form_Open(Cancel As Integer)
Натура.Form.Filter = "year=" & годы & " and OES=" & ОЭС
Натура.Form.FilterOn = True
Натура.Form.OrderBy = "obl,numb1,year"
Натура.Form.OrderByOn = True
End Sub


Private Sub Вставка_Click()
If годы = "Все" Then
bm = MsgBox("Не установлен год", vbOKOnly)
GoTo endp
End If
'DoCmd.OpenForm ("Выбор_из_списка"), , , , , acDialog, "select name,numb from имена_станций;/Редактирование_натуры"
DoCmd.OpenForm ("Выбор_из_списка"), , , , , acDialog, "select name,numb from имена_станций where obl=" & Натура.Form!OBL & " order by ordnumb;/Редактирование_натуры"
Натура.SetFocus
n = Натура.Form.CurrentRecord
sqlins = "insert into Натура99 (name,year,numb1120,numb1,oes,obl,er) "
sqlins = sqlins & "select name," & годы & " as year,numb,ordnumb,oes,obl,er from имена_станций where numb=" & fromlist & ";"
Debug.Print sqlins
DoCmd.RunSQL (sqlins)
Натура.Form.Requery
DoCmd.GoToRecord , , acGoTo, n
endp:
End Sub

Private Sub Годы_AfterUpdate()
Call Уголь_AfterUpdate
End Sub
Private Sub ОЭС_AfterUpdate()
Call Уголь_AfterUpdate
End Sub


Private Sub Уголь_AfterUpdate()
If годы = "все" And уголь = "все" And ОЭС = "все" Then
Натура.Form.FilterOn = False
GoTo endp
End If
If уголь = "все" Then
Натура.Form.Filter = "year=" & годы & " and OES=" & ОЭС
Else
    If годы = "все" Then
    Натура.Form.Filter = уголь.Column(1) & ">0"
    Else
    Натура.Form.Filter = "year=" & годы & " and " & уголь.Column(1) & ">0"
    End If
End If
Натура.Form.FilterOn = True
endp:
Натура.Form.OrderBy = "obl,numb1,year"
Натура.Form.OrderByOn = True
End Sub