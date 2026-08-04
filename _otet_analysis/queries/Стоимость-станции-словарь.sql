SELECT Станции2017.*, Имена_станций.MAIN
FROM Станции2017 INNER JOIN Имена_станций ON Станции2017.NUMB1120=Имена_станций.NUMB
WHERE (((Имена_станций.MAIN)=0 Or (Имена_станций.MAIN) Is Null));
