SELECT First(Имена_станций.NAME) AS [First-NAME], Имена_станций.NUMB, Sum(Турбины.nt) AS [Sum-nt]
FROM Турбины INNER JOIN Имена_станций ON Турбины.numb1120=Имена_станций.NUMB
GROUP BY Имена_станций.NUMB;
