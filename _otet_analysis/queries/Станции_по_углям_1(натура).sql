SELECT w.NUMB1120, w.YEAR, 'воркутинский' AS topl, [vork] as koeff 
FROM [Натура99] AS w    
WHERE (((vork)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'интинский' AS topl, [int] as koeff
FROM [Натура99] AS w    
WHERE (((int)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'подмосковный' AS topl, [podm] as koeff 
FROM [Натура99] AS w    
WHERE (((w.podm)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'донецкий' AS topl, [don] as koeff 
FROM [Натура99] AS w    
WHERE (((w.don)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'свердловский' AS topl, [sver] as koeff 
FROM [Натура99] AS w    
WHERE (((sver)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'челябинский' AS topl, [chel] as koeff 
FROM [Натура99] AS w    
WHERE (((chel)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'кизеловский' AS topl, [kizel] as koeff 
FROM [Натура99] AS w    
WHERE (((kizel)>0))
UNION 
SELECT w.NUMB1120, w.YEAR, 'башкирский' AS topl, [bashk] as koeff 
FROM [Натура99] AS w    
WHERE (((w.bashk)>0))
UNION SELECT w.NUMB1120, w.YEAR, 'карагандинский' AS topl, [karag] as koeff 
FROM [Натура99] AS w    
WHERE (((w.karag)>0))
UNION SELECT w.NUMB1120, w.YEAR, 'экибастузский' AS topl, [ekib] as koeff 
FROM [Натура99] AS w    
WHERE (((w.ekib)>0));
