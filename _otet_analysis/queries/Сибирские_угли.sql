SELECT w.NAME AS NAME, YEAR,numb1120,oes,obl, kuzn AS data, 10 AS toplcode
FROM [Рабочий(станции)] AS w
WHERE (((kuzn)>0))
union
SELECT d.NAME AS NAME, YEAR,numb1120,oes,obl,kuzngd  AS data, 10.3 AS toplcode
FROM [Рабочий(доп_угли)] AS d
WHERE (((d.kuzngd)>0))
union
SELECT d.NAME AS NAME, YEAR,numb1120,oes,obl,kuznt  AS data, 10.1 AS toplcode
FROM [Рабочий(доп_угли)] AS d
WHERE (((d.kuznt)>0))
union
SELECT d.NAME AS NAME, YEAR,numb1120,oes,obl,kuznss  AS data, 10.2 AS toplcode
FROM [Рабочий(доп_угли)] AS d
WHERE (((d.kuznss)>0))
union
SELECT d.NAME AS NAME, YEAR,numb1120,oes,obl,kuznun  AS data, 10.4 AS toplcode
FROM [Рабочий(доп_угли)] AS d
WHERE (((d.kuznun)>0))
union
SELECT w.NAME AS NAME, YEAR,numb1120,oes,obl,kan AS data, 16.5  AS toplcode
FROM [Рабочий(станции)] AS w
WHERE (((kan)>0))
union
SELECT d.NAME AS NAME, YEAR,numb1120,oes,obl,nazar  AS data, 17 AS toplcode
FROM [Рабочий(доп_угли)] AS d
WHERE (((d.nazar)>0))
union
SELECT d.NAME AS NAME, YEAR,numb1120,oes,obl,ibor  AS data,18 AS toplcode
FROM [Рабочий(доп_угли)] AS d
WHERE (((d.ibor)>0))
union
SELECT d.NAME AS NAME, YEAR,numb1120,oes,obl,berez  AS data, 19 AS toplcode
FROM [Рабочий(доп_угли)] AS d
WHERE (((d.berez)>0))
union
SELECT d.NAME AS NAME, YEAR,numb1120,oes,obl,per  AS data,19.1 AS toplcode
FROM [Рабочий(доп_угли)] AS d
WHERE (((d.per)>0))
union
SELECT w.NAME AS NAME,YEAR,numb1120,oes,obl, tuv AS data,21  AS toplcode
FROM [Рабочий(станции)] AS w
WHERE (((tuv)>0))
union
SELECT w.NAME AS NAME, YEAR, numb1120,oes,obl,hak  AS data, 20 AS toplcode
FROM [Рабочий(станции)] AS w
WHERE (((hak)>0))
union
SELECT w.NAME AS NAME,YEAR,numb1120,oes,obl, irkut AS data, 21.5 AS toplcode
FROM [Рабочий(станции)] AS w
WHERE (((irkut)>0))
union
SELECT d.NAME AS NAME, YEAR,numb1120,oes,obl,azey  AS data, 22 AS toplcode
FROM [Рабочий(доп_угли)] AS d
WHERE (((d.azey)>0))
union
SELECT d.NAME AS NAME, YEAR,numb1120,oes,obl,cher  AS data,23 AS toplcode
FROM [Рабочий(доп_угли)] AS d
WHERE (((d.cher)>0))
union
SELECT w.NAME AS NAME,YEAR,numb1120,oes,obl, bur AS data, 23.5  AS toplcode
FROM [Рабочий(станции)] AS w
WHERE (((bur)>0))
union
SELECT d.NAME AS NAME, YEAR,numb1120,oes,obl,gusin  AS data, 24 AS toplcode
FROM [Рабочий(доп_угли)] AS d
WHERE (((d.gusin)>0))
union
SELECT d.NAME AS NAME, YEAR,numb1120,oes,obl,tugn  AS data,25 AS toplcode
FROM [Рабочий(доп_угли)] AS d
WHERE (((d.tugn)>0))
UNION SELECT w.NAME AS NAME,YEAR,numb1120,oes,obl, chit AS data, 26 AS toplcode
FROM [Рабочий(станции)] AS w
WHERE (((chit)>0));
