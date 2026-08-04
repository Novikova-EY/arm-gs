INSERT INTO [Доп_угли(архив)]
SELECT DISTINCTROW Доп_угли2024.*
FROM Доп_угли2024 LEFT JOIN [Доп_угли(архив)] ON Доп_угли2024.NUMB1120 = [Доп_угли(архив)].NUMB1120;
