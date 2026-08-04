SELECT Станции2024.NAME, Станции2024.YEAR, ROUND([Q]-[QOTR],3) AS Qkot, Имена_ОЭС.nameoes, Имена_областей.NAME, Станции2024.NUST
FROM Имена_ОЭС INNER JOIN (Имена_областей INNER JOIN Станции2024 ON Имена_областей.OBL=Станции2024.OBL) ON Имена_ОЭС.oes=Станции2024.OES
WHERE ((([Q]-[QOTR])<0));
