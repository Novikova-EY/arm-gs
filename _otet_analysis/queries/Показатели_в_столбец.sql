SELECT w.NAME AS NAME, YEAR,numb1120,oes,obl, nust AS data, 0.1  AS toplcode
FROM [Рабочий(станции)] AS w
union
SELECT w.NAME AS NAME, YEAR,numb1120,oes,obl,e AS data, 0.2  AS toplcode
FROM [Рабочий(станции)] AS w
union
SELECT w.NAME AS NAME, YEAR,numb1120,oes,obl,Q  AS data, 0.3  AS toplcode
FROM [Рабочий(станции)] AS w
UNION
 SELECT w.NAME AS NAME, YEAR, numb1120,oes,obl,B AS data,0.4  AS toplcode
FROM [Рабочий(станции)] AS w
UNION 
SELECT w.NAME AS NAME, YEAR, numb1120,oes,obl,gaz AS data,0.5  AS toplcode
FROM [Рабочий(станции)] AS w
where gaz>0
UNION SELECT w.NAME AS NAME, YEAR, numb1120,oes,obl,mazut AS data,0.6  AS toplcode
FROM [Рабочий(станции)] AS w
where mazut>0
UNION SELECT w.NAME AS NAME, YEAR, numb1120,oes,obl,torf AS data,0.7  AS toplcode
FROM [Рабочий(станции)] AS w
where torf>0
UNION SELECT w.NAME AS NAME, YEAR, numb1120,oes,obl,proch AS data,0.8  AS toplcode
FROM [Рабочий(станции)] AS w
where proch>0
UNION SELECT w.NAME AS NAME, YEAR, numb1120,oes,obl,ugol AS data,0.9  AS toplcode
FROM [Рабочий(станции)] AS w
where ugol>0;
