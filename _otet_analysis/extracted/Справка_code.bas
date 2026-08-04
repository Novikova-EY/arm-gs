Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Option Compare Database

Private Sub af_Click()
i = af.ListIndex
For j = 0 To flist.ListCount - 1
If InStr(";" & af.Column(1, i) & ";", ";" & flist.Column(0, j) & ";") > 0 Then
If af.Selected(i) Then flist.Selected(j) = True Else flist.Selected(j) = False
End If
Next j
End Sub

Private Sub Кнопка2_Click()
Dim sellist As String, db As Database, qr As QueryDef, qh As QueryDef
Dim h As String, R As Report, ry As Recordset, qt As QueryDef
Set db = DBEngine.Workspaces(0).Databases(0)
If cond <> "" Then swhere = " Where (" & cond & ")" Else swhere = ""
sumlist = ""
formugol = ""
formugol1 = ""
nsugol = ""
fnf = 0
If Not (usl And nat) Then secstr = False
Debug.Print Time
For i = 0 To flist.ListCount - 1
If flist.Column(2, i) <> "" And flist.Column(1, i) <> "f" And Not flist.Selected(i) And flist.Column(1, i) = "w" Then
nsugol = nsugol & ",sum(w." & flist.Column(0, i) & ") as " & flist.Column(0, i)
End If
Next i
bnugol = False
For Each i In flist.ItemsSelected
If sumlist <> "" Then sumlist = sumlist & ","
If flist.Column(1, i) = "f" Then
isum = InStr(flist.Column(2, i), ";")
sumlist = sumlist & "sum(" & Mid(flist.Column(2, i), 1, isum - 1) & ") as " & flist.Column(0, i)
Else
sumlist = sumlist & "sum(" & flist.Column(1, i) & "." & flist.Column(0, i) & ") as " & flist.Column(0, i)
End If
If flist.Column(0, i) = "UGOL" Then bnugol = True
Next i
If nat And bnugol Then sumlist = sumlist & nsugol
fromtxt1 = "([#w] as w left join [#d] as d on w.numb1120=d.numb1120 and w.year=d.year #v) inner join имена_станций on w.numb1120=имена_станций.numb "
If so.Column(2) = "no" Then fromtxt1 = Replace(fromtxt1, "#v", "") Else fromtxt1 = Replace(fromtxt1, "#v", " and w.v=d.v")
fromtxt1 = Replace(fromtxt1, "#w", so.Column(0))
fromtxt1 = Replace(fromtxt1, "#d", so.Column(1))
sumsql = "select " & sumlist & " FROM " & fromtxt1 & swhere & ";"
If hide Then
Set rsum = db.OpenRecordset(sumsql)
rsum.MoveFirst
End If 'hide
If InStr(cond, "main=0") > 0 Then vedtxt = "" Else vedtxt = " and w.ved>0"
If Not transp Then 'прямая таблица
fnat = 0
seltxt = "SELECT Имена_станций.NAME AS name1, w.numb1120, w.numb1, 0 as v,w.YEAR, 1 as var, Имена_областей.NAME AS oblname, Имена_ОЭС.name AS oesname, w.OBL, w.OES "
If so.Column(2) <> "no" Then seltxt = Replace(seltxt, " 0 as v", "w.v")
sellist = ",null as f01,null as f02,null as f03,null as f04,null as f05,null as f06,null as f07,null as f08,null as f09,null as f10"
sellistnat = sellist
sellistdop = ",null as f11,null as f12,null as f13,null as f14,null as f15"
sellistsum = sellist
sellistsumnat = sellist
h = """"" as h01,"""" as h02,"""" as h03,"""" as h04,"""" as h05,"""" as h06,"""" as h07,"""" as h08,"""" as h09,"""" as h10"
hdop = """"" as h11,"""" as h12,"""" as h13,"""" as h14,"""" as h15"
nf = 0
For Each i In flist.ItemsSelected
If hide Then If z(rsum(flist.Column(0, i))) > 0 Then B = True Else B = False Else B = True
If B Then
nf = nf + 1
If nf = 11 Then
sellist = sellist & sellistdop
sellistsum = sellistsum & sellistdop
sellistnat = sellistnat & sellistdop
sellistsumnat = sellistsumnat & sellistdop
h = h & "," & hdop
End If 'nf=11
fname = flist.Column(0, i)
If usl Or (nat And (flist.Column(2, i) = "" Or flist.Column(1, i) = "f")) Then
If flist.Column(1, i) = "f" Then
isum = InStr(flist.Column(2, i), ";")
f1 = Mid(flist.Column(2, i), 1, isum - 1) & " as f" & Format(nf, "00")
f1sum = Mid(flist.Column(2, i), isum + 1) & " as f" & Format(nf, "00")
Else
f1 = flist.Column(1, i) & "." & fname & " as f" & Format(nf, "00")
f1sum = "sum(" & flist.Column(1, i) & "." & fname & ") as f" & Format(nf, "00")
End If 'f
h1 = """" & fname & """" & " as h" & Format(nf, "00")
sellist = Replace(sellist, "null as f" & Format(nf, "00"), f1)
sellistsum = Replace(sellistsum, "null as f" & Format(nf, "00"), f1sum)
h = Replace(h, """"" as h" & Format(nf, "00"), h1)
End If 'usl
If nat And flist.Column(2, i) <> "" And flist.Column(1, i) <> "f" Then
If usl Then
If Not secstr Then nf = nf + 1
If nf = 11 And Not secstr Then
sellist = sellist & sellistdop
sellistsum = sellistsum & sellistdop
h = h & "," & hdop
End If ' nf=11
If fnat = 0 Then fnat = nf
End If 'usl in nat
f1 = flist.Column(2, i) & " as f" & Format(nf, "00")
f1sum = "sum(" & flist.Column(2, i) & ") as f" & Format(nf, "00")
h1 = """n" & fname & """" & " as h" & Format(nf, "00")
If Not secstr Then
sellist = Replace(sellist, "null as f" & Format(nf, "00"), f1)
sellistsum = Replace(sellistsum, "null as f" & Format(nf, "00"), f1sum)
Else 'secstr
sellistnat = Replace(sellistnat, "null as f" & Format(nf, "00"), f1)
sellistsumnat = Replace(sellistsumnat, "null as f" & Format(nf, "00"), f1sum)
End If ' not secstr
h = Replace(h, """"" as h" & Format(nf, "00"), h1)
If flist.Column(1, i) = "w" And flist.Column(0, i) <> "UGOL" Then '1)
If formugol <> "" Then formugol = formugol & "+"
If formugolsum <> "" Then formugolsum = formugolsum & "+"
formugol = formugol & "z(f" & Format(nf, "00") & ")"
End If '1)
End If
End If
Next i
'End If
If nat And bnugol Then
For i = 0 To flist.ListCount - 1
If flist.Column(2, i) <> "" And flist.Column(1, i) <> "f" And Not flist.Selected(i) And flist.Column(1, i) = "w" Then
If rsum(flist.Column(0, i)) <> 0 Then
If formugol1 <> "" Then formugol1 = formugol1 & "+"
formugol1 = formugol1 & "z(" & flist.Column(2, i) & ")"
End If 'rsum<>0
End If
Next i
If formugol <> "" And formugol1 <> "" Then formugol = formugol & "+"
formugolsum = formugol
If formugol1 <> "" Then formugolsum = formugol & "sum(" & formugol1 & ")"
formugol = formugol & formugol1
End If 'nat and bnugol
sellistnat = Replace(sellistnat, "#", formugol)
sellistsumnat = Replace(sellistsumnat, "sum(#)", formugolsum)
fnf = nf
If fnf > 15 Then
bm = MsgBox("Число столбцов больше 15", vbOKOnly)
GoTo endp
End If 'fnf>15
If nat Then
If Not secstr Then
fromtxt1 = "(" & fromtxt1 & ") left join Натура99 as n on w.numb1120=n.numb1120  and w.year=n.year"
fromtxt = "((" & fromtxt1 & ")INNER JOIN Имена_областей ON w.OBL = Имена_областей.OBL) INNER JOIN Имена_ОЭС ON w.OES = Имена_ОЭС.oes"
sellist = Replace(sellist, "#", formugol)
sellistsum = Replace(sellistsum, "sum(#)", formugolsum)
Else 'secstr
fromtxt1nat = "(" & fromtxt1 & ") left join Натура99 as n on w.numb1120=n.numb1120 and w.year=n.year"
fromtxtnat = "((" & fromtxt1nat & ")INNER JOIN Имена_областей ON w.OBL = Имена_областей.OBL) INNER JOIN Имена_ОЭС ON w.OES = Имена_ОЭС.oes"
sellistnat = Replace(sellistnat, "#", formugol)
sellistsumnat = Replace(sellistsumnat, "sum(#)", formugolsum)
End If 'not secstr
End If 'nat
fromtxt = "((" & fromtxt1 & ")INNER JOIN Имена_областей ON w.OBL = Имена_областей.OBL) INNER JOIN Имена_ОЭС ON w.OES = Имена_ОЭС.oes"
sqlqr = seltxt & sellist & " FROM " & fromtxt & ";"
sqlqr = Replace(sqlqr, ";", swhere)
If secstr Then
sqlqr = sqlqr & " UNION " & Replace(seltxt, "1 as var", "2 as var") & sellistnat & " FROM " & fromtxtnat & swhere
End If
Set qsum = db.QueryDefs("Справка")
Set qh = db.QueryDefs("СправкаП(заголовок)")
sqlhold = qh.SQL
sqlsumold = qsum.SQL
qh.SQL = "select " & h & " from main;"
If itog Then
sqlsum1 = "Select ""Всего"" as name1,0 as numb1,0 as numb1120,0 as v,w.year,1 as var,null as oblname,null as oesname,0 as oes,0 as obl"
sumvarfrom = ""
sumvargroup = ""
If so.Column(2) <> "no" Then
sqlsum1 = Replace(sqlsum1, "0 as v", "sumvar.v as v")
sumvarfrom = " inner join sumvar on w.v=sumvar.v1 "
sumvargroup = ",sumvar.v "
End If
sqlsum = sqlsum1 & sellistsum & " from " & "(" & fromtxt1 & ")" & sumvarfrom & swhere & vedtxt & " group by w.year" & sumvargroup
If Not secstr Then
qsum.SQL = sqlqr & " union " & sqlsum & IIf(secstr, "", ";")
Else
qsum.SQL = sqlqr & " union " & sqlsum & " UNION " & Replace(sqlsum1, "1 as var", "2 as var") & sellistsumnat & " from (" & fromtxt1nat & ")" & sumvarfrom & swhere & vedtxt & " group by w.year" & sumvargroup & ";"
End If 'not secstr
Else
qsum.SQL = sqlqr & ";"
End If 'itog
If fnf <= 10 Then
DoCmd.OpenReport ("СправкаП"), acPreview
Else
DoCmd.OpenReport ("СправкаП15"), acPreview
End If
qsum.SQL = sqlsumold
qh.SQL = sqlhold
Debug.Print Time
Else 'транспонированная таблица
Debug.Print Time
If nat Then fromtxt1 = "(" & fromtxt1 & ") left join Натура99 as n on w.numb1120=n.numb1120  and w.year=n.year"
usql1 = "Select numb1120,0 as v,year,obl,oes,#f as data,""#n"" as h from [Рабочий(станции)] where #f>0"
If so.Column(2) <> "no" Then usql1 = Replace(usql1, "0 as v", "v")
Set qw = db.QueryDefs("Рабочий(станции)")
Set qu = db.QueryDefs("Справка1п")
wsqlold = qw.SQL
usqlold = qu.SQL
usql = ""
sellist = ""
sellistsum = ""
nf = 1
For Each i In flist.ItemsSelected
If hide Then If z(rsum(flist.Column(0, i))) > 0 Then B = True Else B = False Else B = True
If B Then
fname = flist.Column(0, i)
If usl Or (nat And (flist.Column(2, i) = "" Or flist.Column(1, i) = "f")) Then 'условное
If flist.Column(1, i) = "f" Then
isum = InStr(flist.Column(2, i), ";")
f1 = Mid(flist.Column(2, i), 1, isum - 1) & " as " & fname
f1sum = Mid(flist.Column(2, i), isum + 1)
Else
f1 = flist.Column(1, i) & "." & fname
f1sum = "sum(" & f1 & ")"
End If
h1 = Format(nf, "00") & fname
sellist = sellist & "," & f1
sellistsum = sellistsum & "," & f1sum
usql1f = Replace(usql1, "#f", fname)
usql1f = Replace(usql1f, "#n", h1)
If usql <> "" Then usql = usql & " UNION "
usql = usql & usql1f
nf = nf + 1
End If 'условное
If nat And flist.Column(2, i) <> "" And flist.Column(1, i) <> "f" Then 'натура
f1u = flist.Column(1, i) & "." & fname
f1 = flist.Column(2, i) & " as " & "n" & IIf(fname <> "[intin]", fname, "intin")
h1 = Format(nf, "00") & "n" & fname
sellist = sellist & "," & f1
sellistsum = sellistsum & "," & "sum(" & flist.Column(2, i) & ") as " & "n" & IIf(fname <> "[intin]", fname, "intin")
If InStr(cond, f1u) > 0 Then sellist = sellist & "," & f1u
usql1f = Replace(usql1, "#f", "n" & IIf(fname <> "[intin]", fname, "intin"))
usql1f = Replace(usql1f, "#n", h1)
If usql <> "" Then usql = usql & " UNION "
usql = usql & usql1f
If flist.Column(1, i) = "w" And flist.Column(0, i) <> "UGOL" Then
If formugol <> "" Then formugol = formugol & "+"
formugol = formugol & "z(n" & fname & ")"
End If
nf = nf + 1
End If 'натура
End If
Next i
If nat And bnugol Then
formugol1 = ""
For i = 0 To flist.ListCount - 1
If flist.Column(2, i) <> "" And flist.Column(1, i) <> "f" And Not flist.Selected(i) And flist.Column(1, i) = "w" Then
If rsum(flist.Column(0, i)) <> 0 Then
If formugol1 <> "" Then formugol1 = formugol1 & "+"
formugol1 = formugol1 & "z(" & flist.Column(2, i) & ")"
End If
End If
Next i
If formugol <> "" And formugol1 <> "" Then formugol = formugol & "+"
formugolsum = formugol
If formugol1 <> "" Then formugolsum = formugol & "sum(" & formugol1 & ")"
formugol = formugol & formugol1
End If
sellist = Replace(sellist, "#", formugol)
sellistsum = Replace(sellistsum, "sum(#)", formugolsum)
usql = usql & ";"
wsql = "Select w.numb1120 ,0 as v,w.year,w.obl,w.oes" & sellist & " FROM " & fromtxt1 & swhere
If so.Column(2) <> "no" Then wsql = Replace(wsql, "0 as v", "w.v")
If itog Then
wsqlsum = "Select 0 as numb1120,0 as v,w.year,0 as obl,0 as oes" & sellistsum & " FROM " & fromtxt1 & swhere & vedtxt & " group by w.year;"
wsql = wsql & " union " & wsqlsum
Else
wsql = wsql & ";"
End If
qw.SQL = wsql
qu.SQL = usql
Set ry = db.OpenRecordset("Справка(годы)")
ry.MoveFirst
sprSQL = "Select c.name,ordnumb as numb1,s.numb1120,s.v,s.h,s.obl,s.oes,o.name as oblname,e.name as oesname"
ny = 1
h = ""
ylist = ""
Do While Not ry.EOF
sprSQL = sprSQL & ",[" & ry!YEAR & "] as f" & ny
If h <> "" Then h = h & ","
h = h & """" & ry!YEAR & """ as h" & Format(ny, "00")
If ylist <> "" Then ylist = ylist & ","
ylist = ylist & ry!YEAR
ry.MoveNext
ny = ny + 1
Loop
For i = ny To 15
sprSQL = sprSQL & ",null as f" & i
h = h & ",null as h" & Format(i, "00")
Next i
Set qsprt = db.QueryDefs("Справка1пТ")
sprtsqlold = qsprt.SQL
qsprt.SQL = Replace(qsprt.SQL, "PIVOT Справка1п.year", "PIVOT Справка1п.year " & "IN (" & ylist & ")")
sprSQL = sprSQL & " from ((Справка1пТ as s inner join имена_станций as c on s.numb1120=c.numb) inner join имена_областей as o on s.obl=o.obl) inner join имена_ОЭС as e on s.oes=e.oes;"
Set qspr = db.QueryDefs("Справка1пТ+")
sprsqlold = qspr.SQL
qspr.SQL = sprSQL
Set qh = db.QueryDefs("СправкаП(заголовок)")
sqlhold = qh.SQL
qh.SQL = "select " & h & " from main;"
Debug.Print Time
If ny <= 10 Then
DoCmd.OpenReport ("СправкаТ"), acPreview
Else
DoCmd.OpenReport ("СправкаТ15"), acPreview
End If
qw.SQL = wsqlold
qu.SQL = usqlold
qspr.SQL = sprsqlold
qsprt.SQL = sprtsqlold
qh.SQL = sqlhold
Debug.Print Time
End If
endp:
End Sub

Private Sub Кнопка9_Click()
DoCmd.OpenForm "Условие", , , , , acDialog, "Справка"
End Sub