Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False


Private Sub first_Click()
Dim R As DAO.Recordset
i = oeslst.ListIndex
i1 = [type].ListIndex
i2 = varlst.ListIndex
codeoes = oeslst.Column(1, i)
typetxt = [type].Column(1, i1)
vartxt = varlst.Column(1, i2)
fltrtxt = "(oes=" & codeoes & ") and (" & typetxt & ")"
Debug.Print fltrtxt
Set R = RecordsetClone
R.FindFirst "filter=" & """" & fltrtxt & """  and wname=""" & vartxt & """"
If R.NoMatch Then
bmsg = MsgBox("Запись не найдена", vbOKOnly)
GoTo endp
End If
Bookmark = R.Bookmark
endp:
End Sub

Private Sub Form_Current()
ce = Null
End Sub

Private Sub Form_Open(Cancel As Integer)
varlst = DFirst("[name]", "Список-вариантов")
End Sub

Private Sub hngt_AfterUpdate()
kngt = hngt / ch
End Sub

Private Sub hnpg_AfterUpdate()
knpg = hnpg / ch
End Sub

Private Sub hnps_BeforeUpdate(Cancel As Integer)
knps = hnps / ch
End Sub

Private Sub next_Click()
DoCmd.GoToRecord , , acNext
End Sub

Private Sub oes_AfterUpdate()
End Sub

Private Sub prev_Click()
DoCmd.GoToRecord , , acPrevious
End Sub



