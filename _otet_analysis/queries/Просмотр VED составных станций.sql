SELECT DISTINCT st1.NAME, st1.NUMB1120, im1.MAIN, st1.VED, st1.numb1
FROM Станции2021 AS st1 LEFT JOIN Имена_станций AS im1 ON st1.NUMB1120 = im1.NUMB
WHERE (((st1.NUMB1120) In (SELECT DISTINCT MAIN 
        FROM Имена_станций
        WHERE MAIN IS NOT NULL
    ) Or (st1.NUMB1120) In (SELECT DISTINCT NUMB 
        FROM Имена_станций
        WHERE MAIN IS NOT NULL
    )))
ORDER BY st1.numb1;
