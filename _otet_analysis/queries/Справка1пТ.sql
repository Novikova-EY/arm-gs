TRANSFORM Avg(Справка1п.data) AS data
SELECT Справка1п.numb1120, Справка1п.v, Справка1п.h AS h, Справка1п.obl, Справка1п.oes
FROM Справка1п
GROUP BY Справка1п.numb1120, Справка1п.v, Справка1п.h, Справка1п.obl, Справка1п.oes
PIVOT Справка1п.year;
