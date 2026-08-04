SELECT Затраты_2021.NUMB1120, Count(*) AS CountOfRecords
FROM Затраты_2021
GROUP BY Затраты_2021.NUMB1120
HAVING (((Count(*))>21));
