SELECT Станции2016.NAME, Станции2016.NUST AS n1, Станции2017.NUST AS n2, [n1]-[n2] AS d
FROM Станции2016 INNER JOIN Станции2017 ON Станции2016.NUMB1120=Станции2017.NUMB1120;
