Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Option Compare Database


Private Sub Form_Close()
Dim db As Database, rng As DAO.Recordset
Set db = DBEngine.Workspaces(0).Databases(0)
wtable = Forms("Редактирование").Form!wname
sqlng = "select ved from [" & wtable & "] where ved=99;"
Set rng = db.OpenRecordset(sqlng)
If Not rng.EOF Then bm = MsgBox("Станция не разбита на группы оборудования", vbOKOnly)
rng.Close
End Sub

Private Sub liststan_AfterUpdate()
i = liststan.ListIndex
For j = 0 To OBOR.ListCount
If OBOR.Column(1, j) = liststan.Column(2, i) Then OBOR.Value = OBOR.Column(0, j)
Next j
End Sub

Private Sub OK_Click()
Dim db As Database, rcheck As DAO.Recordset, rcl As DAO.Recordset, codeob As Variant
Dim qupdata As QueryDef, qupdop As QueryDef, qud As QueryDef, qft As QueryDef
i = liststan.ListIndex
codeob = OBOR.Column(1, OBOR.ListIndex)
numb1120 = liststan.Column(1, i)
wtable = Forms("Редактирование").Form!wname
sqlcheck = "select numb1120 from [" & wtable & "] where numb1120=" & numb1120 & " and year=" & Form_Редактирование.byear & ";"
Set db = DBEngine.Workspaces(0).Databases(0)
Set rcheck = db.OpenRecordset(sqlcheck)
If Not rcheck.EOF Then
bm = MsgBox("Станция уже присутствует в данном варианте", vbOKOnly)
GoTo endp
End If
rcheck.Close
sqlcl = "select name,numb,main,comp,ведомство,ordnumb,oes,dep,er,obl,R from имена_станций where numb=" & numb1120 & ";"
Set rcl = db.OpenRecordset(sqlcl)
rcl.MoveFirst
If z(rcl!MAIN) > 0 Then
sqlcheck = Replace(sqlcheck, "numb1120=" & numb1120, "numb1120=" & rcl!MAIN)
Set rcheck = db.OpenRecordset(sqlcheck)
If rcheck.EOF Then
bm = MsgBox("Группа оборудования не может быть вставлена раньше станции", vbOKOnly)
GoTo endp
End If
rcheck.Close
End If
If rcl!COMP = 1 Then splitcomp = MsgBox("Будет ли станция разбита на группы оборудования?", vbYesNo)
If (z(rcl!COMP) = 0 Or rcl!COMP = 1 And splitcomp = vbNo) And z(codeob) = 0 Then
bm = MsgBox("Не задан тип оборудования", vbOKOnly)
GoTo endp
End If
If rcl!COMP = 1 And splitcomp = vbYes Then
v = 99
Else
If codeob < 8 Or codeob >= 20 And codeob <= 22 Then 'КЭС
If rcl!Ведомство = 1 Then v = 1 Else v = 4
Else 'ТЭЦ
If rcl!Ведомство = 1 Then v = 2 Else v = 3
End If
End If
ayears = split(Form_Редактирование.byear & "," & Form_Редактирование.years, ",")
Workspaces(0).BeginTrans
Call setoptions
If z(rcl!MAIN) > 0 Then
sqlrep = "update [" & wtable & "] set ved=0 where numb1120=" & rcl!MAIN & ";"
DoCmd.RunSQL (sqlrep)
sqlrep1 = "update [" & wtable & "] set obor=50 where numb1120=" & rcl!MAIN & ";"
DoCmd.RunSQL (sqlrep1)
sqlupgr = "UPDATE Списки_агрегатов as a SET a.grcode=grcodec where a.stcode=" & rcl!MAIN & ";"
End If
For i = 0 To UBound(ayears)
sqlins = "insert into [" & wtable & "] (name,year,numb1120,numb1,oes,dep,er,obl,obor,ved) values ("
sqlins = sqlins & """" & IIf(i = 0, rcl!Name, " ") & """," & ayears(i) & "," & numb1120 & "," & Str(rcl!ordnumb) & "," & rcl!oes & "," & rcl!DEP & "," & rcl!ER & "," & rcl!OBL & "," & IIf(IsNull(codeob), "null", codeob) & "," & v & ");"
DoCmd.RunSQL (sqlins)
Next i
If z(rcl!MAIN) > 0 And rcl!R = 1 Then
DoCmd.RunSQL (sqlupgr)
Set qupdata = db.QueryDefs("Копирование_данных_со_станции_на_группу")
sqlupdata = Replace(qupdata.SQL, "[код]", numb1120)
DoCmd.RunSQL (sqlupdata)
sqldeldop = "DELETE d.*,d.numb1120 FROM [Доп_угли(Схема)] AS d WHERE (((d.NUMB1120)=" & numb1120 & "));"
DoCmd.RunSQL (sqldeldop)
Set qupdop = db.QueryDefs("Копирование_доп_углей_со_станции_на_группу")
sqlupdop = Replace(qupdop.SQL, "[код станции]", rcl!MAIN)
sqlupdop = Replace(sqlupdop, "[код группы]", numb1120)
sqlupdop = Replace(sqlupdop, "[номер]", Replace(rcl!ordnumb, ",", "."))
DoCmd.RunSQL (sqlupdop)
sqldelud = "DELETE d.*,d.numb1120 FROM [Удельные(Схема)] AS d WHERE (((d.NUMB1120)=" & numb1120 & "));"
DoCmd.RunSQL (sqldelud)
Set qud = db.QueryDefs("Копирование_удельных_со_станции_на_группу")
sqlupud = Replace(qud.SQL, "[код станции]", rcl!MAIN)
sqlupud = Replace(sqlupud, "[код группы]", numb1120)
sqlupud = Replace(sqlupud, "[номер]", Replace(rcl!ordnumb, ",", "."))
DoCmd.RunSQL (sqlupud)
sqldelft = "DELETE d.*,d.numb1120 FROM [Формулы_топлива(Схема)] AS d WHERE (((d.NUMB1120)=" & numb1120 & "));"
DoCmd.RunSQL (sqldelft)
Set qft = db.QueryDefs("Копирование_формул_топлива_со_станции_на_группу")
sqlupft = Replace(qft.SQL, "[код станции]", rcl!MAIN)
sqlupft = Replace(sqlupft, "[код группы]", numb1120)
sqlupft = Replace(sqlupft, "[номер]", Replace(rcl!ordnumb, ",", "."))
DoCmd.RunSQL (sqlupft)
End If
Call resetoptions
With Forms("Редактирование")!wform.Form
.Requery
.RecordsetClone.FindFirst ("numb1120=" & numb1120)
.Bookmark = .RecordsetClone.Bookmark
End With
Workspaces(0).CommitTrans
endp:
End Sub