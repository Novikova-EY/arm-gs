Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Option Compare Database
Dim crdop As Integer, dopup As Boolean
Private Sub Form_AfterUpdate()
Dim w As Form, wr As DAO.Recordset, dopr As Recordset
Set w = Parent!wform.Form
Set wr = w.RecordsetClone
wr.Bookmark = w.Bookmark
ydop = year
crdop = Me.Form.CurrentRecord
dopup = True
Do While wr!year <> ydop
If wr!year < ydop Then wr.MoveNext Else wr.MovePrevious
Loop
w.Bookmark = wr.Bookmark
w!NUST = w!NUST
w.Refresh
End Sub

Private Sub Form_BeforeUpdate(Cancel As Integer)
If Me.NewRecord Then Me!numb1 = Parent!wform.Form!numb1
End Sub