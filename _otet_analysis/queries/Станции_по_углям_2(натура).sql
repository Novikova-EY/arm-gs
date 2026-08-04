SELECT w.NUMB1120, w.YEAR, 'кузнецкий' AS topl, [kuzn] as koeff
FROM [Натура99] AS w  
WHERE (((w.kuzn)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'назаровский' AS topl, [nazar] as koeff
FROM [Натура99] AS w  
WHERE (((nazar)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'бородинский' AS topl, [ibor] as koeff
FROM [Натура99] AS w  
WHERE (((ibor)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'березовский' AS topl, [berez] as koeff
FROM [Натура99] AS w  
WHERE (((berez)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'переясловский' AS topl, [per] as koeff
FROM [Натура99] AS w  
WHERE (((per)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'хакасский' AS topl, [hak] as koeff
FROM [Натура99] AS w  
WHERE (((w.hak)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'тувинский' AS topl, [tuv] as koeff
FROM [Натура99] AS w  
WHERE (((w.tuv)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'азейский' AS topl, [azey] as koeff
FROM [Натура99] AS w  
WHERE (((azey)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'черемховский' AS topl, [cher] as koeff
FROM [Натура99] AS w  
WHERE (((cher)>0))
UNION SELECT w.NUMB1120, w.YEAR, 'жеронский' AS topl, [jer] as koeff
FROM [Натура99] AS w  
WHERE (((jer)>0))
UNION
SELECT w.NUMB1120, w.YEAR, 'харанорский' AS topl, [har] as koeff
FROM [Натура99] AS w  
WHERE (((har)>0))
UNION SELECT w.NUMB1120, w.YEAR, 'уртуйский' AS topl, [urt] as koeff
FROM [Натура99] AS w  
WHERE (((urt)>0))
UNION
SELECT w.NUMB1120, w.YEAR, 'якутский' AS topl, [yakut] as koeff
FROM [Натура99] AS w  
WHERE (((w.yakut)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'амурский' AS topl, [amur] as koeff
FROM [Натура99] AS w  
WHERE (((w.amur)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'ургальский' AS topl, [urg] as koeff
FROM [Натура99] AS w  
WHERE (((w.urg)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'ушумунский' AS topl, [ushum] as koeff
FROM [Натура99] AS w  
WHERE (((w.ushum)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'приморский' AS topl, [prim] as koeff
FROM [Натура99] AS w  
WHERE (((w.prim)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'лучегорский' AS topl, [luch] as koeff
FROM [Натура99] AS w  
WHERE (((w.luch)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'магаданский' AS topl, [mag] as koeff
FROM [Натура99] AS w  
WHERE (((w.mag)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'сахалинский' AS topl, [sah] as koeff
FROM [Натура99] AS w  
WHERE (((w.sah)>0))
UNION SELECT w.NUMB1120, w.YEAR, 'камчатский' AS topl, [kamch] as koeff
FROM [Натура99] AS w  
WHERE (((w.kamch)>0));
