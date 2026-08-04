Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Option Compare Database
Option Explicit

Sub ПолеСоСписком4_AfterUpdate()
    ' Поиск записи, соответствующей этому элементу управления.
    Me.RecordsetClone.FindFirst "[NAME] = '" & Me![ПолеСоСписком4] & "'"
    Me.Bookmark = Me.RecordsetClone.Bookmark
End Sub


Private Sub Form_Open(Cancel As Integer)
With Forms("Расчет").Form
Часы.Form.RecordSource = !wname
'Список_станций.RowSourceType = "TABLE/QUERY"
'Список_станций.RowSource = "select name,numb1120 as numb from [" & !wname & "] where year=" & !byear & " and (" & !filter1 & ") order by numb1;"
End With
End Sub


Private Sub Кнопка15_Click()
Dim db As Database, R As Recordset, f As Form, c As String
Dim sqllist As String, r1 As Recordset
With Forms("Расчет").Form
sqllist = "select name,numb1120 as numb from [" & !wname & "] where year=" & !byear & " and (" & !filter1 & ") order by numb1;"
DoCmd.OpenForm "Выбор_из_списка", , , , , acDialog, sqllist & "/Фиксированные_часы"
End With
Set db = DBEngine.Workspaces(0).Databases(0)
Set f = Часы.Form
Debug.Print f.RecordSource
Set R = db.OpenRecordset(f.RecordSource, DB_OPEN_DYNASET)
c = "numb1120=" & fromlist
Debug.Print c
R.FindFirst c
R.Edit
R!HFIX = 1
R.Update
Requery
Set r1 = RecordsetClone
r1.FindFirst "numb=" & fromlist
Bookmark = r1.Bookmark
End Sub


Private Sub Кнопка17_Click()
Dim f As Form, sqlupd As String, r1 As Recordset, numbnext As Integer
Set r1 = RecordsetClone
r1.FindFirst "numb=" & numb
r1.MoveNext
numbnext = r1!numb
Set f = Часы.Form
sqlupd = "update [" & f.RecordSource & "] set hfix=0 where numb1120=" & numb & ";"
DoCmd.RunSQL sqlupd
Requery
Set r1 = RecordsetClone
r1.FindFirst "numb=" & numbnext
Bookmark = r1.Bookmark
End Sub