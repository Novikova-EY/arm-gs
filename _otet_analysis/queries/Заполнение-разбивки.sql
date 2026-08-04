INSERT INTO Разбивка ( NAME, numb1120 )
SELECT Имена_станций.NAME, Имена_станций.NUMB
FROM Имена_станций, Станции98
WHERE (((Имена_станций.MAIN)>0));
