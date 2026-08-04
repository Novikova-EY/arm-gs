SELECT t_2023.t_2023, t_2024.t_2024, t_2024.NUMB1120, Имена_станций.NAME AS stancia, Имена_ОЭС.nameoes, Имена_областей.NAME AS oblast
FROM (((t_2023 INNER JOIN t_2024 ON t_2023.NUMB1120 = t_2024.NUMB1120) INNER JOIN Имена_станций ON t_2024.NUMB1120 = Имена_станций.NUMB) INNER JOIN Имена_ОЭС ON Имена_станций.OES = Имена_ОЭС.oes) INNER JOIN Имена_областей ON Имена_станций.OBL = Имена_областей.OBL
WHERE (((t_2024.t_2024)<>[t_2023]));
