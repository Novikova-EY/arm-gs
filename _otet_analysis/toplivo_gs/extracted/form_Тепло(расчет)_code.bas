Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Option Compare Database

Private Sub Form_AfterUpdate()
Refresh
End Sub

Private Sub Form_BeforeUpdate(Cancel As Integer)
Dim stan As Form
Set stan = Parent.Form
If stan!calc = 0 Then B = MsgBox("Станция разбита на групп оборудования.Изменения учтены не будут")
End Sub
Function ppf(y As Double)
Dim Q() As Double, R As Recordset
Set R = Me.RecordsetClone
ny = R.RecordCount
ReDim Q(ny - 1)
R.MoveFirst
If R!year = y Then
ppf = 0
GoTo endppf
End If
Do While (R!year <> y)
Qprev = R!Q
R.MoveNext
Loop
If Qprev <> 0 Then ppf = (R!Q - Qprev) / Qprev * 100 Else ppf = 0
endppf:
End Function