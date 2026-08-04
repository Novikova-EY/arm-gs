INSERT INTO [Удельные(архив)]
SELECT DISTINCTROW Удельные2023.*
FROM Удельные2023 LEFT JOIN [Удельные(архив)] ON Удельные2023.NUMB1120 = [Удельные(архив)].NUMB1120;
