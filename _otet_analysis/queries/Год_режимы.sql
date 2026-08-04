SELECT First(Имена_станций.NAME) AS [First-NAME], [станции95(режимы)].NUMB, Sum([станции95(режимы)].Q) AS [Sum-Q], Имена_станций.ordnumb
FROM [станции95(режимы)] INNER JOIN Имена_станций ON [станции95(режимы)].NUMB=Имена_станций.NUMB
GROUP BY [станции95(режимы)].NUMB, Имена_станций.ordnumb
ORDER BY Имена_станций.ordnumb;
