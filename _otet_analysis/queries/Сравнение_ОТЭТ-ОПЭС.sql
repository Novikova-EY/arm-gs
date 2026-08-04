SELECT Имена_станций.NAME
FROM Имена_станций LEFT JOIN [ОПЭС-ОТЭТ] ON Имена_станций.NUMB=[ОПЭС-ОТЭТ].ОТЭТ
WHERE (((Имена_станций.MAIN) Is Null) AND (([ОПЭС-ОТЭТ].ОПЭС) Is Null))
ORDER BY Имена_станций.ordnumb;
