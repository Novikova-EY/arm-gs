Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Public byear As Double, years As String, fltroes As String
Private Declare Function intWNetGetUser Lib "mpr.dll" Alias "WNetGetUserA" (ByVal lpname As String, ByVal lpUserName As String, lpnLength As Long) As Long
Dim cv As DAO.Recordset, prevvar As Integer, asf As String, ff As String, fltr3 As String

Private Sub Agr_Click()
Dim tform As Form, trs As DAO.Recordset
With wform.Form
DoCmd.OpenForm "Турбины", acFormDS, , "grcode=" & !numb1120
wform.SetFocus
Do While !year <> byear
DoCmd.GoToRecord , , acPrevious
Loop
codest = !numb1120
bm = .Bookmark
DoCmd.GoToRecord , , acNext
Do While (!numb1120 = codest) And Not (.RecordsetClone.EOF) And (z(!year) <> 0)
Set tform = Forms("Турбины")
Set trs = tform.RecordsetClone
nturb = trs.RecordCount
sumnu = 0
sumnr = 0
sumnt = 0
trs.MoveFirst
For i = 1 To nturb
na = z(trs(Format(!year, "#")))
If trs("ur") = 1 Then sumnu = sumnu + na Else sumnr = sumnr + na
If na > 0 And trs("ur") = 1 Then sumnt = sumnt + z(trs("nt"))
trs.MoveNext
Next i
!NUST = sumnu
!NR = sumnr
!NT = sumnt
Debug.Print !year; sumt
DoCmd.GoToRecord , , acNext
Loop
.Bookmark = bm
End With
End Sub

Private Sub Dopform_Enter()
asf = "dop"
End Sub

Private Sub dummy_AfterUpdate()
With wform.Form
If dummy = True Then
For i = 0 To .Section(0).Controls.Count - 1
.Section(0).Controls(i).ColumnHidden = False
Next i
Else
For i = 0 To .Section(0).Controls.Count - 1
fname = .Section(0).Controls(i).Name
If .Section(0).Controls(i).Tag = "key" Then
.Section(0).Controls(i).ColumnHidden = False
Else
If .Section(1).Controls("sum" & fname) > 0 Then
.Section(0).Controls(i).ColumnHidden = False
Else
.Section(0).Controls(i).ColumnHidden = True
End If
End If
Next i
End If
End With
End Sub
Private Sub Form_Close()
Dim dbchange As Database, rchange As DAO.Recordset
If fchange = 1 Then
Set dbchange = DBEngine.OpenDatabase("f:\Базы данных\изменения")
Set rchange = dbchange.OpenRecordset("изменения")
rchange.Edit
rchange(cv!alias) = Date & " " & Time
rchange.Update
End If
End Sub

Private Sub Form_Open(Cancel As Integer)
Dim db As Database, w As DAO.Recordset
DoCmd.Maximize
Set db = Application.DBEngine.Workspaces(0).Databases(0)
Set cv = db.OpenRecordset("Текущий_вариант", DB_OPEN_DYNASET)
retry:
fchange = 0
If cv!Locked = 1 Then
msgcode = MsgBox("Набор данных занят", vbRetryCancel)
If msgcode = vbCancel Then
Application.DoCmd.Close
GoTo endp
End If
cv.Requery
GoTo retry
End If
Application.DoCmd.OpenForm "Выбор_варианта", , , , , acDialog
byear = cv!byear
byearf = byear
years = cv!years
wform.Form.RecordSource = "SELECT w.*, c.NAME as name1,main FROM [" & cv!wname & "] AS w INNER JOIN Имена_станций AS c ON w.NUMB1120 = c.NUMB;"
wname = cv!wname
uform.Form.RecordSource = cv!uname
toplform.SourceObject = "topl"
toplform.Form.RecordSource = cv!topleur
dopform.Form.RecordSource = cv!dopname
Set w = wform.Form.RecordsetClone
If cv!oes = 0 Then
wform.Form.filter = "(v=0 or v=1)"
Else
Select Case cv!oes
    Case 7
        wform.Form.filter = "(oes=7 or oes=12) and (v=0 or v=1)"
    Case 4
        wform.Form.filter = "(oes=4 or oes=13) and (v=0 or v=1)"
    Case 8
        wform.Form.filter = "(obl=10) and (v=0 or v=1)"
    Case 13
        wform.Form.filter = "(obl=77) and (v=0 or v=1)"
    Case 12
        wform.Form.filter = "(numb1120=721) and (v=0 or v=1)"
    Case Else
        wform.Form.filter = "oes=" & cv!oes & " and (v=0 or v=1)"
