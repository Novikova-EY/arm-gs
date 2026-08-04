SELECT Sum(Станции2001.NUST) AS [Sum-NUST], Sum(Станции2001.nr) AS [Sum-nr], Sum(Станции2001.E) AS [Sum-E], Count(Имена_станций.ordnumb) AS [Count-ordnumb]
FROM Станции2001 INNER JOIN Имена_станций ON Станции2001.NUMB1120=Имена_станций.NUMB
WHERE (((Станции2001.NUST)>0) AND ((Станции2001.B)>0) AND ((z([B])-z([gaz])-z([mazut])-z([gtt]))=0) AND ((z([gaz]))>0) AND ((z([mazut])+z([gtt]))>0) AND ((Имена_станций.Ведомство)=1) AND ((Имена_станций.MAIN) Is Null Or (Имена_станций.MAIN)=0));
