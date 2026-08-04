Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Dim Est As Double, Qst As Double, qotrst As Double, Btst As Double
Dim eotpst As Double, best As Double, snkst As Double, sntst As Double
Dim turtst As Double, eurtst As Double
Option Compare Database
Option Explicit


Private Sub Form_Current()
Dim n As Integer
If (OES = 1 Or OES = 8) And Not (data.SourceObject = "Северо-Запад") Then setform ("Северо-Запад")
If OES = 2 And Not (data.SourceObject = "Центр") Then setform ("Центр")
If OES = 3 And Not (data.SourceObject = "Волга") Then setform ("Волга")
If OES = 4 And Not (data.SourceObject = "Юг") Then setform ("Юг")
If (OES = 5 Or OES = 11) And Not (data.SourceObject = "Урал") Then setform ("Урал")
If (OES = 6 Or OES = 10) And Not (data.SourceObject = "Сибирь") Then setform ("Сибирь")
If (OES = 7 Or OES = 9) And Not (data.SourceObject = "Восток") Then setform ("Восток")
dmax1 = 0
dmax2 = 0
dmax3 = 0
dis = True
n = data.Form.RecordsetClone.RecordCount
If n = 3 Then switch = 1 Else switch = 3
End Sub


Private Sub Form_KeyDown(KeyCode As Integer, Shift As Integer)
If KeyCode = 114 Then data.SetFocus
End Sub

Private Sub Form_Open(Cancel As Integer)
setform ("Северо-Запад")
End Sub


Public Sub setform(fname As String)
Dim i As Long
data.SourceObject = fname
data.Form.KeyPreview = True
data.LinkChildFields = "numbm"
data.LinkMasterFields = "numb"
data.Form.OrderBy = "ordnumb"
End Sub


Private Sub Кнопка11_Click()
Dim df As Form, q1 As Double, q2 As Double, bt1 As Double, bt2 As Double
Dim be1 As Double, be2 As Double, eotp1 As Double
data.SetFocus
Set df = data.Form
DoCmd.GoToRecord , , acGoTo, 2
bt1 = df!TURT
be1 = df!EURT
If bt1 = 0 Then df!Q = 0
DoCmd.GoToRecord , , acGoTo, 3
bt2 = df!TURT
be2 = df!EURT
If bt2 = 0 Then
df!Q = 0
q1 = Qst
Else
If bt1 = 0 Then
df!Q = Qst
Else
q1 = (Btst * 1000 - Qst * bt2) / (bt1 - bt2)
df!Q = Qst - q1
End If
End If
eotp1 = (best * 1000 - eotpst * be2) / (be1 - be2)
df!EOTP = eotpst - eotp1
DoCmd.GoToRecord , , acGoTo, 2
df!Q = q1
df!EOTP = eotp1
End Sub

Private Sub Кнопка12_Click()
Dim df As Form, q1 As Double, q2 As Double, bt1 As Double, bt2 As Double
Dim rf As Form, n As Integer, sumqotr As Double, i As Integer, k1 As Double
Dim sume As Double, k2 As Double
data.SetFocus
Set df = data.Form
Set rf = Разбивка.Form
n = df.RecordsetClone.RecordCount
sumqotr = 0
sume = 0
For i = 2 To n
DoCmd.GoToRecord , , acGoTo, i
df!QOTR = df!NT * z(rf!kNт / 100) * 8.76
sumqotr = sumqotr + df!QOTR
df!E = (df!EOTP + z(df!Q) * z(df!SNt) / 1000) / (1 - z(df!SNK) / 100)
sume = sume + df!E
df!EUST = df!EOTP * df!EURT / 1000
df!TUST = df!Q * df!TURT / 1000
df!B = df!EUST + df!TUST
df!GAZ = df!B * z(rf!газ) / 100
df!MAZUT = df!B * z(rf!мазут) / 100
df!UGOL = df!B * z(rf!уголь) / 100
Next
k1 = qotrst / sumqotr
k2 = Est / sume
For i = 2 To n
DoCmd.GoToRecord , , acGoTo, i
df!QOTR = df!QOTR * k1
df!E = df!E * k2
Next
End Sub

