SELECT Имена_ОЭС.name, Имена_областей.NAME AS obl, [Станции(архив)].name, [Станции(архив)].year, [E]-[EOTP] AS SN, [E]*[SNK]/100+[Q]*[SNT]/1000 AS SN1, Abs([SN]-[Sn1]) AS d
FROM ([Станции(архив)] INNER JOIN Имена_областей ON [Станции(архив)].obl = Имена_областей.OBL) INNER JOIN Имена_ОЭС ON [Станции(архив)].oes = Имена_ОЭС.oes
WHERE ((([Станции(архив)].obor)<>95))
ORDER BY [Станции(архив)].numb1, [Станции(архив)].year;
