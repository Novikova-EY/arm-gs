Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Option Compare Database
Dim db As Database, cv As Recordset
Private Sub Form_Open(Cancel As Integer)
Set db = DBEngine.Workspaces(0).Databases(0)
Set cv = db.OpenRecordset("Текущий_вариант", DB_OPEN_TABLE)
ОЭС.Value = cv!OES
End Sub

Private Sub Кнопка4_Click()
Dim sv As Recordset
Dim work As QueryDef, dest As QueryDef, work1 As QueryDef, dopq As QueryDef, stoimq As QueryDef
Set sv = Список_вариантов.Form.RecordsetClone
sv.Bookmark = Список_вариантов.Form.Bookmark
If OpenArgs = "Редактирование_отчетных_данных" Then
Forms("Редактирование_отчетных_данных").Form!var = sv!wname
Forms("Редактирование_отчетных_данных").Form!varname = sv!alias
Forms("Редактирование_отчетных_данных").Form!OES = ОЭС.Value
Forms("Редактирование_отчетных_данных").Form!dop = sv!dopname
'добавила
Forms("Редактирование_отчетных_данных").Form!stoim = sv!stoimname
Form_Редактирование_отчетных_данных.years = sv!years
End If
If OpenArgs = "тепло" Then
Forms("Тепло").Form!var = sv!wname
Forms("Тепло").Form!OES = ОЭС.Value
End If
cv.Edit
For i = 0 To sv.Fields.Count - 1
cv.Fields(sv.Fields(i).Name) = sv.Fields(i).Value
Next i
cv!OES = ОЭС.Value
cv.Update
DoCmd.Close
End Sub