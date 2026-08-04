Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Option Compare Database
Dim secscan As Boolean, ny As Integer
Dim jr As Integer, jnt As Integer, istan As Integer, istanfg As Integer
Dim sq() As Double, Qsys() As Double
Dim stanoes As Recordset, qsum() As Variant, jp As Integer
Dim jy As Integer, jh As Integer, jht As Integer, jd As Integer, jq As Integer
Dim sqlsum As String
Dim sprav() As Double, pwrite As Boolean, pqfix As Double
Private Sub Form_Current()
Qoes.SetFocus
With Qoes.Form.RecordsetClone
.MoveLast
ny = .RecordCount
ReDim qsum(9, ny - 1)
.MoveFirst
jp = 7
jy = 0
jh = 8
jr = 9
jht = 4
jd = 5
jq = 6
jnt = 3
For i = 0 To ny - 1
qsum(0, i) = !year
qsum(1, i) = ![sum-q]
qsum(2, i) = ![Sum-QOTR]
qsum(3, i) = ![Sum-NT]
qsum(4, i) = !Ht
qsum(5, i) = !delta
.MoveNext
Next i
End With
With [Qdist].Form.RecordsetClone
.MoveFirst
For i = 0 To ny - 1
qsum(6, i) = !Qрас
qsum(7, i) = !Прирост
qsum(8, i) = !hs
qsum(9, i) = !ri
.MoveNext
Next i
End With
qsum(6, 0) = qsum(1, 0)
End Sub

Private Sub Form_Open(Cancel As Integer)
DoCmd.OpenForm "Выбор_варианта", , , , , acDialog, "тепло"
sqlsum = "select [#t].oes,[#t].year,(avg(Qрас)-sum(Q)) as delta,sum(q) as [sum-q] ,sum(qotr) as [sum-qotr],sum(nt) as [sum-nt],sum(nust) as [sum-nust],iif([sum-nt]>0,[sum-qotr]/[sum-nt]*1000,0) as Ht "
sqlsum = sqlsum & "from [#t] left join [распределяемое_тепло] as qdis on [#t].year=qdis.year and [#t].oes=qdis.code "
sqlsum = sqlsum & "where ved>0 and [#t].year>0 and [#t].oes=" & oes & " "
sqlsum = sqlsum & "group by [#t].oes,[#t].year;"
sqlsum = Replace(sqlsum, "#t", var)
Qoes.Form.RecordSource = sqlsum
sqlstan = "select [#t].name,[#t].numb1120,[#t].ved,[#t].obl,[#t].oes,ordnumb,main,"
sqlstan = sqlstan & "(select count(class!numb) from [имена_станций] as class where class!main=[имена_станций]!main and class!r=1) as dg,"
sqlstan = sqlstan & "iif(dg=1 and r=1,main,numb) as linko,iif(code is not null,true,false) as Qfix "
sqlstan = sqlstan & "from ([#t] inner join [имена_станций] on [#t].numb1120=[имена_станций].numb) left join [Фиксированное_тепло] on "
sqlstan = sqlstan & " [имена_станций].numb=[Фиксированное_тепло].code where ([#t].year=year) order by ordnumb;"
sqlstan = Replace(sqlstan, "#t", var)
Qstan.Form.RecordSource = sqlstan
Qstan.Form!Qr.Form.RecordSource = var
End Sub

Private Sub Другой_вариант_Click()
Dim Cancel As Integer
Call Form_Open(Cancel)
End Sub

