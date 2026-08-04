Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Public af As String, ac As String
Dim ff As String, fltroes As String, fltr3 As String
Private Declare Function GetWindowRect Lib "User32" (ByVal hwnd As Long, crect As rect) As Long
Private Declare Function MoveWindow Lib "User32" (ByVal hwnd As Long, ByVal x As Long, ByVal y As Long, ByVal w As Long, ByVal h As Long, ByVal B As Long) As Long
Private Type rect
left As Long
top As Long
right As Long
bottom As Long
End Type
Public years As String
Private Sub Form_Close()
DoCmd.Close acForm, "Доп_угли"
DoCmd.Close acForm, "Стоимость"
Dim dbchange As Database, rchange As Recordset
If fchange = 1 Then
Set dbchange = DBEngine.OpenDatabase("f:\Базы данных\изменения")
Set rchange = dbchange.OpenRecordset("изменения")
rchange.Edit
rchange(varname) = Date & " " & Time
rchange.Update
End If
End Sub

Private Sub Form_Open(Cancel As Integer)
Dim df As Form, st As Form, crect As rect, dfrect As rect, strect As rect
DoCmd.OpenForm "выбор_варианта", , , , , acDialog, "Редактирование_отчетных_данных"
With stan.Form
.RecordSource = "select w.*,main,форэм from [" & var & "] as w inner join имена_станций on w.numb1120=имена_станций.numb;"
If OES <> 0 Then .Filter = "oes=" & OES Else .Filter = "oes<100"
fltroes = .Filter
.FilterOn = True
.Form.OrderBy = "numb1,year"
.OrderByOn = True
Application.DoCmd.OpenForm "Доп_угли", acFormDS
Set df = Forms("Доп_угли")
df.RecordSource = dop
df.Filter = "numb1120=" & !NUMB1120 & " and year=" & !YEAR
df.FilterOn = True
End With
'добавила
With stan.Form
.RecordSource = "select w.*,main,форэм from [" & var & "] as w inner join имена_станций on w.numb1120=имена_станций.numb;"
If OES <> 0 Then .Filter = "oes=" & OES Else .Filter = "oes<100"
fltroes = .Filter
.FilterOn = True
.Form.OrderBy = "numb1,year"
.OrderByOn = True
Application.DoCmd.OpenForm "Стоимость", acFormDS
Set st = Forms("Стоимость")
st.RecordSource = stoim
st.Filter = "numb1120=" & !NUMB1120 & " and year=" & !YEAR
st.FilterOn = True
End With
'конец
уровень = False
Ведомство = "Все"
Me.SetFocus
DoCmd.Maximize
Call GetWindowRect(Me.hwnd, crect)
Call GetWindowRect(df.hwnd, dfrect)
dfw = dfrect.right - dfrect.left
dfh = dfrect.bottom - dfrect.top
dftop = crect.bottom - dfh - 25
stan.Width = InsideWidth - 690
stan.Height = InsideHeight - df.WindowHeight - stan.top - 100
df.SetFocus
DoCmd.MoveSize , dftop
Call MoveWindow(df.hwnd, 20, dftop, dfw, dfh, 1)
'добавила
Call GetWindowRect(st.hwnd, strect)
stw = strect.right - strect.left
sth = strect.bottom - strect.top
sttop = crect.bottom - sth - 30
stan.Width = InsideWidth - 690
stan.Height = InsideHeight - st.WindowHeight - stan.top - 100
st.SetFocus
DoCmd.MoveSize , sttop
Call MoveWindow(st.hwnd, 20, sttop, stw, sth, 1)
'конец добавленного фрагмента
'выравнивание по правому краю
'nat.left = stan.left + stan.Width - nat.Width
nat1.top = stan.top + stan.Height + 100
nat.top = nat1.top + nat1.Height
End Sub

Private Sub nat1_AfterUpdate()
For i = 0 To nat.Controls.Count - 1
If nat.Controls(i).Name = ac Then GoTo found
Next i
bmsg = MsgBox("Неверное поле", vbOKOnly)
GoTo endp
found:
If nat(ac).Tag = "w" Then fvalue = stan.Form(ac) Else fvalue = Forms("Доп_угли")(ac)
nat(ac) = fvalue / nat1
If nat(ac).Tag = "w" Then stan.Form(ac).SetFocus Else Forms("Доп_угли").SetFocus
endp:
End Sub