End Select
End If
fltroes = wform.Form.filter
prevvar = 1
listvar = 1
If cv!vars <> "no" Then
listvar.RowSource = cv!vars
listvar.Visible = True
comvars = split(cv!comvars, ";")
ctt = ""
For j = 0 To UBound(comvars)
ctt = ctt & Chr(13) & comvars(j)
Next j
listvar.ControlTipText = ctt
Добавить.Enabled = True
Удалить.Enabled = True
Else
listvar = 1
End If
wform.Form.FilterOn = True
wform.Form.OrderBy = "obl,numb1,year"
wform.Form.OrderByOn = True
cv.Edit
cv!Locked = 0
cv.Update
Form_W.msgstanu = 0
Form_W.msgstant = 0
endp:
End Sub

Private Sub itog_Click()
Dim argst As String, f As field
Dim sqlm As String, sqlt As String, fname As String, tname As String, oes As String
Set db = DBEngine.Workspaces(0).Databases(0)
If asf = "dop" Then dopform.SetFocus Else wform.SetFocus
fname = Screen.ActiveControl.Name
If InStr(",name,year,numb1120,numb1,v,eurt,turt,", "," & fname & ",") > 0 Then
MsgBox ("Этот тип данных не суммируется")
GoTo enditog
End If
If asf = "dop" And Вид_итога = "КЭС по типам" Then
MsgBox (fname & " в режиме КЭС по типам не суммируется")
GoTo enditog
End If
argst = Screen.ActiveControl.Name & ";" & wname & ";" & wform.Form.filter
If Вид_итога = "ОЭС" Or Вид_итога = "Обл" Then
If InStr(fltroes, "oes") > 0 Then
sqlm = "select w.oes,w.year,sum(#field) as Сумма from ([#table] as w left join [#dop] as d on w.numb1120=d.numb1120 and w.year=d.year and w.v=d.v) inner join имена_станций on w.numb1120=имена_станций.numb where (ved>0 and (w.v=0 or w.v=" & listvar & ") and #oes " & IIf(фильтр3 Or Фильтр1 <> "Все", "and (" & cond & ")", "") & ") group by w.oes,w.year;"
Else
sqlm = "select w.year,sum(#field) as Сумма from ([#table] as w left join [#dop] as d on w.numb1120=d.numb1120 and w.year=d.year and w.v=d.v) inner join имена_станций on w.numb1120=имена_станций.numb where (ved>0 and (w.v=0 or w.v=" & listvar & ")" & IIf(фильтр3 Or Фильтр1 <> "Все", "and (" & cond & ")", "") & ") group by w.year;"
End If
End If
If Вид_итога = "КЭС по типам" Then
If InStr(fltroes, "oes") > 0 Then
sqlm = "Transform sum(#field) as Сумма select iif(obor=21,""ПГУ"",iif(obor=20,""ГТУ"",iif(obor=22,""Диз"",iif(obor=23,""Дет"",""ПСУ"")))) as type from [#table] as w where ((ved=1 or ved=4) and (v=0 or v=" & listvar & ") and #oes) group by iif(obor=21,""ПГУ"",iif(obor=20,""ГТУ"",iif(obor=22,""Диз"",iif(obor=23,""Дет"",""ПСУ"")))) pivot year;"
Else
sqlm = "Transform sum(#field) as Сумма select iif(obor=21,""ПГУ"",iif(obor=20,""ГТУ"",iif(obor=22,""Диз"",iif(obor=23,""Дет"",""ПСУ"")))) as type from [#table] as w where ((ved=1 or ved=4) and (v=0 or v=" & listvar & ")) group by iif(obor=21,""ПГУ"",iif(obor=20,""ГТУ"",iif(obor=22,""Диз"",iif(obor=23,""Дет"",""ПСУ"")))) pivot year;"
End If
End If
If Вид_итога = "Станция" Then
If IsNull(wform!MAIN) Then GoTo enditog
sqlm = "select null as oes,w.year,sum(#field) as Сумма from ([#table] as w left join [#dop] as d on w.numb1120=d.numb1120 and w.year=d.year and w.v=d.v) inner join имена_станций on w.numb1120=имена_станций.numb where (ved>0 and (w.v=0 or w.v=" & listvar & ") and main=" & wform.Form!MAIN & ") group by w.year;"
End If
args = split(argst, ";")
tname = args(1)
oes = "w.oes=" & wform.Form!oes
dopname = dopform.Form.RecordSource
sqlt = Replace(sqlm, "#field", fname)
sqlt = Replace(sqlt, "#table", tname)
sqlt = Replace(sqlt, "#dop", dopname)
If Вид_итога = "ОЭС" Or Вид_итога = "КЭС по типам" Then sqlt = Replace(sqlt, "#oes", oes)
If Вид_итога = "Обл" Then sqlt = Replace(sqlt, "#oes", "w.OBL=" & wform.Form!OBL)
If Вид_итога = "ОЭС" Or Вид_итога = "Обл" Or Вид_итога = "Станция" Then
Application.DoCmd.OpenForm "Итог", acFormDS
Forms("Итог").RecordSource = sqlt
Forms("Итог").Requery
Else
Application.DoCmd.OpenForm "ИтогХ", acFormDS
Forms("ИтогХ").RecordSource = sqlt
Forms("ИтогХ").Requery
End If
enditog:
End Sub



