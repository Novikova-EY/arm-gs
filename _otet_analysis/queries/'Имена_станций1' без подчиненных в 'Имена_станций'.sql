SELECT Имена_станций1.NAME, Имена_станций1.NUMB
FROM Имена_станций1 LEFT JOIN Имена_станций ON Имена_станций1.[NUMB] = Имена_станций.[NUMB]
WHERE (((Имена_станций.NUMB) Is Null));
