Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Option Compare Database   'Сравнение строк средствами баз данных
Dim insert As Boolean
Private Sub Form_AfterDelConfirm(Status As Integer)
If Me.CurrentRecord > 1 Then
DoCmd.GoToRecord , , a_prev
formtxt = formtxt
Refresh
Else
bmsg = MsgBox("Отсутствуют формулы топлива", vbOKOnly)
End If
End Sub
Private Sub Form_AfterUpdate()
Dim w As Form, code As Double, topl As Form
Set w = Parent!wform.Form
Set topl = Parent!toplform.Form
cr = CurrentRecord
If insert Then
Requery
insert = False
End If
Parent.wform.SetFocus
Do While ((z(w.year) > topl.year) Or (z(w.year) = 0))
DoCmd.GoToRecord , , a_prev
Loop
code = w.numb1120
var = w!v
Do While (code = w.numb1120 And var = w!v)
w.NUST = w.NUST
DoCmd.GoToRecord , , A_NEXT
Loop
DoCmd.GoToRecord , , a_prev
Parent.toplform.SetFocus
If cr - 1 > 0 Then DoCmd.GoToRecord , , acNext, cr - 1
End Sub

Private Sub Form_BeforeInsert(Cancel As Integer)
insert = True
End Sub

Private Sub Form_BeforeUpdate(Cancel As Integer)
If InStr(Parent.wform.Form.filter, "year") > 0 Or Parent!Фильтр2 Then
bm = MsgBox("В этом режиме менять удельные и формулы топлива нельзя", vbOKOnly)
Cancel = 1
End If

End Sub