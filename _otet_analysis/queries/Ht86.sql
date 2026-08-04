SELECT DISTINCTROW Рабочий.NAME, Рабочий.Year, KOEFF.k, IIf([ved]>1,IIf([qotr]>0,z([EWTP])/z([QOTR])*1000,0),0) AS Y, IIf([ved]>1 And z([ewtp])>0,IIf([e]<>[ewtp],z(Рабочий!EURT)-z(KOEFF!k)*(1-z(Рабочий!EWTP)/z(Рабочий!E))*100,[eurt]),0) AS BTP, IIf([ved]>1 And [ewtp]>0,z(([EOTP])-(z([E])-z([EWTP]))*(1-z([SNK])/100))/z([EWTP]),0) AS SNTP, IIf([ved]>1 And [ved]<4 And z([ewtp])>0,IIf(z([e])>z([ewtp]),(z([EUST])-z([EWTP])*z([SNTP])*z([BTP])/1000)/((z([E])-z([EWTP]))*(1-z([SNK])/100))*1000,z([btp])),[eurt]) AS BK, Рабочий.NUMB1120, Рабочий.SNK INTO Удельные2024
FROM Рабочий LEFT JOIN KOEFF ON Рабочий.NUMB1120 = KOEFF.NUMB
WHERE (((Рабочий.NUST)>0) AND ((Рабочий.VED)>0))
ORDER BY Рабочий.numb1;
