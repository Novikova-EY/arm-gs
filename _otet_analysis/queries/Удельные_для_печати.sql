SELECT DISTINCTROW Удельные2013.*, Имена_станций.ordnumb, Имена_станций.OES
FROM Имена_станций INNER JOIN Удельные2013 ON Имена_станций.NUMB=Удельные2013.NUMB1120;
