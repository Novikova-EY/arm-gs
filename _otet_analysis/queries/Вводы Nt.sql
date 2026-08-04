SELECT Имена_станций.NAME, Турбины.stnumb, Турбины.yearin, Турбины.nt, Имена_станций.OES, Имена_станций.NUMB
FROM Турбины INNER JOIN Имена_станций ON Турбины.numb1120=Имена_станций.NUMB
WHERE (((Турбины.yearin)=2001 Or (Турбины.yearin)=2002 Or (Турбины.yearin)=2003 Or (Турбины.yearin)=2004) AND ((Турбины.nt)>0) AND ((Имена_станций.NUMB)<>0))
ORDER BY Имена_станций.OES;
