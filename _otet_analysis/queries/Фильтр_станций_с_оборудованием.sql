SELECT t.numb1120
FROM Турбины AS t LEFT JOIN ((Станции2014 AS w LEFT JOIN Доп_угли2014 AS d ON (w.YEAR=d.YEAR) AND (w.NUMB1120=d.NUMB1120)) LEFT JOIN Имена_станций ON w.NUMB1120=Имена_станций.NUMB) ON t.grcode=w.NUMB1120
WHERE (((w.OES)<100))
GROUP BY t.numb1120;