Private Sub Q_Click()
Dim Qr As DAO.Recordset, opor As Form, rop As DAO.Recordset
DoCmd.OpenForm ("Q")
sqlq = "select year,q,qotr,nt from [" & wname & "] where numb1120=" & wform.Form!numb1120 & ";"
sqlqop = Replace(sqlq, ";", " and (year=2006 or year=2010 or year=2015 or year=2020);")
Set Qr = CurrentDb.OpenRecordset(sqlq)
Set opor = Forms("Q").Form!Qop.Form
opor.RecordSource = sqlqop
opor.OrderBy = "year"
opor.OrderByOn = True
Set rop = opor.RecordsetClone
p = Forms("Q").Form!p
If IsNull(p) And IsNull(Forms("Q")!H) And Forms("Q")!var < 3 Then
bmsg = MsgBox("Введите данные и снова нажмите кнопку Q", vbOKOnly)
GoTo Skip
End If
Qr.MoveFirst
qrp = Qr!Q
yp = Qr!year
If IsNull(Forms("Q")!potr) Then potr = Qr!QOTR / Qr!Q * 100 Else potr = Forms("Q")!potr
Do While Not (Qr.EOF)
Qr.MoveNext
If Qr.EOF Then GoTo Skip
qrc = Qr!Q
If Forms("Q")!sely And Qr!year > z(Forms("Q")!Y1) And Qr!year < z(Forms("Q")!Y2) Or Not (Forms("Q")!sely) Then         'не все годы
If Forms("Q")!var = 4 Then 'интерполяция
rop.FindFirst "year>=" & Format(Qr!year, "#")
opor.Bookmark = rop.Bookmark
p = opor!pa
If (rop!year <> Qr!year) And opor!k > 0 Then
qrc = qrp * (1 + (Qr!year - yp) * p / 100)
qotrc = qrc * potr / 100
Else
qrc = Qr!Q
qotrc = Qr!QOTR
End If
End If ' интерполяция
If Forms("Q")!var = 1 Then  'по процентам
qrc = qrp * (1 + (Qr!year - yp) * p / 100)
qotrc = qrc * potr / 100
End If 'по процентам
If Forms("Q")!var = 2 Then 'по часам
qotrc = Qr!NT * Forms("Q")!H / 1000
qrc = qotrc / potr * 100
If Not (IsNull(Forms("Q")!pmax)) Then
If qrc > qrp * (1 + Forms("Q")!pmax / 100) Then
qrc = qrp * (1 + Forms("Q")!pmax / 100)
qotrc = qrc * potr / 100
End If
End If
End If 'по часам
If Forms("Q")!var = 3 Then 'только Qотр
qrc = Qr!Q
qotrc = qrc * potr / 100
End If 'только Qотр
Qr.Edit
Qr!Q = qrc
Qr!QOTR = qotrc
Qr.Update
End If 'не все годы
qrp = qrc
yp = Qr!year
Loop
Skip:
End Sub

