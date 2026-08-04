Public Function det3(m() As Double) As Double
Dim d11 As Double, d12 As Double, d13 As Double, n As Integer
n = UBound(m, 1)
If n = 2 Then
det3 = m(1, 1) * m(2, 2) - m(1, 2) * m(2, 1)
Else
d11 = m(2, 2) * m(3, 3) - m(2, 3) * m(3, 2)
d12 = m(2, 1) * m(3, 3) - m(2, 3) * m(3, 1)
d13 = m(2, 1) * m(3, 2) - m(2, 2) * m(3, 1)
det3 = m(1, 1) * d11 - m(1, 2) * d12 + m(1, 3) * d13
End If
End Function
Public Function repbetw(s As Variant, s1 As String, s2 As String, s3 As Variant) As Variant
i2 = InStr(1, s, s2, vbTextCompare)
i1 = InStrRev(Mid(s, 1, i2), s1, , vbTextCompare)
repbetw = Mid(s, 1, i1 - 1 + Len(s1)) & s3 & Mid(s, i2)
End Function

Function namegt(gt) As String
If gt = 1 Then
namegt = "газо-мазутные"
ElseIf gt = 2 Then
namegt = "смешанные"
Else
namegt = "на твердом топиве"
End If
End Function
Function gradtopl(B, GAZ, MAZUT, tt) As Double
If tt = 0 Then
gradtopl = 1
ElseIf GAZ > 0 Then
gradtopl = 2
Else: gradtopl = 3
End If
End Function
Function adoFindfield(flist As ADODB.Fields, namet As String) As Integer
Dim i As Integer
For i = 0 To flist.Count - 1
If flist(i).Name = namet Then
adoFindfield = i
GoTo lexit
End If
Next
adoFindfield = -1
lexit:
End Function
Function Findfield(flist As Fields, namet As String) As Integer
Dim i As Integer
For i = 0 To flist.Count - 1
If flist(i).Name = namet Then
Findfield = i
GoTo lexit
End If
Next
Findfield = -1
lexit:
End Function
Public Function Nivh(hb As Double, ph As Double) As Double
If ph > 1.15 Then
de = ph - 1 - 0.05
If hb > 6000 Then
Nivh = 1
ElseIf hb < 2000 Then Nivh = 1 + de
Else
Nivh = 1 + de * (1.5 - hb / 4000)
End If
Nivh = Nivh / (1 + de * 0.5)
Else: Nivh = 1
End If
End Function

Function insertclst(ByVal NUMB1120 As Double, ByVal split As Integer, MAIN As Double) As Double
Dim db As Database, clst As Recordset
Dim maxcode As Recordset, nextcode As Double
Dim cordnumb As Double, nordnumb As Double
Dim OBL As Double, DEP As Double, OES As Double, ER As Double
Set db = DBEngine.Workspaces(0).Databases(0)
Set clst = db.OpenRecordset("Имена_станций", DB_OPEN_TABLE)
Set maxcode = db.OpenRecordset("Макс_код", DB_OPEN_DYNASET)
clst.Index = "numb"
clst.Seek "=", NUMB1120
cordnumb = clst!ordnumb
clst.Index = "ordnumb"
clst.Seek "=", cordnumb
If split = -1 Then
If z(clst!MAIN) = 0 Then
MAIN = clst!NUMB
OBL = clst!OBL
DEP = clst!DEP
OES = clst!OES
ER = clst!ER
clst.Edit
clst!COMP = 1
clst.Update
Else: MAIN = clst!MAIN
End If
End If
clst.MoveNext
nordnumb = clst!ordnumb
clst.AddNew
clst!ordnumb = cordnumb + (nordnumb - cordnumb) / 10
nextcode = maxcode!max_numb + 1
clst!NUMB = nextcode
If split = -1 Then clst!MAIN = MAIN
clst!OBL = OBL
clst!OES = OES
clst!DEP = DEP
clst!ER = ER
clst.Update
insertclst = nextcode
End Function

