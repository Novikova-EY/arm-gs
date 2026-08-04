TRANSFORM Avg(Станции8994.nt) AS Avg_nt
SELECT Станции8994.numb1120 AS Выражение1, First(Станции8994.name) AS name, First(Станции8994.obl) AS obl, First(Станции8994.oes) AS oes, First(Станции8994.ved) AS ved
FROM Станции8994
WHERE (((Станции8994.year)>0))
GROUP BY Станции8994.numb1120
PIVOT Станции8994.year;