Private Sub Udelnie_Click()
Dim w As Form, code As Double, U As Form
Set w = wform.Form
Set U = uform.Form
cr = CurrentRecord
DoCmd.Requery
wform.SetFocus
Do While ((z(w.year) > U.year) Or (z(w.year) = 0))
DoCmd.GoToRecord , , a_prev
Loop
code = w.numb1120
var = w!v
Do While (code = w.numb1120 And var = w!v)
w.NUST = w.NUST
DoCmd.GoToRecord , , A_NEXT
i = i + 1
Loop
DoCmd.GoToRecord , , a_prev
uform.SetFocus
If cr - 1 > 0 Then DoCmd.GoToRecord , , acNext, cr - 1
End Sub

Private Sub wform_Enter()
asf = "stan"
End Sub

Private Sub Вставка_Click()
DoCmd.OpenForm "Список_станций"
Forms("Список_станций").Form!liststan.RowSource = "select name,numb,тип from имена_станций where obl=" & wform.Form!OBL & " order by ordnumb;"
End Sub


Private Sub Годы_Click()
DoCmd.OpenForm ("Годы")
End Sub

Private Sub Диаграмма_Click()
flist = "select name from список_полей where table=""w"" or table=""d"" or table=""f"";"
fromlist = ""
DoCmd.OpenForm ("Выбор_из_списка_м"), , , , , acDialog, flist & "/Редактирование"
If fromlist <> "" Then DoCmd.OpenForm "Диаграмма", , , "numb=" & wform.Form!numb1120
End Sub

Private Sub Добавить_Click()
Dim stcode As Double, var As Integer
If wform.Form!v > 0 Then
msg = MsgBox("Варианты уже существуют", vbOKOnly)
GoTo endadd
End If
If z(wform.Form!VED) = 0 Then
msg = MsgBox("Варианты создаются только для групп оборудования", vbOKOnly)
GoTo endadd
End If
stcode = wform.Form!numb1120
mainsql = "select main from имена_станций where numb=" & wform.Form!numb1120 & ";"
Set rmain = CurrentDb.OpenRecordset(mainsql)
rmain.MoveFirst
Workspaces(0).BeginTrans
Call setoptions
Call copyvar(wname, stcode, z(rmain!MAIN))
Call copyvar(dopform.Form.RecordSource, stcode, z(rmain!MAIN))
Call copyvar(uform.Form.RecordSource, stcode, 0)
Call copyvar(toplform.Form.RecordSource, stcode, 0)
Workspaces(0).CommitTrans
Call resetoptions
endadd:
End Sub

Private Sub Кнопка38_Click()
Form_Open (Cancel)
End Sub

Private Sub Кнопка40_Click()
Dim w As Form
Set w = wform.Form
w.filter = w.filter & "and ved=1"
w.FilterOn = True
w.OrderBy = "numb1"
w.OrderByOn = True
End Sub


Private Sub Копирование_Click()
Dim qdata As QueryDef, qdop As QueryDef
With wform.Form
Set qdata = CurrentDb.QueryDefs("Копирование_показателей")
sqldata = Replace(qdata.SQL, "[код]", !numb1120)
DoCmd.RunSQL (sqldata)
Set qdop = CurrentDb.QueryDefs("Копирование_доп_углей")
sqldop = Replace(qdop.SQL, "[код]", !numb1120)
DoCmd.RunSQL (sqldop)
End With
End Sub

Private Sub Отчет_Click()
flist = "select name from список_полей where table=""w"" or table=""d"" or table=""f"";"
fromlist = ""
DoCmd.OpenForm ("Выбор_из_списка_м"), , , , , acDialog, flist & "/Редактирование"
If fromlist <> "" Then DoCmd.OpenReport ("Для_Редактирования"), acViewPreview
End Sub

