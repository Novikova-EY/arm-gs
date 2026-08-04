SELECT SUMNT.[First-NAME], Abs([Sum-nt]-Станции2000!NT) AS d, SUMNT.[Sum-nt], Станции2000.NT AS Выражение1
FROM SUMNT, Имена_станций, Станции2000
WHERE (((Abs([Sum-nt]-Станции2000!NT))>1))
ORDER BY Имена_станций.ordnumb;
