SELECT Станции2018.NAME, Станции2018.NUMB1120, Имена_станций.NIV, Имена_станций.COMP, Имена_станций.MAIN, Станции2018.OBOR, Станции2018.VED, IIf([ved]>0,0,1) AS sost, IIf([main]>0,1,0) AS [group]
FROM Имена_станций INNER JOIN Станции2018 ON Имена_станций.NUMB = Станции2018.NUMB1120
WHERE (((IIf([ved]>0,0,1))=1));
