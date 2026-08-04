SELECT Станции2018.NAME, Станции2018.NUST, Станции2018.E, [e]/[nust]*1000 AS H, Станции2018.NUMB1120
FROM Станции2018
WHERE (((Станции2018.NUST)>0))
ORDER BY Станции2018.NUMB1120;
