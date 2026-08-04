SELECT Затраты_2.NUMB1120, Имена_станций.NAME, [Затраты_2]![110]/[Затраты_2]![10] AS d_topl, [Затраты_2]![10]-[Затраты_2]![110] AS proch_zatr, Затраты_2.zatraty, Cost_ee.cena_e
FROM (Затраты_2 INNER JOIN Имена_станций ON Затраты_2.NUMB1120 = Имена_станций.NUMB) INNER JOIN Cost_ee ON Имена_станций.ordnumb = Cost_ee.ordnumb
WHERE (((Затраты_2.zatraty)=" Zatr_E"))
ORDER BY Имена_станций.ordnumb, Затраты_2.zatraty;
