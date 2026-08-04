SELECT z.NUMB1120, z.Year, Sum(IIf(i.[post/per]='post',z.ZATRATY_SUM,0)) AS Post_Sum, Sum(IIf(i.[post/per]='per',z.ZATRATY_SUM,0)) AS Per_Sum, Sum(IIf(i.[post/per] Is Null,z.ZATRATY_SUM,0)) AS Sum_Zatr, Sum(IIf(i.[post/per]='post',z.Zatr_E,0)) AS Post_E, Sum(IIf(i.[post/per]='per',z.Zatr_E,0)) AS Per_E, Sum(IIf(i.[post/per]='post',z.Zatr_Q,0)) AS Post_Q, Sum(IIf(i.[post/per]='per',z.Zatr_Q,0)) AS Per_Q, Sum(IIf(i.[post/per]='post',z.Zatr_P,0)) AS Post_P, Sum(IIf(i.[post/per]='per',z.Zatr_P,0)) AS Per_P, IIf(Sum(IIf(i.[post/per]='per', z.ZATRATY_SUM, 0))=0,
        Null,
        Sum(IIf(z.code_zatr BETWEEN 110 AND 114, z.ZATRATY_SUM, 0)) / 
        Sum(IIf(i.[post/per]='per', z.ZATRATY_SUM, 0))
    ) AS Fuel_Share, IIf(Sum(IIf(i.[post/per]='post', z.ZATRATY_SUM, 0))=0,
        Null,
        Sum(IIf(z.code_zatr=170, z.ZATRATY_SUM, 0)) / 
        Sum(IIf(i.[post/per]='post', z.ZATRATY_SUM, 0))
    ) AS Amort_Share
FROM Все_Затраты AS z LEFT JOIN Имена_затраты AS i ON z.code_zatr = i.code_zatr
WHERE z.code_zatr NOT IN (11,10,111,112,113,114,201,202,203,204,205,311,312)
GROUP BY z.NUMB1120, z.Year;
