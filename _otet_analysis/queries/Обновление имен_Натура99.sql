UPDATE Имена_станций INNER JOIN Натура99 ON Имена_станций.NUMB=Натура99.NUMB1120 SET Натура99.NAME = Имена_станций!name
WHERE (((Натура99.YEAR)=2020));