Function max2(x As Double, y As Double) As Double
If x < y Then max2 = y Else max2 = x
End Function

Function perc(x, y)
If y > 0 Then perc = x / y * 100 Else perc = 0
End Function

Function resetoptions()
Application.SetOption "Confirm Record Changes", True
Application.SetOption "Confirm Document Deletions", True
Application.SetOption "Confirm Action Queries", True
End Function

Function setoptions()
Application.SetOption "Confirm Record Changes", False
Application.SetOption "Confirm Document Deletions", False
Application.SetOption "Confirm Action Queries", False
End Function

Public Function typeob(ob As Double) As Double
If (ob = 90) Or (ob = 91) Or (ob = 20) Or (ob = 21) Or (ob = 22) Then typeob = ob
If (ob > 0) And (ob < 8) Then typeob = 1
If ((ob >= 8) And (ob <= 10)) Or (ob > 91) Then typeob = 94
If ob = 0 Then typeob = 0
End Function

Function z(x) As Double
z = IIf(IsNull(x), 0, x)
End Function

Function Кнопка5_Click()
Dim db As Database, w As Recordset, U As Recordset
Dim bsumnust As Long
Set db = DBEngine.Workspaces(0).Databases(0)
Set w = db.OpenRecordset("Максют1(раб)", DB_OPEN_DYNASET)
Set U = db.OpenRecordset("Удельные", DB_OPEN_TABLE)
U.Index = "numb1"
w.FindFirst "[ved]=2"
bsumnust = 0
Do Until w.NoMatch
If w("year") = 1998 Then
bsumnust = bsumnust + z(w("nust"))
End If
If w("year") = 2000 Then
U.Seek "=", w("numb1")
w.Edit
w("ewtp") = w("qotr") * U("y") / 1000
w("test") = 1
w.Update
End If
w.FindNext "[ved]=2"
Loop
Debug.Print bsumnust

End Function

