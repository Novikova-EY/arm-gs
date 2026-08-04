SELECT Имена_ОЭС.name, Имена_областей.NAME AS obl, Станции2024.NAME, [E]-[EOTP] AS SN, [E]*[SNK]/100+[Q]*[SNT]/1000 AS SN1, Abs([SN]-[Sn1]) AS d, Станции2024.numb1
FROM (Станции2024 INNER JOIN Имена_областей ON Станции2024.OBL = Имена_областей.OBL) INNER JOIN Имена_ОЭС ON Станции2024.OES = Имена_ОЭС.oes
ORDER BY Станции2024.numb1;