Private Sub nat1_DblClick(Cancel As Integer)
For i = 0 To nat.Controls.Count - 1
If nat.Controls(i).Name = ac Then GoTo found
Next i
bmsg = MsgBox("Неверное поле", vbOKOnly)
GoTo endp
found:
If nat(ac).Tag = "w" Then fvalue = stan.Form(ac) Else fvalue = Forms("Доп_угли")(ac)
nat1 = fvalue / nat(ac)
endp:
End Sub

Private Sub nat1_MouseMove(Button As Integer, Shift As Integer, x As Single, y As Single)
If Screen.ActiveControl.Parent.Name = "Доп_угли" Or Screen.ActiveControl.Parent.Name = "Станции_отчет" Then ac = Screen.ActiveControl.Name
End Sub

Private Sub Ведомство_Change()
With stan.Form
f = .Filter
f = Replace(f, " and (форэм<>1 or форэм is null) and вед=1", "")
f = Replace(f, " and вед=1", "")
f = Replace(f, " and вед=2", "")
f = Replace(f, " and форэм=1", "")
If Ведомство = "РАО и АО-энерго" Then f = f & " and вед=1"
If Ведомство = "Прочие ведомства" Then f = f & " and вед=2"
If Ведомство = "Форэм" Then f = f & " and форэм=1"
If Ведомство = "без Форэм" Then f = f & " and (форэм<>1 or форэм is null) and вед=1"
If Ведомство = "Все" Then
f = Replace(f, " and (форэм<>1 or форэм is null) and вед=1", "")
f = Replace(f, " and вед=1", "")
f = Replace(f, " and вед=2", "")
f = Replace(f, " and форэм=1", "")
End If
.Filter = f
.FilterOn = True
.Form.OrderBy = "numb1,year"
.OrderByOn = True
End With
For i = 0 To Forms.Count - 1
If Forms(i).Name = "Итог" Then
Call Итог_Click
End If
Next i
End Sub

Private Sub Вставка_Click()
DoCmd.OpenForm "Список_станций"
Forms("Список_станций").Form!liststan.RowSource = "select name,numb from имена_станций where obl=" & stan.Form!OBL & " order by ordnumb;"
End Sub

Private Sub Годы_Click()
DoCmd.OpenForm ("Годы")
End Sub


Private Sub Диаграмма_Click()
flist = "select name from список_полей where table=""w"" or table=""d"" or table=""f"";"
fromlist = ""
DoCmd.OpenForm ("Выбор_из_списка_м"), , , , , acDialog, flist & "/Редактирование_отчетных_данных"
If fromlist <> "" Then DoCmd.OpenForm "Диаграмма", , , "numb=" & stan.Form!NUMB1120
End Sub

