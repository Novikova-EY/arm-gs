TRANSFORM Sum([Станции(архив)].Q) AS [Sum-Q]
SELECT [Станции(архив)].name
FROM [Станции(архив)] INNER JOIN Имена_станций ON [Станции(архив)].numb1120=Имена_станций.NUMB
WHERE (((Имена_станций.MAIN)=0 Or (Имена_станций.MAIN) Is Null) AND (([Станции(архив)].ved)=2 Or ([Станции(архив)].ved)=0 Or ([Станции(архив)].ved) Is Null) AND (([Станции(архив)].obor)<>95))
GROUP BY [Станции(архив)].name
PIVOT [Станции(архив)].year;