Private Sub Справка_Click()
DoCmd.OpenForm ("Диалог_для_справки")
End Sub

Private Sub Сумма_Click()
Dim db As Database, stanf As DAO.Recordset, sumg As DAO.Recordset, dop As DAO.Recordset
Dim fndx() As Integer, sumgq As QueryDef, sumgsql As String
Set db = DBEngine.Workspaces(0).Databases(0)
Set stanf = db.OpenRecordset(wname)
Set dop = db.OpenRecordset(dopform.Form.RecordSource)
Set sumgq = db.QueryDefs("Сумма_частей(выборка)")
sumgsql = sumgq.SQL
If cv!oes <> 0 Then sumgsql = Replace(sumgsql, "(s.OES)<100", "s.oes=" & wform!oes)
sumgsql = Replace(sumgsql, "Рабочий_для_суммы(доп_угли)", dopform.Form.RecordSource)
sumgsql = Replace(sumgsql, "Рабочий_для_суммы", "[" & wname & "]")
sumgsql = Replace(sumgsql, "(s.v)=1", "(s.v)=" & listvar)
Set sumg = db.OpenRecordset(sumgsql)
nfs = stanf.Fields.Count
nfd = dop.Fields.Count
nfg = sumg.Fields.Count
ReDim fndx(nfg - 1, 1)
For j = 0 To nfg - 1
For j1 = 0 To nfs - 1
If stanf.Fields(j1).Name = sumg.Fields(j).Name Then GoTo instan
Next j1
For j1 = 0 To nfd - 1
If dop.Fields(j1).Name = sumg.Fields(j).Name Then GoTo indop
Next j1
fndx(j, 0) = 0
fndx(j, 1) = 0
GoTo nxtj
indop:
fndx(j, 0) = j1
fndx(j, 1) = 2
GoTo nxtj
instan:
fndx(j, 0) = j1
fndx(j, 1) = 1
nxtj:
Next j
stanf.Index = "numb2"
dop.Index = "numb2"
sumg.MoveFirst
pb.Max = 100
pb.Min = 0
For i = 1 To sumg.RecordCount
stanf.Seek "=", sumg!numb1120, sumg!v, sumg!year
stanf.Edit
bdop = False
For j = 0 To nfg - 1
If InStr(",NAME,YEAR,NUMB1120,oes,numb1,v,", "," & sumg.Fields(j).Name & ",") = 0 Then
If fndx(j, 1) = 1 Then
stanf.Fields(fndx(j, 0)).Value = sumg.Fields(j)
End If
If fndx(j, 1) = 2 And z(sumg.Fields(j)) > 0 Then bdop = True
End If
Next j
stanf.Update
dop.Seek "=", sumg!numb1120, sumg!v, sumg!year
If dop.NoMatch Then dnm = True Else dnm = False
If bdop Then
If dop.NoMatch Then
dop.AddNew
dop!numb1 = sumg!numb1
dop!numb1120 = sumg!numb1120
dop!year = sumg!year
dop.Update
dop.Move 0, dop.LastModified
dnm = False
End If
End If
If Not dnm Then
dop.Edit
For j = 0 To nfg - 1
If fndx(j, 1) = 2 Then
If InStr(",name,year,numb1120,oes,numb1,", "," & sumg.Fields(j).Name & ",") = 0 Then
dop.Fields(fndx(j, 0)).Value = sumg.Fields(j)
End If
End If
Next j
dop.Update
End If
sumg.MoveNext
pb.Value = i / sumg.RecordCount * 100
Next i
pb.Value = 0
wform.Form.Refresh

End Sub


Private Sub Турбины_Click()
Dim db As Database, qturb As QueryDef
Set db = DBEngine.Workspaces(0).Databases(0)
Set qturb = db.QueryDefs("турбины(из_списков)")
R = MsgBox("Показывать располагаемую мощность?", vbYesNo)
qturbsql = qturb.SQL
qturbsql = repbetw1(qturbsql, "FROM ", " AS a", "[" & cv!agr & "]")
qturb.SQL = qturbsql
Application.DoCmd.OpenForm "Турбины", acFormDS, , "grcode=" & wform.Form!numb1120 & IIf(R = vbNo, " and ur=1 ", "")
End Sub

