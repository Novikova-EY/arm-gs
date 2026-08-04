SELECT Kat.OES, [Kat]![E]-[Pavl]![E] AS d_E, [Kat]![Q]-[Pavl]![Q] AS d_Q, Kat.NUMB1120, Pavl.NUMB1120, Kat.numb1, Kat.Q, Pavl.Q, *
FROM Станции2020 AS Kat LEFT JOIN Станции2020_Павловская AS Pavl ON Kat.NUMB1120 = Pavl.NUMB1120
WHERE (((Kat.OES)=3))
ORDER BY Kat.numb1;
