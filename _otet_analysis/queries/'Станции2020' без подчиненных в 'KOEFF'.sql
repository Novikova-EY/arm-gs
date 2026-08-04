SELECT Станции2020.NAME, Станции2020.NUMB1120, Станции2020.numb1, Станции2020.VED, Станции2020.Q, Станции2020.OBOR
FROM Станции2020 LEFT JOIN KOEFF ON Станции2020.NUMB1120 = KOEFF.NUMB
WHERE (((KOEFF.NUMB) Is Null) AND ((Станции2020.VED)=2 Or (Станции2020.VED)=3) AND ((Станции2020.OBOR)<>95));
