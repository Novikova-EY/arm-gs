DELETE *
FROM Доп_угли2023
WHERE numb1120 IN (

    SELECT im.numb

    FROM [Имена_станций] AS im

    WHERE im.OES IN (5)

);
