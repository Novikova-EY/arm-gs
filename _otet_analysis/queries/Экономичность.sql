SELECT Станции2003.NAME, [ewtp]/[e]*100 AS Pтп, [e]*0.86+[qotr] AS Qп, ([b]-([q]-[qotr])*0.155)*7 AS Qз, [Qп]/[Qз]*100 AS КИТ
FROM Станции2003
WHERE (((Станции2003.VED)>1))
ORDER BY Станции2003.numb1;
