SELECT NAME,YEAR,NUST,0 as nr,E,eotp,ewtp,eurt,eust,Q,turt,tust,b,gaz,mazut,gtt,torf,slan,proch,ugol,don,arkt,pech,podm,kuzn,ural,bashk,ekib,karag,hak,kan,tuv,irkut,bur,chit,ner,raich,prim,urg,luch,mag,sah,qotr,NT,snk,obor,VED,OBL,DEP,OES,ER,NUMB1120,numb1
FROM [станции(архив)]
UNION SELECT NAME,YEAR,NUST,nr,E,eotp,ewtp,eurt,eust,Q,turt,tust,b,gaz,mazut,gtt,torf,slan,proch,ugol,don,arkt,pech,podm,kuzn,ural,bashk,ekib,karag,hak,kan,tuv,irkut,bur,chit,ner,raich,prim,urg,luch,mag,sah,qotr,NT,snk,obor,VED,OBL,DEP,OES,ER,NUMB1120,numb1
FROM станции1135_новый
where(year=2000) or year>2004
ORDER BY numb1120, year;
