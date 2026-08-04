Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Option Compare Database

Private Sub Form_Open(Cancel As Integer)
Dim db As Database, cv As Recordset, sv As Recordset, s As String
Set db = DBEngine.Workspaces(0).Databases(0)
Set cv = db.OpenRecordset("Текущий_вариант", DB_OPEN_TABLE)
Set sv = RecordsetClone
s = "name='" & cv!Name & "'"
sv.FindFirst s
Bookmark = sv.Bookmark
End Sub