TRANSFORM Sum([Все_угли+показатели].data) AS [Sum-data]
SELECT Имена_станций.ordnumb, [Все_угли+показатели].numb1120, [Все_угли+показатели].toplcode, [Все_угли+показатели].oes, First(Классификтор_топлива.name) AS toplname, First(Имена_станций.NAME) AS name, First([Все_угли+показатели].obl) AS obl, First(Имена_ОЭС.name) AS oesname, First(Имена_областей.NAME) AS oblname
FROM ((([Все_угли+показатели] INNER JOIN Имена_станций ON [Все_угли+показатели].numb1120=Имена_станций.NUMB) INNER JOIN Классификтор_топлива ON [Все_угли+показатели].toplcode=Классификтор_топлива.code) INNER JOIN Имена_ОЭС ON [Все_угли+показатели].oes=Имена_ОЭС.oes) INNER JOIN Имена_областей ON [Все_угли+показатели].obl=Имена_областей.OBL
GROUP BY Имена_станций.ordnumb, [Все_угли+показатели].numb1120, [Все_угли+показатели].toplcode, [Все_угли+показатели].oes
ORDER BY Имена_станций.ordnumb, [Все_угли+показатели].toplcode
PIVOT [Все_угли+показатели].YEAR;
