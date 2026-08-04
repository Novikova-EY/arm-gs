Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Option Compare Database

Private Sub Кнопка0_Click()
Dim db As Database, trans As DAO.Recordset, def As DAO.Recordset, isb As DAO.Recordset, links As DAO.Recordset
Dim p(50) As Double, t(50) As Double, isbs(50) As Double, s(50) As Double, oblk(50) As Double
Dim id(4, 50) As Double, prot As DAO.Recordset
Dim Qlinks As QueryDef, Qdef As QueryDef, Qisb As QueryDef
Set db = CurrentDb
Set Qdef = db.QueryDefs("дефициты_год")
Qdef![год] = year
Qdef![ОЭС] = oes
Set Qisb = db.QueryDefs("дефициты_год")
Qisb![год] = year
Qisb![ОЭС] = oes
Set trans = db.OpenRecordset("перетоки_табл")
Set prot = db.OpenRecordset("протокол")
trans.Index = "ndx1"
prot.Index = "ndx1"
sqlinitD = "UPDATE Дефициты SET Дефициты.Dwork = [D] where year=" & year & "and oes=" & oes & ";"
sqlinitT = "UPDATE Перетоки_табл SET Pwork = null,t=0 where year=" & year & "and oes=" & oes & ";"
sqldelp = "Delete Протокол.* from Протокол where year=" & year & " and oes=" & oes & ";"
db.Execute (sqldelp) 'очистка prot
qh = 1
If Queu Then ql = 1 Else ql = 0
db.Execute (sqlinitD) 'инициациализация Dwork
db.Execute (sqlinitT) 'инициациализация Pwork,T
nxtq:
l = 1
pb.Max = 4
pb.Min = 0
pb.Value = 0
pb1.Min = 0
nxtstep:
pb.Value = l
Set def = Qdef.OpenRecordset
Set isb = Qisb.OpenRecordset
Set Qlinks = db.QueryDefs("L" & l & "_РЭУ")
Qlinks![год] = year
Qlinks![ОЭС] = oes
def.MoveFirst
Do While Not (def.EOF)
breu:
bdu = False
If def!dwork < 0 Then 'дефицитная область
If def!Q >= ql And def!Q <= qh Then 'очередь
Qlinks![введите РЭУ] = def!OBL
Debug.Print def!РЭУ; def!dwork; def!dn; l; Time
Set links = Qlinks.OpenRecordset(DB_OPEN_DYNASET)
defwork = def!dwork
' форимирование массива связей с избыточными РЭУ
i = 0
If links.RecordCount = 0 Then GoTo nxtreu
pb1.Max = links.RecordCount
pb1.Value = 0
links.MoveFirst
nxtlink:
trans.Seek "=", year, links("id" & l)
isb.FindFirst "obl=" & links!oblk
For j = 0 To l - 1 ' по количеству звеньев
id(j, i) = links("id" & j + 1)
Next j
isbs(i) = isb!D
p(i) = links!pwork
s(i) = links!s
t(i) = 0
oblk(i) = links!oblk
i = i + 1
links.MoveNext
If Not (links.EOF) Then GoTo nxtlink
nlink = i - 1
sumt = 0
For i = 0 To nlink
pb1.Value = i
If s(i) >= Abs(defwork) Then
t(i) = defwork
defwork = 0
Debug.Print id(0, i); id(1, i); id(2, i); id(3, i); "p="; p(i); defwork; isbs(i); t(i); s(i); def!dn; def!D
GoTo wres
Else
t(i) = -s(i)
defwork = defwork - t(i)
End If
Debug.Print id(0, i); id(1, i); id(2, i); id(3, i); "p="; p(i); defwork; isbs(i); t(i); s(i); def!dn; def!D
bdu = DblUse(i, id, nlink, l, oblk)
If bdu Then GoTo wres
Next i
wres: 'вывод результатов расчета
'Debug.Print "вывод результатов "; def!РЭУ
For i = 0 To nlink
prot.AddNew
prot!year = year
prot!oes = oes
prot!OBL = def!OBL
prot!step = l
prot!nlink = i
For j = 0 To l - 1
trans.Seek "=", year, id(j, i)
oblb = IIf(j = 0, def!OBL, oble)
trans.Edit
If trans!obl1 = oblb Then
trans!t = trans!t + t(i)
oble = trans!obl2
Else:
trans!t = trans!t - t(i)
oble = trans!obl1
End If
If t(i) <> 0 Then trans!pwork = IIf(IsNull(trans!pwork), IIf(trans!obl1 = oblb, trans!pinv, trans!p) - Abs(t(i) * def!dn / def!D), trans!pwork - Abs(t(i) * def!dn / def!D))
trans.Update
prot("id" & j + 1) = id(j, i)
Next j
prot!t = t(i)
'Debug.Print "протокол "; prot!nlink; prot!id1; prot!id2; prot!id3; prot!id4; prot!t
prot.Update
isb.FindFirst "obl=" & oble
isb.Edit
isb!dwork = isb!dwork + t(i)
isb.Update
Next i
def.Edit
If def!dwork < 0 Then def!dwork = defwork
def.Update
Debug.Print "def="; def!OBL; def!dwork; defwork
End If 'очередь
End If 'дефицитная область
If bdu Then GoTo breu
nxtreu:
def.MoveNext
Loop
Debug.Print "шаг "; l
If l < 4 Then
l = l + 1
GoTo nxtstep
End If
endq:
pb.Value = 0
If Queu Then
If ql > 0 Then
ql = 0
qh = ql
GoTo nxtq
End If
End If
End Sub
Public Function DblUse(i, id, nlink, l, oblk) As Boolean
DblUse = False
If i = nlink Then GoTo endf
For i1 = i + 1 To nlink
If oblk(i) = oblk(i1) Then
Debug.Print "повторное использование "; oblk(i)
DblUse = True
GoTo endf
End If
If l = 1 Then GoTo endf
For j1 = 0 To l - 1
For j2 = 0 To l - 1
If id(j1, i1) = id(j2, i) Then
Debug.Print "повторное использование "; id(j1, i1); id(j2, i)
DblUse = True
GoTo endf
End If
Next j2
Next j1
Next i1
endf:
End Function