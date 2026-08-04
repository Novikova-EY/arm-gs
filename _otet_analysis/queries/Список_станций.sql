SELECT Имена_станций.NAME AS name1, Имена_станций.NUMB, Имена_станций.ordnumb AS numb1, Имена_станций.OBL, Имена_станций.OES, Имена_областей.NAME AS oblname, Имена_ОЭС.name AS oesname
FROM ((Имена_станций INNER JOIN Имена_областей ON Имена_станций.OBL=Имена_областей.OBL) INNER JOIN Имена_ОЭС ON Имена_станций.OES=Имена_ОЭС.oes) INNER JOIN Фильтр_станций ON Имена_станций.NUMB=Фильтр_станций.NUMB1120
ORDER BY Имена_станций.ordnumb;
