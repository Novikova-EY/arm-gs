SELECT Станции2002.NAME, Рабочая_ОРГРЭС.Code, Станции2002.NUST, Рабочая_ОРГРЭС.Value, [nust]-[value] AS d
FROM Рабочая_ОРГРЭС LEFT JOIN Станции2002 ON Рабочая_ОРГРЭС.Code=Станции2002.NUMB1120;
