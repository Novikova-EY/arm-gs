SELECT First(Станции2013.NAME) AS [First-NAME], Avg(Станции2013!NT)-Sum(Турбины!nt) AS Разница, Avg(Станции2013.NT) AS [Avg-NT], Sum(Турбины.nt) AS [Sum-nt], Станции2013.NUMB1120, Станции2013.numb1
FROM Станции2013 INNER JOIN Турбины ON Станции2013.NUMB1120=Турбины.numb1120
WHERE (((Турбины.dem) Is Null Or (Турбины.dem)=0))
GROUP BY Станции2013.NUMB1120, Станции2013.numb1
HAVING (((Avg(Станции2013!NT)-Sum(Турбины!nt))>0))
ORDER BY Avg(Станции2013!NT)-Sum(Турбины!nt) DESC , Станции2013.numb1;
