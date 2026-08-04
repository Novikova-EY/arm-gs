SELECT KOEFF.*, Удельные2013.BK, [Станции(архив)].eurt, Удельные2013.BTP, Удельные2013.Y, [ewtp]/[E] AS Pewtp, [qotr]/[q] AS Pqotr, ([BK]-[BTP])/[BK] AS d, ([eurt]-[BTP])/[eurt] AS [сниж btp к eurt], ([bk]-[eurt])/[eurt] AS [повыш bk к eurt]
FROM ((KOEFF INNER JOIN Имена_станций ON KOEFF.NUMB=Имена_станций.NUMB) INNER JOIN [Станции(архив)] ON KOEFF.NUMB=[Станции(архив)].numb1120) INNER JOIN Удельные2013 ON KOEFF.NUMB=Удельные2013.NUMB1120
WHERE ((([Станции(архив)].year)=2013));
