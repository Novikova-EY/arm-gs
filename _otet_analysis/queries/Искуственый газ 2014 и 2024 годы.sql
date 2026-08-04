SELECT Станции2014.NAME AS stanciya, Станции2014.NUMB1120, Станции2014.Year AS god, Станции2014.ISK_GAZ AS [иск газ 2014], Станции2014.PROCH AS Proch_2014, Станции2024.ISK_GAZ AS [искс газ 2024], Доп_угли2024.domen_g, Доп_угли2024.koks_g, Доп_угли2024.prochgaz, Станции2024.PROCH AS Proch_2024, Доп_угли2024.tvproch, Доп_угли2024.szh_gaz, Доп_угли2024.inoe
FROM Доп_угли2024 RIGHT JOIN (Станции2014 LEFT JOIN Станции2024 ON Станции2014.NUMB1120 = Станции2024.NUMB1120) ON Доп_угли2024.NUMB1120 = Станции2024.NUMB1120
WHERE (((Станции2014.ISK_GAZ)>0))
ORDER BY Станции2014.numb1;