Private Sub Итог_Click()
Dim sqlm As String, sqlt As String
If af = "dop" Then Forms("Доп_угли").SetFocus Else stan.SetFocus
'добавила
If af = "stoim" Then Forms("Стоимость").SetFocus Else stan.SetFocus
fname = Screen.ActiveControl.Name
If Фильтр3 Then condtxt = "(" & Replace(fltroes, "oes", "w.oes") & ") and (" & cond & ")" Else condtxt = Replace(Replace(stan.Form.Filter, "year", "[#t].YEAR"), "oes", "w.oes")
If Тип_Итога = "ОЭС" Then
Debug.Print fltroes
If fltroes = "oes<100" Then
sqlm = "select w.year,sum(#field) as Сумма from ([#t] as w left join [#d] as d on w.numb1120=d.numb1120 and w.year=d.year) inner join имена_станций on w.numb1120=имена_станций.numb where " & IIf(InStr(condtxt, "main Is NULL or main=0") > 0, "", "ved>0 and ") & "(" & condtxt & ") group by w.year;"
Debug.Print sqlm
Else
sqlm = "select w.oes as code,w.year,sum(#field) as Сумма from ([#t] as w left join [#d] as d on w.numb1120=d.numb1120 and w.year=d.year) inner join имена_станций on w.numb1120=имена_станций.numb where " & IIf(InStr(condtxt, "main Is NULL or main=0") > 0, "", "ved>0 and ") & "(" & condtxt & ") group by w.oes,w.year;"
End If
Else
sqlm = "select w.obl as code,w.year,sum(#field) as Сумма from ([#t] as w left join [#d] as d on w.numb1120=d.numb1120 and w.year=d.year) inner join имена_станций on w.numb1120=имена_станций.numb where ved>0 and w.obl=" & stan.Form!OBL & " and (" & condtxt & ") group by w.obl,w.year;"
End If
sqlt = Replace(sqlm, "#field", Screen.ActiveControl.Name)
'sqlt = Replace(sqlt, "oes", "[#t].oes")
'If Тип_Итога = "Область" Then sqlt = Replace(sqlt, "obl", "[#t].obl")
sqlt = Replace(sqlt, "#t", var)
sqlt = Replace(sqlt, "#d", dop)
'добавила
sqlt = Replace(sqlt, "#s", stoim)
If уровень Then sqlt = Replace(sqlt, "ved>0 and", "")
Application.DoCmd.OpenForm "Итог", acFormDS
'Debug.Print sqlt
Forms("Итог").RecordSource = sqlt
Forms("Итог").Caption = UCase(fname)
Forms("Итог").Requery
End Sub

Private Sub Итог_MouseMove(Button As Integer, Shift As Integer, x As Single, y As Single)
If Screen.ActiveControl.Parent.Name = "Доп_угли" Then af = "dop"
If Screen.ActiveControl.Parent.Name = "Стоимость" Then af = "stoim"
If Screen.ActiveControl.Parent.Name = "Станции_отчет" Then af = "stan"
End Sub

Private Sub Кнопка10_Click()
Dim Cancel As Integer
Call Form_Open(Cancel)
End Sub


Private Sub Кнопка28_Click()
Debug.Print Form.ActiveControl.Name
End Sub

Private Sub Отчет_Click()
flist = "select name from список_полей where table=""w"" or table=""d"" or table=""f"";"
fromlist = ""
DoCmd.OpenForm ("Выбор_из_списка_м"), , , , , acDialog, flist & "/Редактирование_отчетных_данных"
If fromlist <> "" Then DoCmd.OpenReport ("Для_Редактирования"), acViewPreview
End Sub

Private Sub Справка_Click()
DoCmd.OpenForm ("Диалог_для_справки"), , , , , , linkcode
End Sub

Private Sub Тип_Итога_Change()
For i = 0 To Forms.Count - 1
If Forms(i).Name = "Итог" Then
Call Итог_Click
End If
Next i
End Sub

Private Sub Турбины_Click()
If stan.Form!YEAR >= 2000 Then
If z(stan.Form!MAIN) > 0 Then sf = "grcode=" Else sf = "numb1120="
Application.DoCmd.OpenForm "Турбины", acFormDS, , sf & stan.Form!NUMB1120, , , Name
Else
B = MsgBox("Сведения о турбинах имеются только начинаяя с 2000 года", vbOKOnly)
End If
End Sub

Private Sub уровень_AfterUpdate()
With stan.Form
If уровень Then
.Filter = .Filter & " and main is null"
Else
.Filter = Replace(.Form.Filter, " and main is null", "")
End If
.FilterOn = True
.Form.OrderBy = "numb1,year"
.OrderByOn = True
End With
For i = 0 To Forms.Count - 1
If Forms(i).Name = "Итог" Then
Call Итог_Click
End If
Next i
End Sub

Private Sub Фильтр_AfterUpdate()
Dim db As Database, rsum As Recordset
With stan.Form
If Фильтр Then
stan.SetFocus
fname = Screen.ActiveControl.Name
ff = fname
Debug.Print .Filter
.Filter = .Filter & " and " & fname & ">0"
Else: .Filter = Replace(.Filter, " and " & ff & ">0", "")
End If
.FilterOn = True
.Form.OrderBy = "numb1,year"
.OrderByOn = True
.Recalc
If Фильтр Then
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
If Фильтр Then
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

