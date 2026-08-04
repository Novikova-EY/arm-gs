SELECT Имена_ОЭС.nameoes AS oesname, Имена_ОЭС.oes, [Новые станции].name, [Новые станции].doc
FROM [Новые станции] INNER JOIN Имена_ОЭС ON [Новые станции].oes=Имена_ОЭС.oes
ORDER BY Имена_ОЭС.oes;
