SELECT DISTINCTROW Рабочий.NAME, Рабочий.YEAR, Рабочий.E, Рабочий.EWTP, Рабочий.EUST, Рабочий.EURT, IIf([qotr]>0,z([EWTP])/z([QOTR])*1000,0) AS Y, IIf([ewtp]>0,IIf([e]<>[ewtp],z(Рабочий!EURT)-IIf(z([k])>0,z(KOEFF!k),1.5)*(1-z(Рабочий!EWTP)/z(Рабочий!E))*100,[eurt]),0) AS BTP, IIf([ewtp]>0,z(([EOTP])-(z([E])-z([EWTP]))*(1-z([SNK])/100))/z([EWTP]),0) AS sntp, IIf(z([e])>z([ewtp]),(z([EUST])-z([EWTP])*z([SNTP])*z([BTP])/1000)/((z([E])-z([EWTP]))*(1-z([SNK])/100))*1000,z([btp])) AS BK, Рабочий.NUMB1120, Рабочий.SNK
FROM Станции2002 AS Рабочий LEFT JOIN KOEFF ON Рабочий.NUMB1120=KOEFF.NUMB
WHERE (((Рабочий.NUST)>0))
ORDER BY Рабочий.numb1;
