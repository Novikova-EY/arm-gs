SELECT Удельные2011_2.YEAR AS Выражение1, Удельные2011_2.NUMB1120 AS Выражение2, Удельные2011_2.NAME AS Выражение3
FROM Удельные2011_2
WHERE ((([Удельные2011_2].[YEAR]) In (SELECT [YEAR] FROM [Удельные2011_2] As Tmp GROUP BY [YEAR],[NUMB1120] HAVING Count(*)>1  And [NUMB1120] = [Удельные2011_2].[NUMB1120])))
ORDER BY Удельные2011_2.YEAR, Удельные2011_2.NUMB1120;
