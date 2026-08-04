SELECT Имена_станций.GKF, [Выбросы ПГ].Year, Count([Выбросы ПГ].CO2) AS [Count-CO2]
FROM [Выбросы ПГ] INNER JOIN Имена_станций ON [Выбросы ПГ].numb1120 = Имена_станций.NUMB
WHERE ((([Выбросы ПГ].CO2)>0))
GROUP BY Имена_станций.GKF, [Выбросы ПГ].Year;