Private Sub Кнопка25_Click() ' Суммирование групп-------------------------
Dim db As Database, work As QueryDef, dopq As QueryDef, dest As QueryDef
Dim wname As String, dopname As String
Dim del As QueryDef, sumq As QueryDef, sqlsum As String, sqlsumm As String
Dim w As Form, sumqf As Recordset, stan As Form
Set stan = Qstan.Form
If stan!VED <> 0 Then
B = MsgBox("Станция не разбита на группы", vbOKOnly)
GoTo endp
End If
stan!calc = 1
Set w = Qstan.Form!Qr.Form
wname = w.RecordSource
Set db = Application.DBEngine.Workspaces(0).Databases(0)
Set dest = db.QueryDefs("destination")
dest.SQL = "select distinctrow " & "[" & wname & "].* from " & "[" & wname & "];"
Set sumq = db.QueryDefs("Сумма_частей(тепло)")
sqlsum = sumq.SQL
sqlsumm = Replace(sqlsum, "(имена_станций.main)>0", "(имена_станций.main)=" & w!numb1120)
sqlsumm = Replace(sqlsumm, "Рабочий_для_суммы", "[" & wname & "]")
Debug.Print sqlsumm
Set sumqf = db.OpenRecordset(sqlsumm)
Qstan.SetFocus
Qstan!Qr.SetFocus
DoCmd.GoToRecord , , acFirst
sumqf.MoveFirst
For i = 1 To sumqf.RecordCount
w!Q = sumqf!Q
w!QOTR = sumqf!QOTR
w!NUST = sumqf!NUST
w!NT = sumqf!NT
DoCmd.GoToRecord , , acNext
sumqf.MoveNext
Next i
DoCmd.GoToRecord , , acFirst
stan!calc = 0
endp:
End Sub

Private Sub Кнопка9_Click() ' Итог--------------------------
[Qoes].Requery
End Sub

Private Sub Нач_точка_Click()
Dim db As Database, qdisf As Recordset
Set db = DBEngine.Workspaces(0).Databases(0)
If Список_областей = "Все" Then
Set qdisf = db.OpenRecordset("Распределяемое_тепло", DB_OPEN_DYNASET)
Else
Set qdisf = db.OpenRecordset("Распределяемое_тепло(области)", DB_OPEN_DYNASET)
End If
[Qoes].Requery
Call Form_Current
With Qoes.Form.RecordsetClone
jqc = 1
jqotrc = 2
End With
With qdisf
qdisf.FindFirst "code=" & oes & " and year=" & qsum(jy, 0)
If z(qsum(jqc, 0) > 0) Then POTRB = qsum(jqotrc, 0) / qsum(jqc, 0) Else POTRB = 0.85
Qprev = qsum(jqc, 0)
For i = 1 To ny - 1
qdisf.FindFirst "code=" & oes & " and year=" & qsum(jy, i)
.Edit
!Прирост = max2(0, Int(!Qрас - Qprev) / Qprev * 100 - 1)
!hs = Round((!Qрас * POTRB) / qsum(jnt, i), 1) * 1000 + 100
!ri = 1
.Update
Qprev = !Qрас
Next i
End With
[Qdist].Requery
Call Form_Current
End Sub

