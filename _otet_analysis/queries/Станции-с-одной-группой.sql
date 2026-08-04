SELECT First(Имена_станций.NAME) AS [First-NAME], Имена_станций.MAIN
FROM Список_станций, Имена_станций
GROUP BY Имена_станций.MAIN
HAVING (((Count(Список_станций.NUMB))=1));
