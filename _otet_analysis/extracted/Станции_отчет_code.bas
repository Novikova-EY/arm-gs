Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Option Compare Text
Public Sub Form_AfterUpdate()
Dim df As Form, st As Form
Parent!fchange = 1
Set df = Forms("Доп_угли")
df.Requery
If YEAR = 1990 Or YEAR = 2014 Or YEAR >= 2018 Then 'добавила
    delta = z(B) - z(Вэ) - z(Вт)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс Bэ+Bт " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(B) - z(GAZ) - z(ISK_GAZ) - z(MAZUT) - z(torf) - z(SLAN) - z(PROCH) - z(UGOL)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс топлива " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(GAZ) - z(df!gaz_prir) - z(df!gazpp)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  газа " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(ISK_GAZ) - z(df!domen_g) - z(df!koks_g) - z(df!prochgaz)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  искусственного газа " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(MAZUT) - z(df!disel) - z(df!maztop) - z(df!nft_proch) - z(df!GTT)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  нефтетоплива " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(UGOL) - z(don) - z(podm) - z(pech) - z(ALT) - z(kuzn) - z(ural) - z(BASHK) - z(KAZAH) - z(KAN) - z(tung) - z(IRKUT) - z(HAK) - z(TUV) - z(BUR) - z(chit) - z(YAKUT) - z(AMUR) - z(prim) - z(urg) - z(mag) - z(sah) - z(KAMCH) - z(CHUKOT) - z(USHUM)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(pech) - z(df!vork) - z(df!intin)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  печорских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(ural) - z(df!sver) - z(df!chel) - z(df!kizel)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  уральских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(kuzn) - z(df!kuzngd) - z(df!kuznt) - z(df!kuznss) - z(df!kuznun)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс кузнецких углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(KAZAH) - z(df!ekib) - z(df!maikub) - z(df!karag) - z(df!karajyra) - z(df!teniz)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  казахстанских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(KAN) - z(df!nazar) - z(df!ibor) - z(df!berez) - z(df!per) - z(df!irbei) - z(df!kansk)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс КАУ " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(tung) - z(df!jer) - z(df!karab)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  тунгусских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(IRKUT) - z(df!azey) - z(df!cher) - z(df!mug)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  иркутских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(BUR) - z(df!gusin) - z(df!tugn) - z(df!okino)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  бурятских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(chit) - z(df!har) - z(df!urt) - z(df!tataur) - z(df!tarbag) - z(df!zab_kam)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  читинских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(AMUR) - z(df!rai) - z(df!erk) - z(df!ogodj) - z(df!svo)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  амурских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(prim) - z(df!bikin) - z(df!razdol) - z(df!hankai)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  приморских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(CHUKOT) - z(df!bering) - z(df!anad)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  чукотских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(YAKUT) - z(df!neru) - z(df!pyak) - z(df!zyryan)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  якутских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(PROCH) - z(df!tvproch) - z(df!szh_gaz) - z(df!inoe)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс прочего топлива " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
ElseIf YEAR >= 2010 And YEAR < 2018 Then
    delta = z(B) - z(Вэ) - z(Вт)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс Bэ+Bт " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(B) - z(GAZ) - z(MAZUT) - z(torf) - z(SLAN) - z(PROCH) - z(UGOL)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс топлива " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(GAZ) - z(df!gaz_prir) - z(df!gazpp)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  газа " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(MAZUT) - z(df!disel) - z(df!maztop) - z(df!nft_proch) - z(df!GTT)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  нефтетоплива " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(UGOL) - z(don) - z(podm) - z(pech) - z(ALT) - z(kuzn) - z(ural) - z(BASHK) - z(KAZAH) - z(KAN) - z(tung) - z(IRKUT) - z(HAK) - z(TUV) - z(BUR) - z(chit) - z(YAKUT) - z(AMUR) - z(prim) - z(urg) - z(mag) - z(sah) - z(KAMCH) - z(CHUKOT) - z(USHUM)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(pech) - z(df!vork) - z(df!intin)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  печорских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(ural) - z(df!sver) - z(df!chel) - z(df!kizel)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  уральских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(kuzn) - z(df!kuzngd) - z(df!kuznt) - z(df!kuznss) - z(df!kuznun)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс кузнецких углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(KAZAH) - z(df!ekib) - z(df!maikub) - z(df!karag) - z(df!karajyra) - z(df!teniz)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  казахстанских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(KAN) - z(df!nazar) - z(df!ibor) - z(df!berez) - z(df!per) - z(df!irbei) - z(df!kansk)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс КАУ " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(tung) - z(df!jer) - z(df!karab)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  тунгусских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(IRKUT) - z(df!azey) - z(df!cher) - z(df!mug)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  иркутских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(BUR) - z(df!gusin) - z(df!tugn) - z(df!okino)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  бурятских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(chit) - z(df!har) - z(df!urt) - z(df!tataur) - z(df!tarbag) - z(df!zab_kam)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  читинских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(AMUR) - z(df!rai) - z(df!erk) - z(df!ogodj) - z(df!svo)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  амурских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(prim) - z(df!bikin) - z(df!razdol) - z(df!hankai)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  приморских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(CHUKOT) - z(df!bering) - z(df!anad)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  чукотских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(YAKUT) - z(df!neru) - z(df!pyak) - z(df!zyryan)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  якутских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(PROCH) - z(df!koksdom) - z(df!prochgaz) - z(df!tvproch)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс прочего топлива " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