Private Sub Добавить_Click()
Dim db As Database, vars As DAO.Recordset
Set db = CurrentDb
i = oeslst.ListIndex
i1 = [type].ListIndex
i2 = varlst.ListIndex
codeoes = oeslst.Column(1, i)
vartxt = varlst.Column(1, i2)
typetxt = [type].Column(1, i1)
tname = [type].Column(0, i1) & " " & oeslst
If [type].Column(0, i1) = "Другой" Then
DoCmd.OpenForm "Условие", acNormal, , , , acDialog, "Расчет"
typetxt = Replace(Me!cond, "w.", "")
tname = InputBox("Введите название", vbOKOnly)
End If
fltrtxt = "(oes=" & codeoes & ")"
Set vars = db.OpenRecordset("Список-вариантов", DB_OPEN_DYNASET)
vars.FindFirst "name=""" & varlst & """"
ay = split(vars!years, ",")
ny = UBound(ay) + 1
Set R = RecordsetClone
If R.RecordCount = 0 Then
n1 = 1
n2 = 100
Else:
R.FindFirst "filter=""" & fltrtxt & " and (" & typetxt & ")"" And wname = """ & vartxt & """"
If Not R.NoMatch Then
bmsg = MsgBox("Запись уже существует")
GoTo endp
End If
R.FindLast "filter like ""*" & fltrtxt & "*"""
If R.NoMatch Then
n1 = (codeoes - 1) * 100
n2 = n1 + 100
Else
R.FindLast "filter like ""*" & fltrtxt & "*"" And wname = """ & vartxt & """"
n1 = R!numb
R.MoveNext
If R.EOF Then n2 = n1 + 100 Else n2 = R!numb
End If
End If
Call setoptions
step = IIf(n1 + ny < n2, 1, (n2 - n1) / IIf(ny < 10, 10, 100))
bklvalue = IIf(codeoes = 6 Or codeoes = 7 Or codeoes = 9, 450, 400)
For i = 0 To ny - 1
If ay(i) <> "2007" Then
sqlins = "INSERT INTO [параметры-распределения] (name,[year],filter,wname,uname,toplname,dopname,byear,numb,bkl)"
sqlins = sqlins & " values(" & """" & tname & """," & ay(i) & "," & """(oes=" & codeoes & ") and (" & typetxt & ")""" & ",""" & vars!wname & """"
sqlins = sqlins & ",""" & vars!uname & """,""" & vars!topleur & """,""" & vars!dopname & """," & vars!byear & "," & Replace(n1 + 1 + i * step, ",", ".") & "," & bklvalue & ");"
DoCmd.RunSQL sqlins
End If
Next i
Requery
Call resetoptions
endp:
End Sub

Private Sub Кнопка27_Click()
'распределение
Dim db As Database, w As DAO.Recordset, U As DAO.Recordset, otet As Database, class As DAO.Recordset
Dim hb As Double, csume As Double, Kh As Double, kl As Double, koptim As Double
Dim bm As String, nit As Integer, doptim As Double, nustb As Double, e1 As Double
Dim kplus As Double, kmin As Double, ke As Double
Dim restr As DAO.Recordset
Set db = DBEngine.Workspaces(0).Databases(0)
Set w = db.OpenRecordset(wname, DB_OPEN_DYNASET)
Set U = db.OpenRecordset(uname, DB_OPEN_TABLE)
Set otet = DBEngine.OpenDatabase("F:/Базы данных/ОТЭТ")
Set class = otet.OpenRecordset("Имена_станций", DB_OPEN_TABLE)
koblreset = 0
prestr.Value = 0
prestr.Min = 0
prestr.Max = 15
irestr = 1
BDis:
class.Index = "numb"
pb.Max = 15
pb.Min = 0
pb.Value = 0
doptim = Me.doptim
If (ph > 1 - doptim) And (ph < 1) Then
kmin = 2 * ph - 1
kplus = 1
ElseIf (ph > 1) And (ph < 1 + doptim) Then
kmin = 1
kplus = 2 * ph - 1
Else
kmin = ph - doptim
kplus = ph + doptim
End If
U.Index = "numb2"
nit = 1
kl = k - 0.1
Kh = k + 0.1
kln = kn - 0.1
khn = kn + 0.1
again:
csume = 0
kobl = 1
brestr = False
For i = 0 To Forms.Count - 1
If Forms(i).Name = "Анализ_по_областям" Then
Set restr = Forms(i).Form!Ограничения.Form.RecordsetClone
brestr = True
GoTo restrfound
End If
Next i
If koblreset = 0 Then
Call setoptions
ioes = InStr(filter1, "oes")
codeoes = Mid(filter1, ioes + 4, 1)
sqllim = "update Ограничения set kobl=1 where oes=" & codeoes & ";"
Debug.Print sqllim
DoCmd.RunSQL (sqllim)
koblreset = 1
Call resetoptions
End If
restrfound:
w.FindFirst filter1
Do Until w.NoMatch
If w("year") = byear Then
hb = z(w("h"))
nustb = z(w!NUST)
End If
If w("year") = cyear Then
If brestr Then 'ограничения по областям
restr.FindFirst "obl=" & w!OBL
If Not (restr.NoMatch) Then 'есть ограничения
kobl = restr!kobl
Else 'нет ограничений
restr.FindFirst "obl=" & 100 + w!oes
kobl = restr!kobl
End If 'есть ограничения или нет
End If 'ограничения по областям
U.Seek ">=", w("numb1120"), w!v, byear
If U.NoMatch Then GoTo skip1
Do While (U!numb1120 = w!numb1120)
If U!year > w!year Then GoTo endu
If U!year <= w!year Then bm = U.Bookmark
U.MoveNext
If U.EOF Then GoTo endu
Loop
endu: U.Bookmark = bm
w.Edit
If z(w!NUST) > 0 And z(w!NR) = 0 And z(w!HFIX) <> 1 Then
class.Seek "=", w!numb1120
stname = class!Name
bmsg = MsgBox(stname & " нет располагаемой мощности.Зафиксировать H=0?", vbYesNo)
If bmsg = vbYes Then
w!H = 0
w!HFIX = 1
End If
End If
If z(w("hfix")) = 1 Then GoTo calce
If hb = 0 Then
If w("obor") = 20 Or w("obor") = 90 Then w("h") = ch * kngt
If w("obor") = 21 Or w("obor") = 91 Then w("h") = ch * knpg
If w("obor") <> 20 And w("obor") <> 90 And w("obor") <> 21 And w("obor") <> 91 Then w("h") = ch * knps
GoTo calce
End If
If U!Bk < 350 Then
koptim = kplus
ElseIf U!Bk > 550 Then
koptim = kmin
Else
koptim = kmin + (kplus - kmin) * (2.75 - z(U!Bk) / 200)
End If
ke = Nivh(hb, ph)
w!H = hb * koptim * k * ke * kobl
If hb > 7000 And w!H > hb Then w!H = hb
If hb > 6000 And hb < 7000 And hd < 6000 And w!H > hb * 1.05 Then
If hb * 1.05 < 7000 Then w!H = hb * 1.05 Else w!H = 7000
Else: If w!H > 7000 Then w!H = 7000
End If
'Debug.Print w!numb1120; w!H; hb; hd
calce:
If (w!OBOR >= 8) And (w!OBOR <= 10) Then
w!E = w!EWTP
Else
If z(w!NUST) > nustb And z(w!H) > ch And nustb > 0 And z(w!HFIX <> 1) Then
e1 = (nustb * z(w!H) + (z(w!NUST) - nustb) * ch) / 1000
Else: e1 = z(w!NUST) * z(w!H) / 1000
End If
w!E = max2(e1, z(w!EWTP) * 1.04)
End If
If z(w!NUST) > 0 Then w!H = w!E / w!NUST * 1000
csume = csume + z(w!E)
w.Update
End If
skip1: w.FindNext filter1
Loop
ce = csume
If (Abs(E - csume) < 0.3) Or nit > 15 Then GoTo enddis
If bnust > 0 Then
If E > csume Then kl = k Else Kh = k
Else
If E > csume Then kln = kn Else khn = kn
knps = knps * kn / ((kln + khn) / 2)
kngt = kngt * kn / ((kln + khn) / 2)
knpg = knpg * kn / ((kln + khn) / 2)
kn = (kln + khn) / 2
End If
pb.Value = nit
nit = nit + 1
k = (kl + Kh) / 2
GoTo again
enddis:
pb.Value = 15
If brestr Then
lim = 1
Call Ограничения_Click
irestr = irestr + 1
prestr.Value = irestr
If irestr < 15 Then GoTo BDis
'With Forms("анализ_по_областям").Form!Ограничения.Form
'.Recalc
'.Requery
'End With
Else
lim = 0
End If
End Sub

Private Sub Кнопка49_Click()
Dim s As String, w1 As DAO.Recordset
Dim db As Database, marks As DAO.Recordset, w As DAO.Recordset, U As DAO.Recordset, topl As DAO.Recordset
Dim dop As DAO.Recordset, bm As String, bm1 As String
Dim j As Integer, j1 As Integer, j2 As Integer, j3 As Integer, j4 As Integer, j5 As Integer
Dim ekotp As Double, etpotp As Double, sumtopl As Double, sumug As Double, pt As Double
Dim namet As String, nameb As String, ugli As String, ugli1 As String
Set db = DBEngine.Workspaces(0).Databases(0)
Set w = db.OpenRecordset(wname, DB_OPEN_DYNASET)
Set U = db.OpenRecordset(uname, DB_OPEN_TABLE)
Set topl = db.OpenRecordset(toplname, DB_OPEN_TABLE)
Set dop = db.OpenRecordset(dopname, DB_OPEN_TABLE)
dop.Index = "numb1"
U.Index = "numb2"
topl.Index = "numb2"
pb.Max = 100
pb.Min = 0
pb.Value = 0
s = "SELECT count(numb1)as n FROM [" & wname & "]where(" & filter1 & "and (year=" & cyear & "));"
Set w1 = db.OpenRecordset(s)
n = w1!n
w1.Close
nrec = 1
w.FindFirst filter1
Do Until w.NoMatch
If z(w("year")) = cyear Then
U.Seek ">=", w("numb1120"), w!v, byear
If U.NoMatch Then GoTo skip2
Do While (U!numb1120 = w!numb1120)
If U!year > w!year Then GoTo endu2
If U!year <= w!year Then bm = U.Bookmark
U.MoveNext
If U.EOF Then GoTo endu2
Loop
endu2: U.Bookmark = bm

w.Edit
w!EWTP = z(w!QOTR) * z(U!y) / 1000
If (w!VED = 1 Or w!VED = 4) And U!Ksn > 0 And w!NUST > 0 Then
ekotp = (z(w!E) - z(w!EWTP)) * (1 - (U!snbas - ((w!E / w!NUST) / 8.76) * U!Ksn) / 100)
Else
ekotp = (z(w!E) - z(w!EWTP)) * (1 - z(U("snk")) / 100)
End If
etpotp = z(w("ewtp")) * z(U("sntp"))
w("eotp") = ekotp + etpotp
Debug.Print w!VED
If (w!VED = 1 Or w!VED = 4) And U!Kh > 0 And w!NUST > 0 Then
w!EUST = w!EOTP * (U!bbas - ((w!E / w!NUST) / 8.76) * U!Kh) / 1000
Else
w!EUST = (ekotp * z(U("bk")) + etpotp * z(U("btp"))) / 1000
End If
If w("eotp") > 0 Then w("eurt") = w("eust") / w("eotp") * 1000 Else w("eurt") = 0
w("tust") = z(w("q")) * z(w("turt")) / 1000
w("b") = w("eust") + w("tust")
topl.Seek ">=", w("numb1120"), w!v, byear
If topl.NoMatch Then GoTo skip2
Do While (topl!numb1120 = w!numb1120)
If topl!year > w!year Then GoTo endtop2
If topl!year <= w!year Then bm1 = topl.Bookmark
topl.MoveNext
Loop
endtop2: topl.Bookmark = bm1
'новые формулы
topls = ",gaz,mazut,torf,slan,gtt,proch,"
ugli = ",ugol,kuzn,kan,hak,tung,tuv,irkut,kazah,bur,chit,don,podm,pech,alt,ural,bashk,karag,amur,urg,prim,luch,yakut,sah,mag,chukot,kamch,ushum,tal"
ugli1 = ",nazar,ibor,berez,per,irbei,kansk,gusin,tugn,okino,azey,cher,jer,karab,mug,har,urt,tataur,tarbag,zab_kam,vork,intin,sver,chel,kizel,sosv,neru,zyryan,pyak,rai,erk,svo,bikin,razdol,hankai,bering,anad,ekib,maikub,kuznt,kuzngd,kuznss,kuznun,gazpp,koksdom,prochgaz,tvproch,"
bdop = False
If Not (IsNull(topl("formtxt"))) Then
ost = w!B
at = split(topl!formtxt & ";", ";")
sumugol = 0
lev = 0
bpech = False
bkuzn = False
bkan = False
btung = False
bural = False
birkut = False
bbur = False
bchit = False
byakut = False
bamur = False
bprim = False
bkazah = False
bchukot = False
bgazpp = False
bproch = False
usedt = ","
For i = 0 To UBound(at) - 1
dopugol = False
ie = InStr(at(i), "=")
If ie > 0 Then
namet = Mid(at(i), 1, ie - 1)
If Mid(namet, 1, 1) = "/" Then
lev = 1
namet = Mid(namet, 2)
End If
Else
namet = at(i)
nametost = namet
End If
usedt = usedt & namet & ","
If namet = "intin" Or namet = "vork" Then bpech = True
If namet = "kuznt" Or namet = "kuznss" Or namet = "kuzngd" Or namet = "kuznun" Then bkuzn = True
If namet = "nazar" Or namet = "ibor" Or namet = "berez" Or namet = "per" Or namet = "irbei" Or namet = "kansk" Then bkan = True
If namet = "sver" Or namet = "chel" Or namet = "kizel" Or namet = "sosv" Then bural = True
If namet = "azey" Or namet = "mug" Or namet = "cher" Then birkut = True
If namet = "gusin" Or namet = "tugn" Or namet = "okino" Then bbur = True
If namet = "har" Or namet = "urt" Or namet = "tataur" Or namet = "tarbag" Or namet = "zab_kam" Then bchit = True
If namet = "neru" Or namet = "zyryan" Or namet = "pyak" Then byakut = True
If namet = "rai" Or namet = "erk" Or namet = "svo" Then bamur = True
If namet = "gazpp" Then bgazpp = True
If namet = "koksdom" Or namet = "prochgaz" Or namet = "tvproch" Then bproch = True
If namet = "jer" Or namet = "karab" Then btung = True
If namet = "bikin" Or namet = "razdol" Or namet = "hankai" Then bprim = True
If namet = "bering" Or namet = "anad" Then bchukot = True
If namet = "ekib" Or namet = "maikub" Then bkazah = True
If InStr(ugli1, "," & namet & ",") > 0 Then 'доп угли
dopugol = True
If Not bdop Then
dop.Seek "=", w("numb1"), w!v, w!year
If dop.NoMatch Then
dop.AddNew
dop!numb1 = w!numb1
dop!numb1120 = w!numb1120
dop!year = w!year
dop.Update
dop.Move 0, dop.LastModified
End If
dop.Edit
bdop = True
End If ' not bdop
End If 'доп угли
If ie > 0 Then
ptvalue = CDbl(Mid(at(i), ie + 1))
If ptvalue >= 0 Then 'проценты
If lev = 0 Then tvalue = w!B * ptvalue / 100 Else tvalue = ost * ptvalue / 100
Else
If dopugol Then tvalue = z(dop(namet)) Else tvalue = z(w(namet))
End If 'проценты или абсолютн
ost = ost - tvalue
If Not dopugol Then 'основные угли
w(namet) = tvalue
Else 'доп угли
dop(namet) = tvalue
End If 'доп угли
End If ' ie>0
Next i
If InStr(ugli1, "," & nametost & ",") > 0 Then dop(nametost) = ost Else w(nametost) = ost
If Not bdop Then
dop.Seek "=", w("numb1"), w!v, w!year
If dop.NoMatch Then GoTo sumdop
dop.Edit
End If
For i = 0 To dop.Fields.Count - 1
fname = dop.Fields(i).Name
If InStr(1, ugli1, "," & fname & ",", vbTextCompare) > 0 And InStr(1, usedt, "," & fname & ",", vbTextCompare) = 0 Then dop(fname) = 0
Next i
dop.Update
sumdop:
If bpech Then
w("pech") = dop("intin") + dop("vork")
usedt = usedt & "pech,"
End If
If bkuzn Then
w("kuzn") = dop("kuznt") + dop("kuznss") + dop("kuzngd") + dop("kuznun")
usedt = usedt & "kuzn,"
End If
If bkan Then
w("kan") = dop("nazar") + dop("ibor") + dop("berez") + dop("per") + dop("irbei") + dop("kansk")
usedt = usedt & "kan,"
End If
If bural Then
w("ural") = dop("sver") + dop("chel") + dop("kizel") + dop("sosv")
usedt = usedt & "ural,"
End If
If birkut Then
w("irkut") = dop("azey") + dop("mug") + dop("cher")
usedt = usedt & "irkut,"
End If
If bbur Then
w("bur") = dop("gusin") + dop("tugn") + dop("okino")
usedt = usedt & "bur,"
End If
If bchit Then
w("chit") = dop("har") + dop("urt") + dop("tataur") + dop("tarbag") + dop("zab_kam")
usedt = usedt & "chit,"
End If
If byakut Then
w("yakut") = dop("neru") + dop("pyak") + dop("zyryan")
usedt = usedt & "yakut,"
End If
If bamur Then
w("amur") = dop("rai") + dop("erk") + dop("svo")
usedt = usedt & "amur,"
End If
If bgazpp Then
w("gaz") = w("gaz") + dop("gazpp")
usedt = usedt & "gaz,"
End If
If bproch Then
w("proch") = dop("koksdom") + dop("prochgaz") + dop("tvproch")
usedt = usedt & "proch,"
End If
If btung Then
w("tung") = dop("jer") + dop("karab")
usedt = usedt & "tung,"
End If
If bprim Then
w("prim") = dop("bikin") + dop("razdol") + dop("hankai")
usedt = usedt & "prim,"
End If
If bchukot Then
w("chukot") = dop("bering") + dop("anad")
usedt = usedt & "chukot,"
End If
If bkazah Then
w("kazah") = dop("ekib") + dop("maikub")
usedt = usedt & "kazah,"
End If
For i = 0 To w.Fields.Count - 1
fname = w.Fields(i).Name
fname1 = fname
If InStr(1, topls & ugli, "," & fname & ",", vbTextCompare) > 0 And InStr(1, usedt, "," & fname & ",", vbTextCompare) = 0 Then w(fname) = 0
If InStr(1, ugli, "," & fname & ",", vbTextCompare) > 0 And fname <> "ugol" Then sumugol = sumugol + w(fname)
Next i
w("ugol") = sumugol
End If
'  новые формулы конец
w.Update
pb.Value = nrec / n * 100
nrec = nrec + 1
End If
skip2: w.FindNext filter1
Loop
End Sub

Private Sub Кнопка5_Click()
'коэффициенты
Dim db As Database, w As DAO.Recordset, U As DAO.Recordset
Dim bsumnust As Double, bsume As Double, bsumetp As Double, bsumq As Double, bsumqotr As Double
Dim csumnust As Double, csumetp As Double, csumq As Double, csumqotr As Double
Dim bm As String, bnust1 As Double, csumnustn As Double, knew As Double
Set db = DBEngine.Workspaces(0).Databases(0)
Set w = db.OpenRecordset(wname, DB_OPEN_DYNASET)
Set U = db.OpenRecordset(uname, DB_OPEN_TABLE)
U.Index = "numb2"
w.FindFirst filter1
bsumnust = 0
bsume = 0
bsumetp = 0
bsumq = 0
bsumqotr = 0
csumnust = 0
csumnustn = 0
csumnustngt = 0
csumnustnpg = 0
csumetp = 0
csumq = 0
csumqotr = 0
Do Until w.NoMatch
'Debug.Print W!year; " "; z(W!NUST)
If w("year") = byear Then
bsumnust = bsumnust + z(w("nust"))
bnust1 = z(w("nust"))
bsume = bsume + z(w("e"))
bsumetp = bsumetp + z(w("ewtp"))
bsumq = bsumq + z(w("q"))
bsumqotr = bsumqotr + z(w("qotr"))
End If
If w("year") = cyear Then
U.Seek ">=", w("numb1120"), w!v, byear
If U.NoMatch Then GoTo Skip
Do While (U!numb1120 = w!numb1120)
If U!year > w!year Then GoTo endu1
If U!year <= w!year Then bm = U.Bookmark
U.MoveNext
If U.EOF Then GoTo endu1
Loop
endu1:
U.Bookmark = bm
w.Edit
w("ewtp") = w("qotr") * U("y") / 1000
csumnust = csumnust + z(w("nust"))
If bnust1 = 0 Then
csumnustn = csumnustn + z(w("nust"))
If w("obor") = 20 Or w("obor") = 90 Then csumnustngt = csumnustngt + z(w("nust"))
If w("obor") = 21 Or w("obor") = 91 Then csumnustnpg = csumnustnpg + z(w("nust"))
End If
csumetp = csumetp + z(w("ewtp"))
csumq = csumq + z(w("q"))
csumqotr = csumqotr + z(w("qotr"))
w.Update
End If
Skip: w.FindNext filter1
Loop
bnust = bsumnust
BE = bsume
betp = bsumetp
bq = bsumq
bqotr = bsumqotr
cnust = csumnust
cnustn = csumnustn
cnustngt = csumnustngt
cnustnpg = csumnustnpg
cnustnps = cnustn - cnustngt - cnustnpg
cetp = csumetp
cq = csumq
cqotr = csumqotr
If bsume > 0 Then bptp = bsumetp / bsume * 100 Else bptp = 0
cptp = csumetp / E * 100
If bsumnust > 0 Then bh = bsume / bsumnust * 1000 Else bh = 0
ch = E / csumnust * 1000
If bh > 0 Then ph1 = ch / bh Else ph1 = 0
If BE > 0 Then pe = E / BE Else pe = 0
If (cnust - cnustn) > 0 Then hd = (E - (cnustnps * knps + cnustngt * kngt + cnustnpg * knpg) * ch / 1000) / (cnust - cnustn) * 1000 Else hd = 0
If cnustn > 0 Then kn = (cnustnps * knps + cnustngt * kngt + cnustnpg * knpg) / cnustn
If bh > 0 Then ph = hd / bh Else ph = 0
If bq > 0 Then pq = cq / bq Else pq = 0
If bqotr > 0 Then potr = cqotr / bqotr Else potr = 0
End Sub

Private Sub Кнопка97_Click()
DoCmd.OpenForm "Фиксированные_часы", , , filter1
End Sub
Private Sub Кнопка125_Click()
On Error GoTo Err_Кнопка125_Click


    Screen.PreviousControl.SetFocus
    DoCmd.FindNext

Exit_Кнопка125_Click:
    Exit Sub

Err_Кнопка125_Click:
    MsgBox Err.Description
    Resume Exit_Кнопка125_Click
    
End Sub

Private Sub Ограничения_Click()
Dim restr As DAO.Recordset, sumobl As DAO.Recordset, sumobldis As DAO.Recordset, sumproch As DAO.Recordset, sumprochdis As DAO.Recordset, db As Database
lim = Forms("Расчет").Form!lim
DoCmd.OpenForm "Анализ_по_областям", acNormal
i = InStr(filter1, "oes=")
codeoes = Mid(filter1, i + 4, 1)
Forms("Анализ_по_областям").Form!Ограничения.Form.filter = "(oes=" & codeoes & ") and (year=" & cyear & ")"
Forms("Анализ_по_областям").Form!Ограничения.Form.FilterOn = True
Set restr = Forms("Анализ_по_областям").Form!Ограничения.Form.RecordsetClone
restr.MoveFirst
fltrproch = ""
deltaoes = 0
Do While restr!OBL <> 100 + codeoes
fltrproch = fltrproch & IIf(fltrproch = "", "", " or ") & "obl=" & restr!OBL
sumoblsql = "Select SUM(E) as esum,SUM(NUST) as nsum from [" & wname & "] where (ved>0) and (year=" & cyear & ") and (obl=" & restr!OBL & ");"
sumobldissql = "Select SUM(E) as esum,SUM(NUST) as nsum,SUM(ewtp) as etpsum from [" & wname & "] where " & filter1 & " and (year=" & cyear & ") and (obl=" & restr!OBL & ");"
Set db = CurrentDb
Set sumobl = db.OpenRecordset(sumoblsql)
Set sumobldis = db.OpenRecordset(sumobldissql)
restr.Edit
If lim = 0 Then restr!kobl = 1
restr!ecur = sumobl!esum
restr!H = sumobl!esum / sumobl!nsum * 1000
restr!ecurdis = sumobldis!esum
restr!Hdis = sumobldis!esum / sumobldis!nsum * 1000
restr!etp = sumobldis!etpsum
If z(restr!emin) > 0 And restr!ecur < restr!emin Then 'ниже минимума
restr!kobl = restr!kobl * (restr!emin - restr!ecur + restr!ecurdis) / restr!ecurdis
deltaoes = deltaoes + restr!emin - restr!ecur
End If 'ниже минимума
If z(restr!emax) > 0 And restr!ecur > restr!emax Then 'выше максимума
restr!kobl = restr!kobl * (restr!emax - restr!ecur + restr!ecurdis) / restr!ecurdis
deltaoes = deltaoes + restr!emax - restr!ecur
End If 'выше максимума
restr.Update
esumrestr = esumrestr + sumobl!esum
restr.MoveNext
Loop
sumprochsql = "Select SUM(E) as esum,SUM(NUST) as nsum from [" & wname & "] where (ved>0) and (year=" & cyear & ") and (oes=" & codeoes & ") and not(" & fltrproch & ");"
Set sumproch = db.OpenRecordset(sumprochsql)
sumprochdissql = "Select SUM(E) as esum,SUM(NUST) as nsum,SUM(ewtp) as etpsum from [" & wname & "] where (ved>0) and (year=" & cyear & ") and (" & filter1 & ") and not(" & fltrproch & ");"
Set sumprochdis = db.OpenRecordset(sumprochdissql)
restr.Edit
restr!ecur = sumproch!esum
restr!H = sumproch!esum / sumproch!nsum * 1000
restr!ecurdis = sumprochdis!esum
restr!kobl = restr!kobl * (sumprochdis!esum - deltaoes) / sumprochdis!esum
restr!etp = sumprochdis!etpsum
restr.Update
Forms("Расчет").Form!lim = 1
End Sub



Private Sub Справка_Click()
fltroes = "oes=" & oeslst.Column(1, oeslst.ListIndex)
fltr = "instr(filter,""" & fltroes & """)>0"
Debug.Print fltr
DoCmd.OpenForm "Справка_расчет", acNormal
Forms("Справка_расчет").Form!sdis.Form.filter = fltr
Forms("Справка_расчет").Form!sdis.Form.FilterOn = True
End Sub
Private Sub Кнопка135_Click()
On Error GoTo Err_Кнопка135_Click


    Screen.PreviousControl.SetFocus
    DoCmd.FindNext

Exit_Кнопка135_Click:
    Exit Sub

Err_Кнопка135_Click:
    MsgBox Err.Description
    Resume Exit_Кнопка135_Click
    
End Sub

Private Sub Статистика_Click()
DoCmd.OpenForm "Статистика", acNormal
With Forms("Статистика").Form!Sres.Form
rs = Forms("Статистика").Form!Sres.Form.RecordSource
rs1 = Replace(rs, "Станции(макет)", wname)
.RecordSource = rs1
.filter = "(year=" & cyear & ") and (" & filter1 & ")"
.FilterOn = True
.OrderBy = "ordnumb"
.OrderByOn = True
End With
End Sub
Private Sub Кнопка136_Click()
On Error GoTo Err_Кнопка136_Click


    Screen.PreviousControl.SetFocus
    DoCmd.FindNext

Exit_Кнопка136_Click:
    Exit Sub

Err_Кнопка136_Click:
    MsgBox Err.Description
    Resume Exit_Кнопка136_Click
    
End Sub