Private Sub Фильтр3_Click()
Dim db As Database
If Фильтр3 Then 'включен
foes = Replace(fltroes, "oes", "w.oes")
DoCmd.OpenForm "Условие", , , , , acDialog, "Редактирование_отчетных_данных"
sqlsel = "select first(имена_станций.name) as name,w.numb1120 as numb1120 from ([" & var & "] as w left join [" & dop & "] as d "
sqlsel = sqlsel & " on w.numb1120=d.numb1120 and w.year=d.year ) inner join имена_станций on w.numb1120=имена_станций.numb "
sqlsel = sqlsel & " where (" & foes & ") and " & cond & " group by w.numb1120,w.numb1 order by w.numb1;"
'добавила
sqlsel = "select first(имена_станций.name) as name,w.numb1120 as numb1120 from ([" & var & "] as w left join [" & stoim & "] as s "
sqlsel = sqlsel & " on w.numb1120=s.numb1120 and w.year=s.year ) inner join имена_станций on w.numb1120=имена_станций.numb "
sqlsel = sqlsel & " where (" & foes & ") and " & cond & " group by w.numb1120,w.numb1 order by w.numb1;"
DoCmd.OpenForm "для_фильтра"
Forms("для_фильтра")!список.RowSource = sqlsel
fltr3 = stan.Form.Filter
If Forms("для_фильтра")!список.ListCount > 0 Then stan.Form.Filter = "numb1120=" & Forms("для_фильтра")!список.Column(1, 0)
Else ' отключен
stan.Form.Filter = fltr3
stan.Form.OrderBy = "numb1,year"
stan.Form.OrderByOn = True
End If
End Sub

Private Sub Удаление_Click()
Dim rcl As DAO.Recordset, rstan As DAO.Recordset, rclm As DAO.Recordset
With stan.Form
sqlcl = "select name,numb,main,comp,ведомство,ordnumb,oes,dep,er,obl,R from имена_станций where numb=" & !NUMB1120 & ";"
Set db = CurrentDb
Set rcl = db.OpenRecordset(sqlcl)
rcl.MoveFirst
Set rstan = .RecordsetClone
Workspaces(0).BeginTrans
Call setoptions
If IsNull(!MAIN) Then  'станция
sqldel = "DELETE d.*,d.numb1120 FROM [" & var & "] AS d WHERE (((d.NUMB1120)=" & !NUMB1120 & "));"
DoCmd.RunSQL (sqldel)
GoTo enddel
End If
                       'группа оборудования
sqlclm = "select name,numb,main,comp,ведомство,ordnumb,oes,dep,er,obl,R from имена_станций where numb=" & !MAIN & ";"
Set rclm = db.OpenRecordset(sqlclm)
rclm.MoveFirst
rstan.FindFirst "numb1120<>" & !NUMB1120 & " and main=" & !MAIN
If rstan.NoMatch Then ungr = True Else ungr = False

If rcl!R <> 1 And Not ungr Then
sqldel = "DELETE d.*,d.numb1120 FROM [" & var & "] AS d WHERE (((d.NUMB1120)=" & !NUMB1120 & "));"
DoCmd.RunSQL (sqldel)
End If
If rcl!R = 1 And Not ungr Then
bmsg = MsgBox("Удаление действующей группы возможно только, если она единственная", vbOKOnly)
GoTo enddel
End If
If ungr Then
sqlupgr = "UPDATE Турбины as a SET a.grcode=a.numb1120 where a.numb1120=" & rcl!MAIN & ";"
DoCmd.RunSQL (sqlupgr)
sqlupved = "UPDATE [" & var & "] SET VED = " & !VED & " WHERE (NUMB1120=" & !MAIN & ");"
DoCmd.RunSQL (sqlupved)
sqlupobor = "UPDATE [" & var & "] SET OBOR = " & !OBOR & " WHERE (NUMB1120=" & !MAIN & ");"
DoCmd.RunSQL (sqlupobor)
sqldel = "DELETE d.*,d.numb1120 FROM [" & var & "] AS d WHERE (((d.NUMB1120)=" & !NUMB1120 & "));"
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