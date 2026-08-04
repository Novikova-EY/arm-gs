Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Option Compare Database
Private Sub Form_Current()
If z(VED) = 0 Then calc = 0 Else calc = 1
End Sub

Private Sub Qfixf_MouseDown(Button As Integer, Shift As Integer, X As Single, y As Single)
Dim db As Database, QfixT As Recordset
Set db = DBEngine.Workspaces(0).Databases(0)
Set QfixT = db.OpenRecordset("Фиксированное_тепло")
With QfixT
.Index = "code"
If Not Qfixf Then
.AddNew
!code = numb1120
.Update
Else
.Delete
End If
End With
nrec = CurrentRecord
Debug.Print nrec
Requery
DoCmd.GoToRecord , , acGoTo, nrec
End Sub