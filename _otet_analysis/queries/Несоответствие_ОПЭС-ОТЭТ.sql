SELECT Списки_агрегатов.stcodeopes, First(ОПЭС.имя) AS [First-имя]
FROM Списки_агрегатов, ОПЭС
WHERE (((Списки_агрегатов.stcode)=0))
GROUP BY Списки_агрегатов.stcodeopes;
