INSERT INTO [Станции(архив)]
SELECT DISTINCTROW Станции2024.*
FROM Станции2024 LEFT JOIN [Станции(архив)] ON Станции2024.NUMB1120 = [Станции(архив)].numb1120;
