SELECT s.NAME
FROM Имена_станций AS s INNER JOIN Имена_станций ON s.NUMB=Имена_станций.MAIN
WHERE (((s.COMP)=1) AND ((s.D)=1))
GROUP BY s.NAME, Имена_станций.R
HAVING (((Имена_станций.R)=1) AND ((Count(Имена_станций.R))>1));
