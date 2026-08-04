SELECT Станции2018.NAME, Станции2018.OES, Станции2018.NUMB1120, Станции2018.numb1, Станции2018.OBL, Станции2018.EWTP, Станции2018.OBOR
FROM Станции2018 LEFT JOIN KOEFF ON Станции2018.NUMB1120 = KOEFF.NUMB
WHERE (((KOEFF.NUMB) Is Null) AND ((Станции2018.EWTP)>0) AND ((Станции2018.OBOR)<>50));
