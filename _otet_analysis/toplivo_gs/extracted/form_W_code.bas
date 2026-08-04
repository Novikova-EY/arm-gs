Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Public msgstanu, msgstant

Private Sub Form_AfterUpdate()
For i = 0 To Forms.Count - 1
If Forms(i).Name = "Итог" Then Forms("Итог").Requery
Next i
End Sub

Private Sub Form_BeforeUpdate(Cancel As Integer)
Dim uf As Form, toplf As Form, dopform As Form, mf As Form
Dim db As Database, w As Form, U As DAO.Recordset, topl As DAO.Recordset, marks As DAO.Recordset
Dim dop As DAO.Recordset
Dim bm As String, bm1 As String
Dim j As Integer, j1 As Integer, j2 As Integer, j3 As Integer, j4 As Integer, j5 As Integer
Dim ekotp As Double, etpotp As Double, sumtopl As Double, sumug As Double, pt As Double
Dim namet As String, nameb As String, ugli As String, ugli1 As String
If Form_Редактирование.byear = 0 Then Form_Редактирование.byear = Form_Редактирование.byearf
Debug.Print "byear="; Form_Редактирование.byear
Parent!fchange = 1
Set db = DBEngine.Workspaces(0).Databases(0)
Set w = Parent![wform].Form
Set uf = Parent![uform].Form
Set toplf = Parent![toplform].Form
Set dopform = Parent![dopform].Form
Set U = uf.RecordsetClone
Set topl = toplf.RecordsetClone
Set dop = db.OpenRecordset(dopform.RecordSource, DB_OPEN_TABLE)
If (w.year = Form_Редактирование.byear) Or (z(w.VED) = 0) Then GoTo endcalc
If w.QOTR > 0 Then
If w.NT > 0 Then
If w.QOTR / w.NT * 1000 > 8760 Then bmsg = MsgBox("Число часов превышает 8760", vbOKOnly)
Else
bmsg = MsgBox("Нет тепловой мощности", vbOKOnly)
End If
End If
dop.Index = "numb1"
If U.RecordCount = 0 Then
If msgstanu <> w!numb1120 Then
bmsg = MsgBox("Отсутствуют удельные", vbOKOnly)
msgstanu = w!numb1120
End If
GoTo skipu
End If
U.MoveFirst
Do Until (U.EOF)
If U!year > w.year Then GoTo endu
If U!year <= w.year Then bm = U.Bookmark
U.MoveNext
Loop
endu: U.Bookmark = bm
w.EWTP = z(w.QOTR) * z(U!y) / 1000
If (w.VED = 1 Or w.VED = 4) And U!Ksn > 0 And w.NUST > 0 Then
ekotp = (z(w.E) - z(w.EWTP)) * (1 - (U!snbas - ((w.E / w.NUST) / 8.76) * U!Ksn) / 100)
Else
ekotp = (z(w.E) - z(w.EWTP)) * (1 - z(U("snk")) / 100)
End If
etpotp = z(w.EWTP) * z(U("sntp"))
w.EOTP = ekotp + etpotp
If (w.VED = 1 Or w.VED = 4) And U!Kh > 0 And w.NUST > 0 Then
w.EUST = w.EOTP * (U!bbas - ((w.E / w.NUST) / 8.76) * U!Kh) / 1000
Else
w.EUST = (ekotp * z(U("bk")) + etpotp * z(U("btp"))) / 1000
End If
If w.EOTP > 0 Then w.EURT = w.EUST / w.EOTP * 1000 Else w.EURT = 0
skipu:
'If z(U!fbt) = 0 And (w.OBOR = 90 Or w.OBOR = 91) And z(w.Q) > 0 Then w.TURT = (130 * z(w.QOTR) + 160 * (z(w.Q) - z(w.QOTR))) / z(w.Q)
If z(w.Q) > 0 And z(w.TURT) = 0 And z(w.OBOR) <> 23 Then bmsg = MsgBox("Отсутствует bt", vbOKOnly)
w.TUST = z(w.Q) * z(w.TURT) / 1000
w.B = w.EUST + w.TUST
If topl.RecordCount = 0 Then
If msgstant <> w!numb1120 Then
bmsg = MsgBox("Отсутствуют формулы топлива", vbOKOnly)
msgstant = w!numb1120
End If
GoTo endcalc
End If
topl.MoveFirst
Do Until (topl.EOF)
If topl!year > w.year Then GoTo endtop
If topl!year <= w.year Then bm1 = topl.Bookmark
topl.MoveNext
Loop
endtop: topl.Bookmark = bm1
'новые формулы
topls = ",gaz,mazut,torf,slan,gtt,proch,"
ugli = ",ugol,kuzn,kan,hak,tung,tuv,irkut,kazah,bur,chit,don,podm,pech,alt,ural,bashk,karag,amur,urg,prim,luch,yakut,chukot,sah,mag,kamch,ushum,tal,"
ugli1 = ",nazar,ibor,berez,per,irbei,kansk,gusin,tugn,okino,azey,cher,jer,karab,mug,har,urt,tataur,tarbag,zab_kam,vork,intin,sver,chel,kizel,sosv,neru,zyryan,pyak,rai,erk,svo,bikin,razdol,hankai,bering,anad,ekib,maikub,kuznt,kuzngd,kuznss,kuznun,gazpp,koksdom,prochgaz,tvproch,"
bdop = False
If Not (IsNull(topl("formtxt"))) Then
ost = w!B
at = split(topl!formtxt & ";", ";")
sumugol1 = 0
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
If namet = "azey" Or namet = "cher" Or namet = "mug" Then birkut = True
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
dopform(namet).ColumnHidden = False
If Not bdop Then
dop.Seek "=", w("numb1"), w!v, w!year
If dop.NoMatch Then
dop.AddNew
dop!numb1 = w.numb1
dop!numb1120 = w.numb1120
dop!year = w.year
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
w("irkut") = dop("azey") + dop("cher") + dop("mug")
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
For i = 0 To w.Controls.Count - 1
fname = w.Controls(i).Name
fname1 = fname
If fname = "yakut" Then fname1 = "yakut"
If InStr(1, topls & ugli, "," & fname & ",", vbTextCompare) > 0 And InStr(1, usedt, "," & fname & ",", vbTextCompare) = 0 Then w(fname) = 0
If InStr(1, ugli, "," & fname & ",", vbTextCompare) > 0 And fname <> "ugol" Then sumugol1 = sumugol1 + w(fname)
Next i
w("ugol") = sumugol1
GoTo endcalc
End If
'  новые формулы конец
endcalc:
End Sub

