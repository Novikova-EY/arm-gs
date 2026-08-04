SELECT w.NUMB1120, w.YEAR, 'газ' AS topl, [gaz]/[b]*100 AS pertop,[gaz] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((w.gaz)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'воркутинский' AS topl, [vork]/[b]*100 AS pertop,[vork] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((d.vork)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'интинский' AS topl, [int]/[b]*100 AS pertop,[int] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((d.int)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'подмосковный' AS topl, [podm]/[b]*100 AS pertop,[podm] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((w.podm)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'донецкий' AS topl, [don]/[b]*100 AS pertop,[don] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((w.don)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'свердловский' AS topl, [sver]/[b]*100 AS pertop,[sver] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((d.sver)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'челябинский' AS topl, [chel]/[b]*100 AS pertop,[chel] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((d.chel)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'кизеловский' AS topl, [kizel]/[b]*100 AS pertop,[kizel] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((d.kizel)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'башкирский' AS topl, [bashk]/[b]*100 AS pertop,[bashk] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((w.bashk)>0))
UNION SELECT w.NUMB1120, w.YEAR, 'карагандинский' AS topl, [karag]/[b]*100 AS pertop,[karag] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((w.karag)>0))
UNION SELECT w.NUMB1120, w.YEAR, 'экибастузский' AS topl, [ekib]/[b]*100 AS pertop,[ekib] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((w.ekib)>0));
