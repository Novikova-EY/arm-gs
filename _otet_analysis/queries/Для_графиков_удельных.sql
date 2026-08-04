SELECT Весь_отчет.name, Весь_отчет.year, [ewtp]/[E]*100 AS p, Весь_отчет.eurt
FROM Весь_отчет
WHERE (((Весь_отчет.year)>1995) AND ((Весь_отчет.E)>0))
ORDER BY Весь_отчет.numb1, Весь_отчет.year;
