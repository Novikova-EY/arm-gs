SELECT First(Имена_станций_1.NAME) AS [First-NAME], Min(Станции2000.VED) AS [Min-VED], Имена_станций_1.NUMB INTO вед_сост_стан
FROM Станции2000, Имена_станций INNER JOIN Имена_станций AS Имена_станций_1 ON Имена_станций.MAIN=Имена_станций_1.NUMB
WHERE (((Имена_станций.MAIN)>0))
GROUP BY Имена_станций_1.NUMB;
