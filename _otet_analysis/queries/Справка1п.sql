Select numb1120,v,year,obl,oes,NUST as data,"01NUST" as h from [Рабочий(станции)] where NUST>0 UNION Select numb1120,v,year,obl,oes,NT as data,"02NT" as h from [Рабочий(станции)] where NT>0;
