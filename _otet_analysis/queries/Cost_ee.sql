SELECT Станции2021.NUMB1120, Станции2021.year, Затраты_2021!Zatr_E/(Станции2021!EOTP*1000) AS cena_e, Имена_станций.NAME, Имена_станций.ordnumb, Затраты_2021!Zatr_Q/(Станции2021!Q*1000) AS cena_q, Затраты_2021!Zatr_P/(Станции2021!NUST*1000) AS cena_p INTO Цена_энергии_2021
FROM Станции2021 INNER JOIN (Затраты_2021 INNER JOIN Имена_станций ON Затраты_2021.NUMB1120=Имена_станций.NUMB) ON Станции2021.NUMB1120=Затраты_2021.NUMB1120
WHERE (((Затраты_2021.code_zatr)=10))
ORDER BY Имена_станций.ordnumb;