Private Sub Удаление_Click()
Dim rcl As DAO.Recordset, rstan As DAO.Recordset, rclm As DAO.Recordset
login = WNetGetUser()
With wform.Form
sqlcl = "select name,numb,main,comp,ведомство,ordnumb,oes,dep,er,obl,R from имена_станций where numb=" & !numb1120 & ";"
Set db = CurrentDb
Set rcl = db.OpenRecordset(sqlcl)
rcl.MoveFirst
Set rstan = .RecordsetClone
Workspaces(0).BeginTrans
Call setoptions
If IsNull(!MAIN) Then  'станция
sqldel = "DELETE d.*,d.numb1120 FROM [Станции(Схема)] AS d WHERE (((d.NUMB1120)=" & !numb1120 & "));"
DoCmd.RunSQL (sqldel)
GoTo enddel
End If
                       'группа оборудования
sqlclm = "select name,numb,main,comp,ведомство,ordnumb,oes,dep,er,obl,R from имена_станций where numb=" & !MAIN & ";"
Set rclm = db.OpenRecordset(sqlclm)
rclm.MoveFirst
rstan.FindFirst "numb1120<>" & !numb1120 & " and main=" & !MAIN
If rstan.NoMatch Then ungr = True Else ungr = False

If rcl!R <> 1 And Not ungr Then
sqldel = "DELETE d.*,d.numb1120 FROM [Станции(Схема)] AS d WHERE (((d.NUMB1120)=" & !numb1120 & "));"
DoCmd.RunSQL (sqldel)
End If
If rcl!R = 1 And Not ungr Then
bmsg = MsgBox("Удаление действующей группы возможно только, если она единственная", vbOKOnly)
GoTo enddel
End If
If ungr Then
sqlupgr = "UPDATE Списки_агрегатов as a SET a.grcode=stcode where a.stcode=" & rcl!MAIN & ";"
DoCmd.RunSQL (sqlupgr)
sqldelud = "DELETE d.*,d.numb1120 FROM [Удельные(Схема)] AS d WHERE (((d.NUMB1120)=" & rcl!MAIN & "));"
DoCmd.RunSQL (sqldelud)
Set qud = db.QueryDefs("Копирование_удельных_со_станции_на_группу") ' здесь наоборот - с группы на станцию
sqlupud = Replace(qud.SQL, "[код станции]", !numb1120) 'здесь наоборот - код группы
sqlupud = Replace(sqlupud, "[код группы]", rcl!MAIN) 'здесь наоборот - код станции
sqlupud = Replace(sqlupud, "[номер]", Replace(rclm!ordnumb, ",", "."))
DoCmd.RunSQL (sqlupud)
sqldelft = "DELETE d.*,d.numb1120 FROM [Формулы_топлива(Схема)] AS d WHERE (((d.NUMB1120)=" & rcl!MAIN & "));"
DoCmd.RunSQL (sqldelft)
Set qft = db.QueryDefs("Копирование_формул_топлива_со_станции_на_группу") ' здесь наоборот - с группы на станцию
sqlupft = Replace(qft.SQL, "[код станции]", !numb1120) 'здесь наоборот - код группы
sqlupft = Replace(sqlupft, "[код группы]", rcl!MAIN) 'здесь наоборот - код станции
sqlupft = Replace(sqlupft, "[номер]", Replace(rclm!ordnumb, ",", "."))
DoCmd.RunSQL (sqlupft)
sqlupved = "UPDATE [Станции(Схема)] SET VED = " & !VED & " WHERE (NUMB1120=" & !MAIN & ");"
DoCmd.RunSQL (sqlupved)
sqlupobor = "UPDATE [Станции(Схема)] SET OBOR = " & !OBOR & " WHERE (NUMB1120=" & !MAIN & ");"
DoCmd.RunSQL (sqlupobor)
sqldel = "DELETE d.*,d.numb1120 FROM [Станции(Схема)] AS d WHERE (((d.NUMB1120)=" & !numb1120 & "));"
DoCmd.RunSQL (sqldel)
End If
enddel:
Call resetoptions
Workspaces(0).CommitTrans
.Requery
Debug.Print "main="; rcl!MAIN
If Not (IsNull(rcl!MAIN)) Then
Debug.Print "возврат к станции"
.RecordsetClone.FindFirst ("numb1120=" & rcl!MAIN)
.Bookmark = .RecordsetClone.Bookmark
End If
End With
endp:
End Sub
Public Function WNetGetUser() As String
Dim res&
Dim tbuf As String
Dim BufferSize&
Dim lenName As Integer
tbuf = String$(256, 0)
BufferSize = Len(tbuf)
res = intWNetGetUser(vbNullString, tbuf, BufferSize) 'отсекаем нули от имени
lenName = InStr(tbuf, Chr(0)) - 1
tbuf = Left(tbuf, lenName)
WNetGetUser = tbuf
End Function
Private Sub Удалить_Click()
Dim stcode As Double
If z(wform.Form!VED) = 0 Then
msg = MsgBox("Варианты удаляются только для групп оборудования", vbOKOnly)
GoTo enddel
End If
stcode = wform.Form!numb1120
mainsql = "select main from имена_станций where numb=" & wform.Form!numb1120 & ";"
Set rmain = CurrentDb.OpenRecordset(mainsql)
rmain.MoveFirst
Workspaces(0).BeginTrans
Call setoptions
Call delvar(wname, stcode, z(rmain!MAIN))
Call delvar(dopform.Form.RecordSource, stcode, z(rmain!MAIN))
Call delvar(uform.Form.RecordSource, stcode, 0)
Call delvar(toplform.Form.RecordSource, stcode, 0)
Call resetoptions
Workspaces(0).CommitTrans
enddel:
End Sub
Private Sub copyvar(tname As String, stcode As Double, MAIN As Double)
Set t = CurrentDb.TableDefs(tname)
repsql = "update [" & tname & "] set v=1 where numb1120=" & stcode & ";"
DoCmd.RunSQL (repsql)
flist = t.Fields(0).Name
For i = 1 To t.Fields.Count - 1
If t.Fields(i).Name <> "v" Then flist = flist & ",[" & t.Fields(i).Name & "]"
Next i
vars = split(cv!vars, ";")
For j = 1 To UBound(vars)
var = vars(j)
addsql = "insert into [" & tname & "](" & flist & ",v) select " & flist & "," & var & " as v from " & t.Name & " where numb1120=" & stcode & " and v=1" & ";"
DoCmd.RunSQL (addsql)
If MAIN > 0 Then
repsql = Replace(repsql, "numb1120=" & stcode, "numb1120=" & MAIN)
DoCmd.RunSQL (repsql)
addsql = Replace(addsql, "numb1120=" & stcode, "numb1120=" & MAIN)
DoCmd.RunSQL (addsql)
End If
Next j
End Sub
Private Sub delvar(tname As String, stcode As Double, MAIN As Double)
Set t = CurrentDb.TableDefs(tname)
delsql = "delete * from [" & tname & "] where numb1120=" & stcode & " and v>1;"
DoCmd.RunSQL (delsql)
repsql = "update [" & tname & "] set v=0 where numb1120=" & stcode & ";"
DoCmd.RunSQL (repsql)
If MAIN > 0 Then
delsql = Replace(delsql, "numb1120=" & stcode, "numb1120=" & MAIN)
DoCmd.RunSQL (delsql)
repsql = Replace(repsql, "numb1120=" & stcode, "numb1120=" & MAIN)
DoCmd.RunSQL (repsql)
End If
End Sub