Private Sub Кнопка16_Click()
Dim a() As Double, a1() As Double, B() As Double, Q() As Double
Dim df As Form, rf As Form, n, i As Integer, j As Integer, d0 As Double, sumq As Double, k As Double
Dim sume As Double, E() As Double, delta As Double, sumeurt As Double, sumsnt As Double, sumbt As Double
Dim k1 As Double, sumqotr As Double, sum1 As Double, delta1 As Double
data.SetFocus
Set df = data.Form
Set rf = Разбивка.Form
n = df.RecordsetClone.RecordCount
DoCmd.GoToRecord , , acGoTo, 1
Est = z(data.Form!E)
Qst = z(data.Form!Q)
qotrst = z(data.Form!QOTR)
Btst = z(data.Form!TUST)
eotpst = z(data.Form!EOTP)
best = z(data.Form!EUST)
snkst = z(data.Form!SNK)
sntst = z(data.Form!SNt)
eurtst = z(data.Form!EURT)
turtst = z(data.Form!TURT)
ReDim a(n - 1, n - 1)
ReDim a1(n - 1)
ReDim B(n - 1)
ReDim Q(n - 1)
sume = 0
sumqotr = 0
For i = 2 To n
DoCmd.GoToRecord , , acGoTo, i
df!E = z(df!NUST) * z(rf!kne) / 100 * 8.76
df!QOTR = z(df!NT) * z(rf!kNт) / 100 * 8.76
sume = sume + df!E
sumqotr = sumqotr + df!QOTR
Next
If sume <> Est Then k = Est / sume
If sumqotr <> qotrst And sumqotr > 0 Then k1 = qotrst / sumqotr
sum1 = 0
For i = 2 To n
DoCmd.GoToRecord , , acGoTo, i
df!E = df!E * k
df!EWTP = df!E * z(rf!ptp) / 100
df!QOTR = df!QOTR * k1
If switch = 1 Then
'sum1 = sum1 + df!E * (1 - z(df!SNK) / 100)
sum1 = sum1 + df!E * (1 - z(df!SNK) / 100) * df!EURT / 1000
End If
Next
'РАСПРЕДЕЛЕНИЕ ТЕПЛА
If dis = False Then GoTo skipq
sumq = 0
sumsnt = 0
sumeurt = 0
sumbt = 0
For i = 2 To n
DoCmd.GoToRecord , , acGoTo, i
a(1, i - 1) = 1
If n = 3 Then
If switch = 1 Then
a(2, i - 1) = z(df!SNt)
ElseIf switch = 2 Then
a(2, i - 1) = z(df!TURT)
End If
ElseIf n = 4 Then
If switch = 3 Then
a(2, i - 1) = z(df!SNt)
a(3, i - 1) = z(df!TURT)
End If
End If
sumeurt = sumeurt + z(df!EURT)
sumsnt = sumsnt + z(df!SNt)
sumbt = sumbt + z(df!TURT)
Next
B(1) = 1
If n = 3 Then
If switch = 1 Then
B(2) = sntst
ElseIf switch = 2 Then
B(2) = turtst
End If
ElseIf n = 4 Then
If switch = 3 Then
B(2) = sntst
B(3) = turtst
End If
End If
d0 = det3(a)
Debug.Print "d0="; d0;
For j = 1 To n - 1
For i = 2 To n
a1(i - 1) = a(i - 1, j)
a(i - 1, j) = B(i - 1)
Next
Q(j) = Qst * det3(a) / d0
If n = 3 And switch < 3 Then
If switch = 1 Then delta = 0.01 Else delta = 0.1
If switch = 1 Then delta1 = 0.055 Else delta1 = 0.1
ElseIf n = 4 And switch = 3 Then
delta = 0.01 * sumbt + 0.1 * sumsnt
delta1 = 0.01 * (sumbt - z(df!TURT) + turtst) + 0.1 * (sumsnt - z(df!SNt) + sntst)
End If
Debug.Print "delta="; delta; "delta1="; delta1
If j = 1 Then
If Q(j) > 0 Then dmax1 = Abs((Abs(det3(a)) + delta1) / (Abs(d0) - delta) - det3(a) / d0) / (det3(a) / d0) * 100
ElseIf j = 2 Then
If Q(j) > 0 Then dmax2 = Abs((Abs(det3(a)) + delta1) / (Abs(d0) - delta) - det3(a) / d0) / (det3(a) / d0) * 100
ElseIf j = 3 Then
If Q(j) > 0 Then dmax3 = Abs((Abs(det3(a)) + delta1) / (Abs(d0) - delta) - det3(a) / d0) / (det3(a) / d0) * 100
End If
Debug.Print det3(a); "q="; Q(j)
For i = 2 To n
a(i - 1, j) = a1(i - 1)
Next
If a(2, j) = 0 Then Q(j) = 0
sumq = sumq + Q(j)
Next
k = Qst / sumq
skipq: For i = 2 To n
DoCmd.GoToRecord , , acGoTo, i
If dis Then df!Q = Q(i - 1) * k
df!EOTP = df!E * (1 - z(df!SNK) / 100) - z(df!Q) * z(df!SNt) / 1000
df!EUST = df!EOTP * df!EURT / 1000
df!TUST = df!Q * z(df!TURT) / 1000
df!B = z(df!EUST) + z(df!TUST)
df!GAZ = df!B * rf!газ / 100
df!MAZUT = df!B * rf!мазут / 100
df!UGOL = df!B * rf!уголь / 100
If Est > 0 Then rf!pe = df!E / Est * 100
Next
End Sub