Private Sub Распред_Click() 'Распределение--------------------------------
Dim allstan As Recordset, clst As Recordset, db1 As Database, db As Database
Dim fQo As Recordset, QfixT As Recordset
Dim dgcount As Recordset, sqldg As String, qdisf As Recordset
Dim maxht As Double, Ht As Double, linko As Double, MAIN As Double
Dim Q() As Double, QOTR() As Double, NT() As Double, years() As Double
Call Form_Current
Debug.Print "time="; Time
ny = 11
Set db = DBEngine.Workspaces(0).Databases(0)
Set db1 = DBEngine.Workspaces(0).OpenDatabase("f:\Базы данных\ОТЭТ")
If Список_областей = "Все" Then
Set qdisf = db.OpenRecordset("Распределяемое_тепло", DB_OPEN_DYNASET)
Else
Set qdisf = db.OpenRecordset("Распределяемое_тепло(области)", DB_OPEN_DYNASET)
End If
Set clst = db1.OpenRecordset("имена_станций", DB_OPEN_TABLE)
clst.Index = "numb"
Set allstan = db.OpenRecordset(Qstan.Form!Qr.Form.RecordSource, DB_OPEN_DYNASET)
allstan.filter = "oes=" & oes
Set stanoes = allstan.OpenRecordset
stanoes.MoveLast
nstan = stanoes.RecordCount / ny
ReDim sprav(nstan, 2)
Set fQo = db1.OpenRecordset("Станции(архив)", DB_OPEN_TABLE)
fQo.Index = "numb2"
Set QfixT = db.OpenRecordset("Фиксированное_тепло")
QfixT.Index = "code"
ReDim Qsys(ny - 1, 1)
ReDim Q(ny - 1)
ReDim QOTR(ny - 1)
ReDim NT(ny - 1)
ReDim years(ny - 1)
ReDim sq(ny - 1, 4)
pb.Max = 100
pb.Min = 0
pb.Value = 0
Pi = -1
deltamax = -1
pdelta = 0
hstep = 100
pstep = 0.5
ristep = 0.05
pwrite = False
[Qoes].Requery
Call Form_Current
Debug.Print "time= "; Time
first:
For i1 = 1 To ny - 1
Qsys(i1, 0) = 0
Qsys(i1, 1) = 0
Next i1
istan = 0
secscan = False
bm = Null
stanoes.MoveFirst
nxt:
If stanoes!year = 2001 Then ',базовый год
If Not IsNull(bm) And VED > 0 Then 'запись расчитанного тепла
bm1 = stanoes.Bookmark
stanoes.Bookmark = bm
'Debug.Print stanoes!YEAR; stanoes!NAME
Call calcq(Q, QOTR, NT, years, MAIN, maxht)
stanoes.Bookmark = bm1
End If 'запись расчитанного тепла
stan:
bm = stanoes.Bookmark
i = 0
If Not psprav Then
clst.Seek "=", stanoes!numb1120
cmain = z(clst!MAIN)
sprav(istan, 1) = cmain
QfixT.Seek "=", stanoes!numb1120
If QfixT.NoMatch Then pqfix = 0 Else pqfix = 1
sprav(istan, 2) = pqfix
Else:
cmain = sprav(istan, 1)
pqfix = sprav(istan, 2)
End If
linko = stanoes!numb1120
If MAIN = 0 And cmain > 0 And Not secscan Then 'первая группа
istanfg = istan
bmfg = stanoes.Bookmark
For i1 = 0 To ny - 1
sq(i1, 0) = 0
sq(i1, 1) = 0
sq(i1, 2) = 0
sq(i1, 3) = 0
sq(i1, 4) = 0
Next i1
End If
If MAIN > 0 And cmain = 0 Then 'последняя группа
If Not secscan Then 'первый проход
Call lastgroup(secscan, bmfg, sq())
GoTo stan
Else 'второй проход
secscan = False
End If
End If 'последняя группа
MAIN = cmain
VED = z(stanoes!VED)
If Not psprav Then
If MAIN > 0 Then
sqldg = "Select count(main) as dg from имена_станций where (d=1 and r=1 and main=" & MAIN & ") group by main;"
Set dgcount = db.OpenRecordset(sqldg)
If dgcount.RecordCount > 0 Then If dgcount!dg = 1 And clst!R = 1 Then linko = clst!MAIN
End If
fQo.Seek ">=", linko, "1990"
maxht = 0
If Not (fQo.NoMatch) Then  ' есть отчет
If fQo!numb1120 = linko Then
numb1120 = fQo!numb1120
Do While (fQo!numb1120 = numb1120)
If fQo!year = 1990 Or fQo!year = 1991 Or fQo!year = 1995 Or fQo!year = 2000 Or fQo!year = 2001 Then
If z(fQo!NT) > 0 Then Ht = z(fQo!QOTR) / fQo!NT * 1000 Else Ht = 0
maxht = max2(maxht, Ht)
End If
fQo.MoveNext
If fQo.EOF Then GoTo outfqo
Loop
outfqo:
End If
End If 'есть отчет
If z(stanoes!NT) > 0 Then maxht = max2(maxht, z(stanoes!QOTR) / stanoes!NT * 1000)
sprav(istan, 0) = maxht
Else
maxht = sprav(istan, 0)
End If 'psprav
istan = istan + 1
End If 'базовый год
Q(i) = z(stanoes!Q)
QOTR(i) = z(stanoes!QOTR)
NT(i) = z(stanoes!NT)
years(i) = z(stanoes!year)
i = i + 1
stanoes.MoveNext
If Not stanoes.EOF Then
GoTo nxt
End If
stanoes.Bookmark = bm
Call calcq(Q, QOTR, NT, years, MAIN, maxht)
If MAIN > 0 Then
If Not secscan Then 'первый проход
Call lastgroup(secscan, bmfg, sq())
GoTo stan
Else 'второй проход
secscan = False
End If
End If
psprav = True
For i = 1 To ny - 1
qdis = qsum(jq, i)
delta = Qsys(i, 0) - qdis
'If years(i) = 2010 And Abs(delta) < 200 Then GoTo nexti
Ht = Qsys(i, 1) / qsum(jnt, i) * 1000
pdis = (qsum(jq, i) - qsum(jq, i - 1)) / qsum(jq, i - 1) * 100
If Abs(delta) > 1 Then
If Pi <> i Then ' следующий год
Qoes.SetFocus
DoCmd.GoToRecord , , acGoTo, i + 1
deltamax = -1
cdc = ""
pdelta = 0
hstep = 50
pstep = 0.5
ristep = 0.05
End If
If deltamax = -1 Then deltamax = Abs(delta)
If deltamax > 0 Then If Abs(delta) < deltamax Then pb.Value = 100 - Abs(delta) / deltamax * 100 Else pb.Value = 0
pdc = ""
If pdelta <> 0 And Sgn(pdelta) <> Sgn(delta) Then
If cdc = "hs" Then hstep = hstep / 2
If cdc = "p" Then pstep = pstep / 2
If cdc = "ri" Then ristep = ristep / 2
pdc = cdc
End If
qdisf.FindFirst "code=" & oes & " and year=" & qsum(jy, i)
qdisf.Edit
If delta < 0 Then
tryagain:
If (qdisf!ri < 1 - ristep) And (pdc = "" Or pdc = "ri") Then
qdisf!ri = qdisf!ri + ristep
cdc = "ri"
Else
If (qdisf!ri < 1) And (pdc = "" Or pdc = "ri") Then
qdisf!ri = 1
cdc = "ri"
Else
If ((Ht > qdisf!hs Or qdisf![Прирост] > pdis) And qdisf!hs < max2(Ht * 1.5, 4000)) And (pdc = "" Or pdc = "hs") Then
qdisf!hs = qdisf!hs + hstep
cdc = "hs"
Else
If pdc = "" Or pdc = "p" Then
qdisf![Прирост] = qdisf![Прирост] + pstep
cdc = "p"
Else
pdc = ""
GoTo tryagain
End If
End If ' сравнение Ht с hs
End If 'сравнение ri с 1
End If 'сравнение ri c ri-ristep
Else 'delta>0
tryagain1:
If (Ht < qdisf!hs - hstep Or pdis >= 0 And (qdisf![Прирост] - pstep) < 0 And Ht < (qdisf!hs - hstep) * 1.2) And (pdc = "" Or pdc = "hs") Then
qdisf!hs = qdisf!hs - hstep
cdc = "hs"
Else
If (qdisf![Прирост] > pstep) And (pdc = "" Or pdc = "p") Then
qdisf![Прирост] = qdisf![Прирост] - pstep
cdc = "p"
Else
If (qdisf![Прирост] > 0) And (pdc = "" Or pdc = "p") Then
qdisf![Прирост] = 0
cdc = "p"
Else
If (qdisf!ri - ristep > 0) And (pdc = "" Or pdc = "ri") Then
qdisf!ri = qdisf!ri - ristep
cdc = "ri"
Else
If pdc = "" Or pdc = "p" Then
qdisf![Прирост] = qdisf![Прирост] - pstep
cdc = "p"
Else
pdc = ""
GoTo tryagain1
End If
End If
End If 'сравнение qdisf![прирост] и 0
End If 'сравнение qdisf![прирост] и pstep
End If 'сравнение Ht и qdisf!hs-hstep
End If
Debug.Print delta; "h="; qdisf!hs; "p="; qdisf![Прирост]; "r="; qdisf!ri
qdisf.Update
qsum(jh, i) = qdisf!hs
qsum(jp, i) = qdisf![Прирост]
qsum(jr, i) = qdisf!ri
pdelta = delta
Pi = i
GoTo first
End If
nexti:
Next i
If Not pwrite Then
pwrite = True
GoTo first
End If
Debug.Print "time= "; Time
[Qoes].Requery
[Qdist].Requery
End Sub
' обработка последней группы--------------------------------------
Sub lastgroup(secscan As Boolean, bmfg As Variant, sq() As Double)
istan = istanfg
stanoes.Bookmark = bmfg
secscan = True
For i1 = 1 To ny - 1
Qd = sq(i1 - 1, 0) + sq(i1 - 1, 2) + sq(i1 - 1, 3)
If Qd > sq(i1, 0) Then
sq(i1, 2) = Min2(sq(i1, 1), Qd - sq(i1, 0))
sq(i1, 3) = max2(0, Qd - (sq(i1, 0) + sq(i1, 2)))
End If
Qsys(i1, 0) = Qsys(i1, 0) - sq(i1, 0)
Qsys(i1, 1) = Qsys(i1, 1) - sq(i1, 4)
Next i1
If sq(ny - 1, 3) > 0 Then 'отмена выравнивания
For i1 = 1 To ny - 1
sq(i1, 2) = 0
sq(i1, 3) = 0
Next i1
End If
End Sub
'  расчет станции --------------------------------------------------------------------------
Sub calcq(Q() As Double, QOTR() As Double, NT() As Double, years() As Double, MAIN As Double, maxht As Double)
Dim DNT As Double, k As Double, k1 As Double, potr1 As Double
For i = 0 To UBound(Q)
p = 0
maxd = 0
If pqfix = 1 Then GoTo skipcalc
For i1 = 0 To UBound(Q)
If qsum(jy, i1) = years(i) Then
hs = qsum(jh, i1) / 1000
p = qsum(jp, i1)
ri = qsum(jr, i1)
End If
Next i1
If i > 0 Then
If secscan Then GoTo skipfirst
If NT(i) >= NT(i - 1) Then
maxnt = NT(i - 1)
For i1 = 0 To i - 1
If maxnt < NT(i1) Then maxnt = NT(i1)
Next i1
If maxnt >= NT(i - 1) Then DNT = max2(NT(i) - maxnt, 0) Else DNT = NT(i) - NT(i - 1)
k = 1
If NT(0) = 0 Then
If QOTR(i - 1) = 0 Then
Q(i) = NT(i) * hs * 1.15
QOTR(i) = NT(i) * hs
Else 'QOTR(i-1)>0
If NT(i) >= NT(i - 1) Then k = ri
Q(i) = Q(i - 1) + max2(Q(i - 1) * p / 100, DNT * hs * k * 1.15)
QOTR(i) = QOTR(i - 1) + max2(QOTR(i - 1) * p / 100, DNT * k * hs)
End If
Else 'Nt(0)<>0
If NT(i) > NT(i - 1) Then k = ri
If p >= 0 Then
Q(i) = Q(i - 1) + max2(Q(i - 1) * p / 100, DNT * hs * k * 1.15)
QOTR(i) = QOTR(i - 1) + max2(QOTR(i - 1) * p / 100, DNT * k * hs)
Else 'p<0
Q(i) = Q(i - 1) + DNT * hs * k * 1.15 + Q(i - 1) * p / 100
QOTR(i) = QOTR(i - 1) + DNT * hs * k + Q(i - 1) * p / 100
If QOTR(i) < 0 Then QOTR(i) = 0
End If
End If
Else ' Nt(i)<Nt(i-1)
If MAIN > 0 Then
QOTR(i) = QOTR(i - 1) * NT(i) / NT(i - 1)
Q(i) = Q(i - 1) * NT(i) / NT(i - 1)
Else 'main=0
QOTR(i) = NT(i) * maxht / 1000
Q(i) = QOTR(i) / 0.85
If Q(i) > Q(i - 1) Then
Q(i) = Q(i - 1)
QOTR(i) = Q(i - 1) * 0.85
End If
End If 'main
End If
skipfirst:
If NT(i) > 0 Then
potr1 = QOTR(i) / Q(i)
Ht = QOTR(i) / NT(i) * 1000
If maxht > 0 Then maxht1 = maxht Else maxht1 = hs * 1000
If Ht > maxht1 Then
QOTR(i) = NT(i) * maxht1 / 1000
Q(i) = QOTR(i) / potr1
End If
If MAIN > 0 Then
If maxht > 0 Then
k2 = 1
If maxht < 3500 Then k2 = 1.2 Else If maxht < 4000 Then k2 = 1 + 0.2 * (4000 - maxht) / 500
If maxht * k2 > Ht Then maxd = (NT(i) * (maxht * k2 - Ht) / 1000) / potr1
End If ' maxht>0
If maxht = 0 And hs * 1000 < 4500 Then maxd = (NT(i) * (4500 - Ht) / 1000) / potr1
If secscan Then 'второй проход
If p >= 0 And sq(i, 2) > 0 Then
k1 = sq(i, 2) / sq(i, 1)
Q(i) = Q(i) + k1 * maxd
QOTR(i) = QOTR(i) + k1 * maxd * potr1
End If
If p >= 0 And sq(i, 3) > 0 And sq(ny - 1, 3) = 0 And NT(i) <= NT(i - 1) And Q(i) < Q(i - 1) Then
Q(i) = Q(i) + Min2(sq(i, 3), Q(i - 1) - Q(i))
sq(i, 3) = sq(i, 3) - Min2(sq(i, 3), Q(i - 1) - Q(i))
End If
End If ' второй проход
End If 'main>0
Else 'Nt(i)=0
If Not secscan Then
QOTR(i) = 0
If NT(0) > 0 Then Q(i) = 0 Else If MAIN = 0 Then Q(i) = Q(i - 1) * (1 + p / 100)
Else
If p >= 0 And sq(i, 3) > 0 And sq(ny - 1, 3) = 0 And Q(i) < Q(i - 1) Then
Q(i) = Q(i) + Min2(sq(i, 3), Q(i - 1) - Q(i))
sq(i, 3) = sq(i, 3) - Min2(sq(i, 3), Q(i - 1) - Q(i))
End If
End If
End If
If p >= 0 And MAIN = 0 And Q(i) < Q(i - 1) Then Q(i) = Q(i - 1)
stanoes.MoveNext
If pwrite Or MAIN > 0 And Not secscan Then
stanoes.Edit
stanoes!Q = Q(i)
stanoes!QOTR = QOTR(i)
stanoes.Update
End If
skipcalc:
Qsys(i, 0) = Qsys(i, 0) + Q(i)
Qsys(i, 1) = Qsys(i, 1) + QOTR(i)
End If
If MAIN > 0 And Not secscan Then
sq(i, 0) = sq(i, 0) + Q(i)
sq(i, 4) = sq(i, 4) + QOTR(i)
sq(i, 1) = sq(i, 1) + maxd
End If 'i>0
Next i
End Sub

