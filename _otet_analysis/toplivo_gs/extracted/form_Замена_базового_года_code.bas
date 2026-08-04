Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Option Compare Database
Dim dname As String, dopname As String, nfrsql As String
Dim db As Database

Private Sub Замена2_Click()
Dim rvar As DAO.Recordset
Set db = DBEngine.Workspaces(0).Databases(0)
dname = listvar.Column(1, i)
btrsql = "select numb1120,turt from [" & dname & "] where q>0 and year=" & newby & " and ved>0;"
Debug.Print btrsql
Set btr = db.CreateQueryDef("Отчетный_bt", btrsql)
btpsql = "update [" & dname & "] as d inner join Отчетный_bt as s on d.numb1120=s.numb1120 set d.turt=s.turt where d.year>" & newby & ";"
Debug.Print btpsql
DoCmd.RunSQL (btpsql)
db.QueryDefs.Delete ("Отчетный_bt")
i = listvar.ListIndex
uname = listvar.Column(2, i)
toplname = listvar.Column(4, i)
If oldby <> newby Then
udelsql = "delete [#].* from [#] where year<" & newby + 1 & " and numb1120=any(select numb1120 from [#] where year=" & newby + 1 & ");"
udelsql = Replace(udelsql, "#", uname)
Debug.Print udelsql
DoCmd.RunSQL udelsql
topldelsql = Replace(udelsql, uname, toplname)
DoCmd.RunSQL topldelsql
usql = "update [" & uname & "] set year=" & newby + 1 & " where year=" & newby & ";"
toplsql = Replace(usql, uname, toplname)
Debug.Print usql
Debug.Print toplsql
DoCmd.RunSQL (usql)
DoCmd.RunSQL (toplsql)
End If
usql = "Update ([" & uname & "] as d inner join vartobase on d.numb1120=vartobase.numb1120) inner join Удельные" & newby & " as s on vartobase.link=s.numb1120 "
usql = usql & "set d.year=s.year,d.btp=s.btp,d.bk=s.bk,d.snk=s.snk,d.sntp=s.sntp,d.y=s.y where d.year=" & oldby & ";"
Debug.Print oldby; usql
DoCmd.RunSQL (usql)
Set rvar = db.OpenRecordset("Список-вариантов", dbOpenDynaset)
rvar.FindFirst "name=""" & listvar.Column(0, i) & """"
rvar.Edit
rvar!byear = newby
rvar.Update
End Sub

Private Sub listvar_Click()
i = listvar.ListIndex
oldby = listvar.Column(5, i)
End Sub

Private Sub stanordop_AfterUpdate()
If stanordop = 1 Then
notfound.RowSource = nfrsql
notfound.Requery
End If
If stanordop = 2 Then
nfdopsql = "select name from [" & dopname & "] as d where d.year=" & oldby & " order by numb1;"
notfound.RowSource = nfdopsql
notfound.Requery
End If
If stanordop = 3 Then
nfdopmsql = "select s.name from [" & "Доп_угли" & newby & "] as s LEFT JOIN " & dopname & " as d ON s.numb1120=d.numb1120 where d.numb1120 is null;"
'Debug.Print nfdopmsql
notfound.RowSource = nfdopmsql
notfound.Requery
End If
End Sub

Private Sub Замена1_Click()
Dim upstan As QueryDef, vtb As QueryDef, updop As QueryDef
i = listvar.ListIndex
dname = listvar.Column(1, i)
dopname = listvar.Column(3, i)
upstancond = " (d.year=" & oldby & " or d.year=" & newby & ") AND s.year=" & newby & " "
vtbcond = " d.year<" & newby + 1 & " AND (s.year=" & newby & " or s.year is null) and (r=1 or z(s.q)>0)"
tonewsql = "UPDATE [" & dname & "] AS d INNER JOIN имена_станций ON d.numb1120=имена_станций.NUMB "
tonewsql = tonewsql & "SET d.year=" & newby & " WHERE (d.year=" & oldby & ") AND ((имена_станций.R<>1) OR (имена_станций.R IS NULL));"
Debug.Print "tonew="; tonewsql
DoCmd.RunSQL (tonewsql)
Set db = DBEngine.Workspaces(0).Databases(0)
Set upstan = db.QueryDefs("updatebase")
Set vtb = db.QueryDefs("vartobase")
Set updop = db.QueryDefs("updatebase(dop)")
vtbsqlsave = vtb.SQL
vtbsql = vtbsqlsave
vtbsql = Replace(vtbsql, "Станции(макет)", dname)
vtbsql = Replace(vtbsql, "Станции(архив)", "Станции" & newby)
vtbsql = repbetw(vtbsql, "WHERE", ";", vtbcond)
upstansql = upstan.SQL
upstansql = Replace(upstansql, "Станции(макет)", dname)
upstansql = Replace(upstansql, "Станции(архив)", "Станции" & newby)
upstansql = repbetw(upstansql, "WHERE", ";", upstancond)
insdopsql = "insert into [" & dopname & "] ([year],numb1120,numb1) select w.year,w.numb1120,w.numb1"
insdopsql = insdopsql & " from [" & dname & "] as w left join [" & dopname & "] as d "
insdopsql = insdopsql & " on w.year=d.year and w.numb1120=d.numb1120 and w.v=d.v"
insdopsql = insdopsql & " where w.year=" & newby & " and z(pech)+z(ural)+z(kan)+z(irkut)+z(bur)>0 and d.numb1120 is null;"
updopsql = updop.SQL
updopsql = Replace(updopsql, "Доп_угли(макет)", dopname)
updopsql = Replace(updopsql, "Доп_угли(архив)", "Доп_угли" & newby)
updopsql = repbetw(updopsql, "WHERE", ";", upstancond)
vtb.SQL = vtbsql
'Debug.Print vtbsql
Debug.Print upstansql
'Debug.Print updopsql
DoCmd.RunSQL (upstansql)
Debug.Print insdopsql
DoCmd.RunSQL insdopsql
DoCmd.RunSQL (updopsql)
vtb.SQL = vtbsqlsave
notfound.RowSourceType = "Table/Query"
rbysql = "UPDATE [" & dname & "] SET year=" & newby & " WHERE year=" & oldby & " and not(z(nust)>0 or z(e)>0 or z(q)>0);"
'Debug.Print rbysql
DoCmd.RunSQL (rbysql)
nfrsql = "select name from [" & dname & "] as d where d.year=" & oldby & " order by numb1;"
'Debug.Print nfrsql
notfound.RowSource = nfrsql
notfound.Requery
End Sub


Private Sub Обновить_Click()
notfound.Requery
End Sub