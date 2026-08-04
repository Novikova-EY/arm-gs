SELECT Имена_станций.GKF, [Выбросы ЗВ].Year, Count([Выбросы ЗВ].VIBROS_ekol) AS [Count-VIBROS_ekol]
FROM [Выбросы ЗВ] INNER JOIN Имена_станций ON [Выбросы ЗВ].numb1120 = Имена_станций.NUMB
WHERE ((([Выбросы ЗВ].VIBROS_ekol)>0))
GROUP BY Имена_станций.GKF, [Выбросы ЗВ].Year;
