SELECT w.NUMB1120, w.YEAR, 'кузнецкий' AS topl, [kuzn]/[b]*100 AS pertop,[kuzn] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((w.kuzn)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'назаровский' AS topl, [nazar]/[b]*100 AS pertop,[nazar] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((d.nazar)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'бородинский' AS topl, [ibor]/[b]*100 AS pertop,[ibor] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((d.ibor)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'березовский' AS topl, [berez]/[b]*100 AS pertop,[berez] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((d.berez)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'переясловский' AS topl, [per]/[b]*100 AS pertop,[per] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((d.per)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'хакасский' AS topl, [hak]/[b]*100 AS pertop,[hak] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((w.hak)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'тувинский' AS topl, [tuv]/[b]*100 AS pertop,[tuv] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((w.tuv)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'азейский' AS topl, [azey]/[b]*100 AS pertop,[azey] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((d.azey)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'черемховский' AS topl, [cher]/[b]*100 AS pertop,[cher] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((d.cher)>0))
UNION SELECT w.NUMB1120, w.YEAR, 'жеронский' AS topl, [jer]/[b]*100 AS pertop,[jer] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((d.jer)>0))
UNION
SELECT w.NUMB1120, w.YEAR, 'харанорский' AS topl, [har]/[b]*100 AS pertop,[har] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((d.har)>0))
UNION SELECT w.NUMB1120, w.YEAR, 'уртуйский' AS topl, [urt]/[b]*100 AS pertop,[urt] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((d.urt)>0))
UNION
SELECT w.NUMB1120, w.YEAR, 'якутский' AS topl, [yakut]/[b]*100 AS pertop,[yakut] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((w.yakut)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'амурский' AS topl, [amur]/[b]*100 AS pertop,[amur] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((w.amur)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'ургальский' AS topl, [urg]/[b]*100 AS pertop,[urg] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((w.urg)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'ушумунский' AS topl, [ushum]/[b]*100 AS pertop,[ushum] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((w.ushum)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'приморский' AS topl, [prim]/[b]*100 AS pertop,[prim] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((w.prim)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'лучегорский' AS topl, [luch]/[b]*100 AS pertop,[luch] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((w.luch)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'магаданский' AS topl, [mag]/[b]*100 AS pertop,[mag] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((w.mag)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'сахалинский' AS topl, [sah]/[b]*100 AS pertop,[sah] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((w.sah)>0))
UNION SELECT w.NUMB1120, w.YEAR, 'камчатский' AS topl, [kamch]/[b]*100 AS pertop,[kamch] as rtop,w.ved as ved
FROM [Станции(архив)] AS w LEFT JOIN [Доп_угли(архив)] AS d ON (w.NUMB1120 = d.NUMB1120) AND (w.YEAR = d.YEAR) 
WHERE (((w.kamch)>0));
