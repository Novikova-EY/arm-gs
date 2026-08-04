SELECT NAME , YEAR,numb1120,oes,obl, yakut AS data,27 AS toplcode
FROM [Рабочий(станции)] AS w
WHERE (((yakut)>0))
union
SELECT NAME , YEAR,numb1120,oes,obl,amur  AS data,29 AS toplcode
FROM [Рабочий(станции)] AS w
WHERE (((amur)>0))
union
SELECT  NAME,YEAR,numb1120,oes,obl, prim AS data, 28 AS toplcode
FROM [Рабочий(станции)] AS w
WHERE (((prim)>0))
union
SELECT NAME , YEAR, numb1120,oes,obl,ushum  AS data, 31 AS toplcode
FROM [Рабочий(станции)] AS w
WHERE (((ushum)>0))
union
SELECT NAME ,YEAR,numb1120,oes,obl, urg  AS data, 30 AS toplcode
FROM [Рабочий(станции)] AS w
WHERE (((urg)>0))
union
SELECT NAME ,YEAR,numb1120,oes,obl, chukot  AS data, 34 AS toplcode
FROM [Рабочий(станции)] AS w
WHERE (((chukot)>0))
union
SELECT NAME ,YEAR,numb1120,oes,obl, kamch  AS data, 35 AS toplcode
FROM [Рабочий(станции)] AS w
WHERE (((kamch)>0))
union
SELECT NAME ,YEAR,numb1120,oes,obl, sah  AS data, 33 AS toplcode
FROM [Рабочий(станции)] AS w
WHERE (((sah)>0))
UNION SELECT NAME ,YEAR,numb1120,oes,obl, mag AS data, 32 AS toplcode
FROM [Рабочий(станции)] AS w
WHERE (((mag)>0));