Sub Счет_Click()
Dim uform As Form, toplform As Form, Dopform As Form, Stoimform As Form
Dim db As Database, w As Form, U As Recordset, topl As Recordset
Dim dop As Recordset, stoim As Recordset
Dim j1 As Integer, j2 As Integer, j As Integer
Dim ekotp As Double, etpotp As Double, sumtopl As Double, sumug As Double, pt As Double
Dim namet As String, nameb As String, ugli As String, ugli1 As String
Set db = DBEngine.Workspaces(0).Databases(0)
Set w = Forms![Edit]![wform].Form
Set uform = Forms![Edit]![uform].Form
Set toplform = Forms![Edit]![toplform].Form
Set Dopform = Forms![Edit]![Dopform].Form
Set Stoimform = Forms![Edit]![Stoimform].Form
Set U = db.OpenRecordset(uform.RecordSource, DB_OPEN_TABLE)
Set topl = db.OpenRecordset(toplform.RecordSource, DB_OPEN_TABLE)
Set dop = db.OpenRecordset(Dopform.RecordSource, DB_OPEN_TABLE)
Set stoim = db.OpenRecordset(Stoimform.RecordSource, DB_OPEN_TABLE)
dop.Index = "numb1"
stoim.Index = "numb1"
U.Index = "numb1"
topl.Index = "numb1"
test = numb1
U.Seek "=", w.numb1
w.EWTP = z(w.QOTR) * z(U!y) / 1000
ekotp = (z(w.E) - z(w.EWTP)) * (1 - z(U("snk")) / 100)
etpotp = z(w.EWTP) * z(U("sntp"))
w.EOTP = ekotp + etpotp
w.EUST = (ekotp * z(U("bk")) + etpotp * z(U("btp"))) / 1000
If w.EOTP > 0 Then w.EURT = w.EUST / w.EOTP * 1000 Else w.EURT = 0
w.TUST = z(w.Q) * z(w.TURT) / 1000
w.B = w.EUST + w.TUST
topl.Seek "=", w.numb1
sumtopl = 0
sumug = 0
nameb = ""
ugli = "kuzn,kan,hak,tuv,irkut,kazah,bur,chit,don,podm,pech,alt,ural,bashk,amur,yakut"
ugli1 = "ugol,nazar,ibor,berez"
j1 = Findfield(topl.Fields, "gaz")
j2 = Findfield(topl.Fields, "proch")
For j = j1 To j2
namet = topl.Fields(j).Name
pt = z(topl.Fields(j).Value)
If InStr(ugli1, namet) = 0 Then
If pt >= 0 Then w(namet) = w("b") * pt / 100
If pt < -1 Then
w(namet) = 0
nameb = namet
End If
sumtopl = sumtopl + z(w(namet))
If InStr(ugli, namet) > 0 Then sumug = sumug + z(w(namet))
End If
Next
If nameb <> "" Then
w(nameb) = w("b") - sumtopl
If InStr(ugli, nameb) > 0 Then sumug = sumug + w(nameb)
End If
w("ugol") = sumug
If z(w("kan")) > 0 Then
j1 = Findfield(topl.Fields, "nazar")
If j1 > 0 Then
dop.Seek "=", w("numb1")
If dop.NoMatch Then
dop.AddNew
dop!numb1 = w.numb1
dop!NUMB1120 = w.NUMB1120
dop!YEAR = w.YEAR
dop.Update
dop.Move 0, dop.LastModified
End If
dop.Edit
'добавила
stoim.Seek "=", w("numb1")
If stoim.NoMatch Then
stoim.AddNew
stoim!numb1 = w.numb1
stoim!NUMB1120 = w.NUMB1120
stoim!YEAR = w.YEAR
stoim!Name = w.Name
stoim.Update
stoim.Move 0, stoim.LastModified
End If
stoim.Edit
'конец
If z(topl("nazar")) >= 0 Then dop!nazar = w.B * z(topl("nazar")) / 100
If z(topl("ibor")) >= 0 Then dop!ibor = w.B * z(topl("ibor")) / 100
If z(topl("berez")) >= 0 Then dop!berez = w.B * z(topl("berez")) / 100
If z(topl("nazar")) < -1 Then dop!nazar = w("kan") - z(dop!berez) - z(dop!ibor)
If z(topl("ibor")) < -1 Then dop!ibor = w("kan") - z(dop!berez) - z(dop!nazar)
If z(topl("berez")) < -1 Then dop!berez = w("kan") - z(dop!nazar) - z(dop!ibor)
dop.Update
End If
End If


End Sub

Public Function Interval(bk As Double, bkcp As Double) As Double
Dim delta As Double
deltam = bkcp * 0.1
deltap = bkcp * 0.1
If bk < bkcp - deltam Then Interval = 1
If (bk >= bkcp - deltam And bk < bkcp) Then Interval = 2
If (bk = bkcp) Then Interval = 3
If (bk > bkcp And bk < bkcp + deltap) Then Interval = 4
If (bk >= bkcp + deltap) Then Interval = 5

End Function



Public Function link()

End Function


Public Function Min2(x As Double, y As Double) As Double
If x < y Then Min2 = x Else Min2 = y
End Function

Public Function betw(s As Variant, s1 As String, s2 As String) As String
Dim i1 As Integer, i2 As Integer
i1 = InStr(s, s1)
If i1 > 0 Then
i2 = InStr(Mid(s, i1 + 5), s2)
betw = Mid(s, i1 + 5, i2 - 1)
Else
betw = ""
End If
End Function

Public Function CNT(nt99 As Double, nt05 As Double, nt10 As Double, nt15 As Double) As String
Dim s As String, dnt As Double
s = ""
If nt99 <> nt05 Then s = s & "2005=" & Format((nt05 - nt99), "#####") & ";"
If nt10 <> nt05 Then s = s & "2010=" & Format((nt10 - nt05), "#####") & ";"
If nt15 <> nt10 Then s = s & "2015=" & Format((nt15 - nt10), "#####") & ";"
CNT = s
End Function

