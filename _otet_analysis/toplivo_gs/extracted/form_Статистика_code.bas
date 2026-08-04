Attribute VB_GlobalNameSpace = False
Attribute VB_Creatable = True
Attribute VB_PredeclaredId = True
Attribute VB_Exposed = False
Option Compare Database



Private Sub Диаграмма_Click()
DoCmd.OpenForm "Диаграмма_расчет"
rs = "select year,e from [" & Forms("Расчет").Form!wname & "] where (numb1120=" & Sres.Form!numb1120 & ")"
Debug.Print rs
Forms("Диаграмма_расчет").Form!diagr.RowSource = rs

End Sub