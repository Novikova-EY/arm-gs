SELECT [Удельные(архив)].YEAR, [Удельные(архив)].NUMB1120, [Удельные(архив)].NAME
FROM [Удельные(архив)]
WHERE ((([Удельные(архив)].YEAR) In (SELECT [YEAR] FROM [Удельные(архив)] As Tmp GROUP BY [YEAR],[NUMB1120] HAVING Count(*)>1  And [NUMB1120] = [Удельные(архив)].[NUMB1120])))
ORDER BY [Удельные(архив)].YEAR, [Удельные(архив)].NUMB1120;
