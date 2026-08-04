SELECT Имена_ОЭС.abbr, Станции2014.numb1, Станции2014.NAME, Станции2014.NT, Сумма_тепл_мощн.[Sum-nt], [NT]-[Sum-nt] AS Дельта, Сумма_тепл_мощн.numb1120
FROM (Станции2014 LEFT JOIN Сумма_тепл_мощн ON Станции2014.NUMB1120=Сумма_тепл_мощн.numb1120) INNER JOIN Имена_ОЭС ON Станции2014.OES=Имена_ОЭС.oes
WHERE ((([NT]-[Sum-nt])<>0))
ORDER BY Станции2014.numb1;
