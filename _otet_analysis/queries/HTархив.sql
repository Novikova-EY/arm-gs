SELECT DISTINCTROW Рабочий.name, Рабочий.Year, IIf([qotr]>0,z([EWTP])/z([QOTR])*1000,0) AS Y, Рабочий.E, Рабочий.ewtp, Рабочий.eust, Рабочий.eurt, IIf([ewtp]>0,IIf([e]<>[ewtp],z([Рабочий]![EURT])-IIf(z([k])>0,z([KOEFF]![k]),1.5)*(1-z([Рабочий]![EWTP])/z([Рабочий]![E]))*100,[eurt]),0) AS BTP, IIf([ewtp]>0,z(([EOTP])-(z([E])-z([EWTP]))*(1-z([SNK])/100))/z([EWTP]),0) AS sntp, IIf(z([e])>z([ewtp]),(z([EUST])-z([EWTP])*z([SNTP])*z([BTP])/1000)/((z([E])-z([EWTP]))*(1-z([SNK])/100))*1000,z([btp])) AS BK, Рабочий.numb1120, Рабочий.snk
FROM [Станции(архив)] AS Рабочий LEFT JOIN KOEFF ON Рабочий.numb1120 = KOEFF.NUMB
WHERE (((Рабочий.Year)>1997) AND ((Рабочий.nust)>0))
ORDER BY Рабочий.numb1, Рабочий.Year, Рабочий.Year;
