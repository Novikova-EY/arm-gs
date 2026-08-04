SELECT Имена_станций.NAME, Sum(Турбины.nt) AS [Sum-nt], Турбины.numb1120
FROM Турбины LEFT JOIN Имена_станций ON Турбины.numb1120=Имена_станций.NUMB
WHERE (((Турбины.dem) Is Null))
GROUP BY Имена_станций.NAME, Турбины.numb1120;
