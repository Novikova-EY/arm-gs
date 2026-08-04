SELECT Станции2017.NAME, Станции2017.NUMB1120, KOEFF.NUMB, KOEFF.k, Станции2017.VED, Станции2017.OBOR, Станции2017.E, Станции2017.EURT, Станции2017.Q, Станции2017.numb1, Станции2017.NUST, IIf([E]>0,[ewtp]/[E],0) AS Pewtp, IIf([q]>0,[qotr]/[q],0) AS Pqotr, ([BK]-[BTP]) AS d, IIf([eurt]>0,([eurt]-[BTP])/[eurt],0) AS [сниж btp к eurt], IIf([eurt]>0,([bk]-[eurt])/[eurt],0) AS [повыш bk к eurt], Удельные2017.BK, Удельные2017.BTP, Станции2017.QOTR, Удельные2017.Y, Станции2017.EWTP, Станции2017.TURT, Станции2017.EUST
FROM Удельные2017 INNER JOIN (Станции2017 LEFT JOIN KOEFF ON Станции2017.NUMB1120=KOEFF.NUMB) ON Удельные2017.NUMB1120=Станции2017.NUMB1120
WHERE (((Станции2017.VED)>1))
ORDER BY Станции2017.numb1, Станции2017.NUST;
