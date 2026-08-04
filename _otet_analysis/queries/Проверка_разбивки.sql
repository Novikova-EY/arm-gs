SELECT First(Имена_станций_1.NAME) AS [First-NAME], Sum(Разбивка2002.QOTR) AS [Sum-QOTR], Avg(Станции2002.QOTR) AS [Avg-QOTR]
FROM ((Разбивка2002 INNER JOIN Имена_станций ON Разбивка2002.NUMB1120 = Имена_станций.NUMB) INNER JOIN Имена_станций AS Имена_станций_1 ON Имена_станций.MAIN = Имена_станций_1.NUMB) INNER JOIN Станции2002 ON Имена_станций_1.NUMB = Станции2002.NUMB1120
GROUP BY Имена_станций.MAIN;