Private Sub Список_областей_AfterUpdate()
Dim sqlobl As String
If Список_областей <> "Все" Then
Qstan.Form.filter = "obl=" & Список_областей.Column(1)
Qstan.Form.FilterOn = True
sqlobl = "select [#t].obl,[#t].year,(avg(Qрас)-sum(Q)) as delta,sum(q) as [sum-q] ,sum(qotr) as [sum-qotr],sum(nt) as [sum-nt],sum(nust) as [sum-nust],iif([sum-nt]>0,[sum-qotr]/[sum-nt]*1000,0) as Ht "
sqlobl = sqlobl & "from [#t] left join [распределяемое_тепло(области)] as qdis on [#t].year=qdis.year and [#t].obl=qdis.code "
sqlobl = sqlobl & "where ved>0 and [#t].obl=" & Список_областей.Column(1) & " "
sqlobl = sqlobl & "group by [#t].obl,[#t].year;"
sqlobl = Replace(sqlobl, "#t", "Станции(Анализ_и_прогноз)")
Qoes.Form.RecordSource = sqlobl
Qdist.Form.RecordSource = "Распределяемое_тепло(области)"
Else
Qstan.Form.FilterOn = False
Qoes.Form.RecordSource = sqlsum
Qdist.Form.RecordSource = "Распределяемое_тепло"
End If
End Sub