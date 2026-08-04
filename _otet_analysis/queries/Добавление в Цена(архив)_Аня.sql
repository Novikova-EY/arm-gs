INSERT INTO [Цена(архив)]
SELECT DISTINCTROW Цена2021.*
FROM Цена2021 LEFT JOIN [Цена(архив)] ON Цена2021.NUMB1120 = [Цена(архив)].NUMB1120;
