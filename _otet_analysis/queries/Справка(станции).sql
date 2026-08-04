SELECT Имена_станций.NAME AS name1, w.numb1120, w.numb1, w.YEAR, Имена_областей.NAME AS oblname, Имена_ОЭС.name AS oesname, w.OBL, w.OES, w.NUST AS f01, iif(z(w.nust)>0,w.e/w.nust*1000,0) AS f02, null AS f03, null AS f04, null AS f05, null AS f06, null AS f07, null AS f08, null AS f09, null AS f10
FROM (((Станции1135_новый AS w LEFT JOIN доп_угли_1135_новый AS d ON (w.numb1120=d.numb1120) AND (w.year=d.year)) INNER JOIN имена_станций ON w.numb1120=имена_станций.numb) INNER JOIN Имена_областей ON w.OBL=Имена_областей.OBL) INNER JOIN Имена_ОЭС ON w.OES=Имена_ОЭС.oes
WHERE ((w.obl=4));
