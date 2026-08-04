SELECT First(Имена_станций.NAME) AS [First-NAME], Max(Станции_89_2000.ugol) AS [Max-ugol], Станции_89_2000.NUMB1120, Имена_станций.ordnumb
FROM Станции_89_2000 INNER JOIN Имена_станций ON Станции_89_2000.NUMB1120=Имена_станций.NUMB
WHERE (((Станции_89_2000.ER)=11 Or (Станции_89_2000.ER)=12) AND ((Имена_станций.MAIN)=0 Or (Имена_станций.MAIN) Is Null))
GROUP BY Станции_89_2000.NUMB1120, Имена_станций.ordnumb
HAVING (((Max(Станции_89_2000.ugol))>0));
