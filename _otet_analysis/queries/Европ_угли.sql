SELECT w.NAME AS NAME, YEAR,numb1120,oes,obl, DON AS data, 6  AS toplcode
FROM [Рабочий(станции)] AS w
WHERE (((DON)>0))
union
SELECT w.NAME AS NAME, YEAR,numb1120,oes,obl,pech AS data, 7.5  AS toplcode
FROM [Рабочий(станции)] AS w
WHERE (((pech)>0))
union
SELECT d.NAME AS NAME, YEAR,numb1120,oes,obl,vork AS data, 8  AS toplcode
FROM [Рабочий(доп_угли)] AS d
WHERE (((d.vork)>0))
union
SELECT d.NAME AS NAME, YEAR,numb1120,oes,obl,intin  AS data, 9  AS toplcode
FROM [Рабочий(доп_угли)] AS d
WHERE (((intin)>0))
union
SELECT w.NAME AS NAME,YEAR,numb1120,oes,obl, podm AS data,7  AS toplcode
FROM [Рабочий(станции)] AS w
WHERE (((podm)>0))
union
SELECT w.NAME AS NAME, YEAR, numb1120,oes,obl,ural AS data,10.5  AS toplcode
FROM [Рабочий(станции)] AS w
WHERE (((ural)>0))
union
SELECT d.NAME AS NAME, YEAR,numb1120,oes,obl,sver  AS data, 11 AS toplcode
FROM [Рабочий(доп_угли)] AS d
WHERE (((d.sver)>0))
union
SELECT d.NAME AS NAME, YEAR,numb1120,oes,obl,chel  AS data, 12 AS toplcode
FROM [Рабочий(доп_угли)] AS d
WHERE (((d.chel)>0))
union
SELECT d.NAME AS NAME, YEAR,numb1120,oes,obl,kizel  AS data, 13 AS toplcode
FROM [Рабочий(доп_угли)] AS d
WHERE (((d.kizel)>0))
union
SELECT w.NAME AS NAME,YEAR,numb1120,oes,obl, bashk AS data, 14 AS toplcode
FROM [Рабочий(станции)] AS w
WHERE (((bashk)>0))
union
SELECT w.NAME AS NAME,YEAR,numb1120,oes,obl,kazah AS data, 15 AS toplcode
FROM [Рабочий(станции)] AS w
WHERE (((kazah)>0))
UNION SELECT w.NAME AS NAME,YEAR,numb1120,oes,obl, karag AS data, 16 AS toplcode
FROM [Рабочий(станции)] AS w
WHERE (((karag)>0));
