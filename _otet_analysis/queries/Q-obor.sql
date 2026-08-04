SELECT Типы_оборудования.name, Станции2013.OBOR, Sum(Станции2013.NUST) AS [Sum-NUST], Sum(Станции2013.QOTR) AS [Sum-QOTR], Sum(Станции2013.Q) AS [Sum-Q]
FROM Станции2013 INNER JOIN Типы_оборудования ON Станции2013.OBOR=Типы_оборудования.code
WHERE (((Станции2013.VED)>0 And (Станции2013.VED)<3) AND ((Станции2013.OES)=5))
GROUP BY Типы_оборудования.name, Станции2013.OBOR
ORDER BY Станции2013.OBOR;