Private Sub Form_Current()
Dim dop As Form, U As Form, R As DAO.Recordset, db As Database, rnconf As DAO.Recordset, stan As Double
If NT > 0 Then Forms("Редактирование").Form!Ht = QOTR / NT * 1000
If z(Parent!link) & z(Parent!v) <> Me!numb1120 & Me!v Then
Parent!link = Me!numb1120
Parent!v = Me!v
If InStr(Me.RecordSource, "Станции(макет)") = 0 Then
Set dop = Parent!dopform.Form
Set U = Parent!uform.Form
If VED = 1 Or VED = 4 Then
U.Controls("sntp").ColumnHidden = True
U.Controls("btp").ColumnHidden = True
U.Controls("Kh").ColumnHidden = False
U.Controls("bbas").ColumnHidden = False
U.Controls("Ksn").ColumnHidden = False
U.Controls("snbas").ColumnHidden = False
Else
U.Controls("sntp").ColumnHidden = False
U.Controls("btp").ColumnHidden = False
U.Controls("Kh").ColumnHidden = True
U.Controls("bbas").ColumnHidden = True
U.Controls("Ksn").ColumnHidden = True
U.Controls("snbas").ColumnHidden = True
End If
sumtxt = "select "
ugli1 = "nazar,ibor,berez,per,irbei,kansk,gusin,tugn,okino,azey,cher,mug,karab,vork,intin,sver,chel,kizel,kuznt,kuzngd,kuznss,kuznun,jer,har,urt,tataur,tarbag,zab_kam,bikin,razdol,hankai,neru,zyryan,pyak,rai,erk,svo,bering,anad,ekib,maikub,koksdom,prochgaz,tvproch"
augli1 = split(ugli1, ",")
For i = 0 To UBound(augli1)
sumtxt = sumtxt & "sum(d." & augli1(i) & ") as " & IIf(augli1(i) = "intin", "[" & augli1(i) & "]", augli1(i))
If i < UBound(augli1) Then sumtxt = sumtxt & ","
Next i
sumtxt = sumtxt & ",sum(d.gazpp) as gazpp"
Debug.Print sumtxt
sumtxt = sumtxt & " from [" & dop.RecordSource & "] as d where numb1120=" & Me!numb1120 & ";"
Set db = DBEngine.Workspaces(0).Databases(0)
Set R = db.OpenRecordset(sumtxt)
R.MoveFirst
For j = 0 To R.Fields.Count - 1
fname = R.Fields(j).Name
'If fname = "[intin]" Then fname = "intin"
fh = IIf(z(R.Fields(j).Value) > 0, False, True)
dop.Controls(fname).ColumnHidden = fh
Next j
End If
For i = 0 To Forms.Count - 1
If Forms(i).Name = "Диаграмма" Then
DoCmd.OpenForm "Диаграмма", , , "numb=" & Me!numb1120
End If
If Forms(i).Name = "Турбины" Then
If InStr(Forms(i).filter, "ur=") > 0 Then agrur = True Else agrur = False
If z(VED) > 0 Then sf = "grcode=" Else sf = "stcode="
Forms(i).filter = sf & numb1120 & IIf(agrur, " and ur=1 ", "")
Forms(i).FilterOn = True
End If
If Forms(i).Name = "Справка_для_редактирования" Then
Forms(i).filter = "numb1120=" & numb1120
Forms(i).FilterOn = True
End If
If Forms(i).Name = "Конфигурация(справка)" Then
stan = IIf(z(MAIN) = 0, numb1120, MAIN)
If z(MAIN) > 0 Then
sqlnconf = "SELECT Count([станция-конфигурация].conf) AS nconf FROM [станция-конфигурация] INNER JOIN Имена_станций ON [станция-конфигурация].stan = Имена_станций.NUMB GROUP BY main HAVING main=" & stan & ";"
Set rnconf = CurrentDb.OpenRecordset(sqlnconf)
If rnconf.RecordCount > 0 Then
If rnconf!nconf > 1 Then stan = numb1120
End If
End If
Forms(i).filter = "stan=" & stan
Forms(i).FilterOn = True
End If
If Forms(i).Name = "Пром_потребители" Then
Forms(i).filter = "codest=" & IIf(z(MAIN) = 0, numb1120, MAIN)
Forms(i).FilterOn = True
End If
Next i
End If
End Sub

Private Sub Form_Open(Cancel As Integer)
For i = 0 To Section(0).Controls.Count - 1
'Section(0).Controls(i).ColumnHidden = False
Next i
End Sub