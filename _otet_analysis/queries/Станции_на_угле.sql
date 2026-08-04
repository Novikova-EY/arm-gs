SELECT Станции2008.NAME, Sum(Станции2008.NUST) AS [Sum-NUST], Sum(Станции2008.UGOL) AS [Sum-UGOL], Sum(Станции2008.PROCH) AS [Sum-PROCH]
FROM Станции2008 INNER JOIN Имена_станций ON Станции2008.NUMB1120=Имена_станций.NUMB
WHERE (((Станции2008.UGOL)>0) AND ((Станции2008.YEAR)=2008) AND ((Имена_станций.MAIN) Is Null) AND ((Станции2008.OES)=1)) OR (((Станции2008.YEAR)=2008) AND ((Имена_станций.MAIN) Is Null) AND ((Станции2008.OES)=1) AND ((Станции2008.PROCH)>0))
GROUP BY Станции2008.NAME;
