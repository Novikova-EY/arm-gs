SELECT Станции2023.NAME, Станции2023.NUST, Станции2023.E, Станции2023.Q, Станции2023.B, Станции2023.OBOR, IIf([ved]>0,0,1) AS sost, IIf([main]>0,1,0) AS [group], *
FROM Имена_станций INNER JOIN Станции2023 ON Имена_станций.NUMB = Станции2023.NUMB1120
WHERE (((Станции2023.NUST)=0 Or (Станции2023.NUST) Is Null) AND ((Станции2023.Q)>0) AND ((Станции2023.OBOR)=95) AND ((IIf([main]>0,1,0))=0))
ORDER BY Станции2023.NAME;
