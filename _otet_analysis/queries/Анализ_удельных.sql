SELECT Весь_отчет.name, Весь_отчет.year, Весь_отчет.E, Весь_отчет.ewtp
FROM Весь_отчет INNER JOIN Имена_станций ON Весь_отчет.numb1120=Имена_станций.NUMB
WHERE (((Весь_отчет.year)>1997) AND ((Весь_отчет.ewtp)>0) AND ((Весь_отчет.obl)=30) AND ((Имена_станций.MAIN) Is Null))
ORDER BY Весь_отчет.numb1, Весь_отчет.year;
