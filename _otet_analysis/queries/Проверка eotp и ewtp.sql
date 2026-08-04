SELECT Станции2024.NAME, Станции2024.Year, [E]-[eotp] AS sn, [E]-[ewtp] AS Ekon, Имена_ОЭС.nameoes, Имена_областей.NAME, Станции2024.NUST
FROM Имена_ОЭС INNER JOIN (Имена_областей INNER JOIN Станции2024 ON Имена_областей.OBL = Станции2024.OBL) ON Имена_ОЭС.oes = Станции2024.OES
WHERE ((([E]-[ewtp])<0));
