SELECT d.*, w.OES, w.OBL
FROM (Станции2024 AS w INNER JOIN доп_угли2024 AS d ON (w.NUMB1120=d.NUMB1120) AND (w.YEAR=d.YEAR)) INNER JOIN имена_станций ON w.NUMB1120=имена_станций.NUMB;