Else
    delta = z(B) - z(Вэ) - z(Вт)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс Bэ+Bт " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(B) - z(GAZ) - z(MAZUT) - z(torf) - z(SLAN) - z(GTT) - z(PROCH) - z(UGOL)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс топлива " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(UGOL) - z(don) - z(podm) - z(pech) - z(ARKT) - z(kuzn) - z(ural) - z(BASHK) - z(ekib) - z(karag) - z(KAN) - z(IRKUT) - z(HAK) - z(TUV) - z(BUR) - z(chit) - z(YAKUT) - z(AMUR) - z(prim) - z(urg) - z(luch) - z(mag) - z(sah) - z(KAMCH) - z(USHUM)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(pech) - z(df!vork) - z(df!intin)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  печорских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(ural) - z(df!sver) - z(df!chel) - z(df!kizel)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  уральских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(KAN) - z(df!nazar) - z(df!ibor) - z(df!berez) - z(df!per)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс КАУ " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(tung) - z(df!jer) - z(df!karab)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  тунгусских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(IRKUT) - z(df!azey) - z(df!cher) - z(df!mug)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  иркутских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(BUR) - z(df!gusin) - z(df!tugn)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  бурятских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(chit) - z(df!har) - z(df!urt)
    If Abs(delta) >= 0.01 Then msg = MsgBox("Небаланс  читинских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(AMUR) - z(df!rai) - z(df!erk)
    If Abs(delta) >= 0.01 And YEAR > 2001 Then msg = MsgBox("Небаланс  амурских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(YAKUT) - z(df!neru) - z(df!pyak)
    If Abs(delta) >= 0.01 And YEAR > 2001 Then msg = MsgBox("Небаланс  якутских углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
    delta = z(kuzn) - z(df!kuzngd) - z(df!kuznt) - z(df!kuznss) - z(df!kuznun)
    If Abs(delta) >= 0.01 And YEAR > 2001 Then msg = MsgBox("Небаланс кузнецких углей " & " Дельта=" & Format(delta, "#.##"), vbOKOnly)
End If
'добавила
Set st = Forms("Стоимость")
st.Requery
End Sub





Private Sub Form_Current()
dopopen = 0
For i = 0 To Forms.Count - 1
If Forms(i).Name = "Доп_угли" Then
dopopen = 1
Forms(i).Filter = "numb1120=" & NUMB1120 & " and year=" & YEAR
Forms(i).FilterOn = True
End If
'добавила
If Forms(i).Name = "Стоимость" Then
Forms(i).Filter = "numb1120=" & NUMB1120 & " and year=" & YEAR
Forms(i).FilterOn = True
End If
'конец
If Forms(i).Name = "Турбины" Then
If z(MAIN) > 0 Then sf = "grcode=" Else sf = "numb1120="
Forms(i).Filter = sf & NUMB1120
Forms(i).FilterOn = True
Forms(i).OrderByOn = True
End If
If Forms(i).Name = "Конфигурация(справка)" Then
Forms(i).Filter = "stan=" & NUMB1120
Forms(i).FilterOn = True
End If
If Forms(i).Name = "Пром_потребители" Then
Forms(i).Filter = "codest=" & NUMB1120
Forms(i).FilterOn = True
End If
If Forms(i).Name = "Диалог_для_справки" Then
DoCmd.Close acForm, "Диалог_для_справки"
DoCmd.OpenForm ("Диалог_для_справки"), , , , , , NUMB1120
End If
Next i
For i = 0 To Forms.Count - 1
If Forms(i).Name = "Диаграмма" Then
DoCmd.OpenForm "Диаграмма", , , "numb=" & NUMB1120
End If
Next i
Parent!linkcode = NUMB1120
Parent!linkyear = YEAR
If dopopen = 1 Then
    With Forms("Редактирование_отчетных_данных")!nat.Form
        For i = 0 To .Controls.Count - 1
        fname = .Controls(i).Name
        If .Controls(i).Tag = "w" Then
            If Me(fname) > 0 Then .Controls(i).ColumnHidden = False Else .Controls(i).ColumnHidden = True
        Else
        If Forms("Доп_угли")(fname) > 0 Then .Controls(i).ColumnHidden = False Else .Controls(i).ColumnHidden = True
        End If
        Next i
    End With
End If
End Sub

Private Sub Form_KeyDown(KeyCode As Integer, Shift As Integer)
If KeyCode = 114 Then
Form_Редактирование_отчетных_данных.ac = Screen.ActiveControl.Name
Parent!nat1.SetFocus
End If
End Sub

Private Sub Form_Open(Cancel As Integer)
For i = 0 To Section(0).Controls.Count - 1
Section(0).Controls(i).ColumnHidden = False
Next i
End Sub

Public Sub nt_AfterUpdate()
Call verifynt(NT, NUMB1120)
End Sub

Public Sub verifynt(NT As Double, NUMB1120 As Double)
If YEAR >= 2000 Then
sqlnt = "select sum(турбины.nt) as nt from турбины where " & IIf(z(MAIN) > 0, "grcode=", "numb1120=") & NUMB1120 & " and (dem is null or dem>" & YEAR & ") and yearin<=" & YEAR & " group by numb1120;"
Set db = Workspaces(0).Databases(0)
Set sumnt1 = db.OpenRecordset(sqlnt)
Debug.Print sqlnt
If sumnt1.RecordCount > 0 Then
sumnt1.MoveFirst
delta = NT - sumnt1!NT
If Abs(delta) >= 1 Then
For i = 0 To Forms.Count - 1
If Forms(i).Name = "Турбины" Then GoTo lmsg
Next i
Application.DoCmd.OpenForm "Турбины", acFormDS, , "numb1120=" & NUMB1120
lmsg:
msg = MsgBox("Небаланс тепловой мощности  " & " Дельта=" & Format(delta, "#"), vbOKOnly)
End If
End If
End If
End Sub

Private Sub PROCH_BeforeUpdate(Cancel As Integer)

End Sub