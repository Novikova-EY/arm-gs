SELECT First(Имена_станций.NAME) AS [First-NAME], [станции91(режимы)].NUMB, Sum([станции91(режимы)].Q) AS [Sum-Q], Имена_станций.ordnumb
FROM [станции91(режимы)] INNER JOIN Имена_станций ON [станции91(режимы)].NUMB=Имена_станций.NUMB
GROUP BY [станции91(режимы)].NUMB, Имена_станций.ordnumb
ORDER BY Имена_станций.ordnumb;
