Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Option Compare Database
Dim ins As Boolean
Private Sub Form_AfterInsert()
For i = 0 To [Type].ListCount - 1
If [Type].Column(0, i) = [Type] Then
ordtype = [Type].Column(1, i)
End If
Next i
ins = True
End Sub

Private Sub Form_AfterUpdate()
If ins Then
Requery
ins = False
End If
End Sub