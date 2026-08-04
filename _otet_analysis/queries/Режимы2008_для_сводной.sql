SELECT Имена_областей.NAME AS nameobl, Режимы2008.name, [e]/1000 AS Э, [etp]/1000 AS Этп, Режимы2008.month, Режимы2008.code, Имена_станций.OBL, Имена_станций.OES, Режимы2008.type
FROM (Режимы2008 INNER JOIN Имена_станций ON Режимы2008.code = Имена_станций.NUMB) INNER JOIN Имена_областей ON Имена_станций.OBL = Имена_областей.OBL
ORDER BY Имена_станций.ordnumb, Режимы2008.month;