Private Sub Фильтр1_BeforeUpdate(Cancel As Integer)
With wform.Form
f = .filter
f = Replace(f, " and ved>0 and (obor<8 or (obor>=20 and obor<=22))", "")
f = Replace(f, " and ved>0 and (obor>=8 and (obor<=10 or obor>=90))", "")
f = Replace(f, " and ved>0 and (obor>=8 and (obor<=10 or obor>=92))", "")
f = Replace(f, " and ved>0 and (obor<8)", "")
f = Replace(f, " and ved>0 and (obor=21)", "")
f = Replace(f, " and ved>0 and (obor=20)", "")
f = Replace(f, " and ved>0 and (obor=91)", "")
f = Replace(f, " and ved>0 and (obor=90)", "")
f = Replace(f, " and ved>0 and (obor=21 or obor=91)", "")
f = Replace(f, " and ved>0 and (obor=20 or obor=90)", "")
cond = ""
If Фильтр1 = "КЭС" Then cond = "obor<8 or (obor>=20 and obor<=22)"
If Фильтр1 = "ПСУ КЭС" Then cond = "obor<8"
If Фильтр1 = "ПГУ КЭС" Then cond = "obor=21"
If Фильтр1 = "ГТУ КЭС" Then cond = "obor=20"
If Фильтр1 = "ТЭЦ" Then cond = "obor>=8 and (obor<=10 or obor>=90)"
If Фильтр1 = "ПСУ ТЭЦ" Then cond = "obor>=8 and (obor<=10 or obor>=92)"
If Фильтр1 = "ПГУ ТЭЦ" Then cond = "obor=91"
If Фильтр1 = "ГТУ ТЭЦ" Then cond = "obor=90"
If Фильтр1 = "ПГУ" Then cond = "obor=21 or obor=91"
If Фильтр1 = "ГТУ" Then cond = "obor=20 or obor=90"
If Фильтр1 <> "Все" Then f = f & " and ved>0 and (" & cond & ")"
.filter = f
.FilterOn = True
.Form.OrderBy = "obl,numb1,year"
End With
End Sub

