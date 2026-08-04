SELECT "Всего" AS name1, 0 AS numb1, 0 AS numb1120, s.YEAR, First(s.sum) AS [sum], Null AS oblname, Null AS oesname, Null AS OES, 0 AS obl, Sum(s.f01) AS f01, Sum(s.f02) AS f02, Sum(s.f03) AS f03, Sum(s.f04) AS f04, Sum(s.f05) AS f05, Sum(s.f06) AS f06, Sum(s.f07) AS f07, Sum(s.f08) AS f08, Sum(s.f09) AS f09, Sum(s.f10) AS f10
FROM [справка(станции)] AS s
WHERE (((s.sum)>0))
GROUP BY s.YEAR;
