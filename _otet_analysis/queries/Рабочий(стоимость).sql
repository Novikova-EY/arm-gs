SELECT s.*, w.OES, w.OBL
FROM (Станции2024 AS w INNER JOIN Стоимость2024 AS s ON (w.NUMB1120=s.NUMB1120) AND (w.YEAR=s.YEAR)) INNER JOIN имена_станций ON w.NUMB1120=имена_станций.NUMB;
