INSERT INTO Станции_из_оборудования ( Выражение1, numb1120 )
SELECT First(Имена_станций.NAME) AS [First-NAME], Турбины.numb1120
FROM (Турбины LEFT JOIN Станции_из_оборудования ON Турбины.numb1120=Станции_из_оборудования.numb1120) INNER JOIN Имена_станций ON Турбины.numb1120=Имена_станций.NUMB
WHERE (((Станции_из_оборудования.numb1120) Is Null))
GROUP BY Турбины.numb1120;
