SELECT w.*, имена_станций.MAIN, имена_станций.форэм
FROM Станции2017 AS w INNER JOIN имена_станций ON w.NUMB1120=имена_станций.NUMB
ORDER BY w.numb1, w.YEAR;
