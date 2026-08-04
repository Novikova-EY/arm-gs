SELECT Станции2004.NAME, Станции2004.NUST AS n1, Станции2005.NUST AS n2, Станции2005.numb1
FROM Станции2004 INNER JOIN Станции2005 ON Станции2004.NUMB1120=Станции2005.NUMB1120
ORDER BY Станции2005.numb1;