Public Function QOTR(Q As Double, Potr As Double, ntb As Double, NT As Double, HT As Double)
If ntb > 0 Then
If NT >= ntb Then
QOTR = Q * Potr / 100
Else
QOTR = Min2(Q * Potr / 100, NT * HT / 1000)
End If
Else
If NT > 0 Then QOTR = Q * 0.85 Else QOTR = 0
End If
End Function

Public Function test()
Dim db As Database, R As Recordset
Set db = DBEngine.Workspaces(0).Databases(0)
Debug.Print SysCmd(acSysCmdAccessDir)
End Function

Public Function Update(source As String, dest As String, sindxs As String, app As Boolean) As Boolean
Dim db As Database, i As Integer, i1 As Integer, wndx As Index, f As field, keyns(10) As Variant, nkeys As Integer
Dim sf As New ADODB.Recordset, df As New ADODB.Recordset, st As New ADODB.Recordset, dfdef As TableDef, s As String
Dim flist As ADODB.Fields
Dim keyvs() As Variant, v As Variant
Set db = DBEngine.Workspaces(0).Databases(0)
sf.Open source, CurrentProject.Connection, adOpenDynamic
Set dfdef = db.TableDefs(dest)
Set wndx = dfdef.CreateIndex("wndx")
i1 = 1
nkeys = 1
For i = 1 To Len(sindxs)
If Mid(sindxs, i, 1) = "+" Then
Set f = wndx.CreateField(Mid(sindxs, i1, i - i1))
keyns(nkeys - 1) = Mid(sindxs, i1, i - i1)
wndx.Fields.Append f
nkeys = nkeys + 1
i1 = i + 1
End If
Next
ReDim keyvs(nkeys - 1)
Set f = wndx.CreateField(Mid(sindxs, i1, i - i1))
keyns(nkeys - 1) = Mid(sindxs, i1, i - i1)
wndx.Fields.Append f
dfdef.Indexes.Append wndx
df.Open dest, CurrentProject.Connection, adOpenDynamic, adLockOptimistic, adCmdTableDirect
df.Index = "wndx"
'добавила
'st.Open dest, CurrentProject.Connection, adOpenDynamic, adLockOptimistic, adCmdTableDirect
'st.Index = "wndx"
'конец
sf.MoveFirst
Do Until (sf.EOF)
For i = 0 To nkeys - 1
keyvs(i) = sf(keyns(i))
Next
df.Seek keyvs, adSeekFirstEQ
If df.EOF Then
If app Then
df.AddNew
Else
df.MoveLast
GoTo nxts
End If
End If
'добавила
Next
st.Seek keyvs, adSeekFirstEQ
If st.EOF Then
If app Then
st.AddNew
Else
st.MoveLast
GoTo nxts
End If
End If
'конец
For i = 0 To sf.Fields.Count - 1
i1 = adoFindfield(df.Fields, sf.Fields(i).Name)
If i1 > -1 Then df.Fields(i1).Value = sf.Fields(i).Value
df.Update
Next
df.Update
nxts: sf.MoveNext
Loop
df.Close
dfdef.Indexes.Delete "wndx"
'добавила
For i = 0 To sf.Fields.Count - 1
i1 = adoFindfield(st.Fields, sf.Fields(i).Name)
If i1 > -1 Then st.Fields(i1).Value = sf.Fields(i).Value
st.Update
Next
st.Update
nxts: sf.MoveNext
Loop
st.Close
dfdef.Indexes.Delete "wndx"
'конец
End Function

Public Function repstring(s1 As String, s2 As String, s3 As String) As String
repstring = Replace(s1, s2, s3)
End Function

Public Function maxval(ParamArray x())
maxval = 0
For i = 0 To UBound(x)
If x(i) > maxval Then maxval = x(i)
Next i
End Function

Public Function nyear(YEAR As Double, list As String) As Integer
i = InStr(list, Format(YEAR, "0000"))
nyear = (i - 1) / 5 + 1
End Function

Public Function kn(k As Variant, ka As Double, y As Double) As Variant
If y < 1999 Then kn = Null Else kn = IIf(z(k) > 0, k, ka)
End Function