Private Sub Фильтр2_Click()
Dim db As Database, rsum As DAO.Recordset
With wform.Form
If Фильтр2 Then
wform.SetFocus
fname = Screen.ActiveControl.Name
ff = fname
.filter = .filter & " and " & fname & ">0"
Else: .filter = Replace(.filter, " and " & ff & ">0", "")
End If
.FilterOn = True
.Form.OrderBy = "obl,numb1,year"
.OrderByOn = True
.Recalc
If Фильтр2 Then
For i = 0 To .Section(1).Controls.Count - 1
If z(.Section(1).Controls(i).Value) = 0 Then
.Section(0).Controls(Mid(.Section(1).Controls(i).Name, 4)).ColumnHidden = True
End If
Next i
Else
For i = 0 To .Section(0).Controls.Count - 1
.Section(0).Controls(i).ColumnHidden = False
Next i
End If
If Фильтр2 Then
For i = 0 To .Section(1).Controls.Count - 1
If z(.Section(1).Controls(i).Value) = 0 Then
.Section(0).Controls(Mid(.Section(1).Controls(i).Name, 4)).ColumnHidden = True
End If
Next i
Else
For i = 0 To .Section(0).Controls.Count - 1
.Section(0).Controls(i).ColumnHidden = False
Next i
End If
End With
End Sub

Private Sub фильтр3_Click()
Dim db As Database
If фильтр3 Then
foes = Replace(fltroes, "oes", "w.oes")
foes = Replace(foes, " v=", " w.v=")
foes = Replace(foes, "(v=", "(w.v=")
DoCmd.OpenForm "Условие", , , , , acDialog, "Редактирование"
sqlsel = "select first(имена_станций.name) as name,w.numb1120 as numb1120 from ([" & cv!wname & "] as w left join [" & cv!dopname & "] as d "
sqlsel = sqlsel & " on w.numb1120=d.numb1120 and w.year=d.year and w.v=d.v ) inner join имена_станций on w.numb1120=имена_станций.numb "
sqlsel = sqlsel & " where (" & foes & ") and " & cond & " group by w.numb1120,w.numb1 order by w.numb1;"
DoCmd.OpenForm "для_фильтра"
Forms("для_фильтра")!список.RowSource = sqlsel
fltr3 = wform.Form.filter
wform.Form.filter = "numb1120=" & Forms("для_фильтра")!список.Column(1, 0)
Else
wform.Form.filter = fltr3
wform.Form.OrderBy = "numb1,v,year"
wform.Form.OrderByOn = True
End If
End Sub