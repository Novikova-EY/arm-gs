SELECT First(Имена_станций_1.NAME) AS NAME, Имена_станций.MAIN, Min(Станции98.VED) AS Min_VED INTO [Ведомства-для-составных-станций]
FROM Станции98, Имена_станций INNER JOIN Имена_станций AS Имена_станций_1 ON Имена_станций.MAIN=Имена_станций_1.NUMB
WHERE (((Имена_станций_1.OES)=4))
GROUP BY Имена_станций.MAIN
HAVING (((Имена_станций.MAIN)>0));
