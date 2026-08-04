SELECT w.*, имена_станций.MAIN
FROM (Станции2024 AS w LEFT JOIN доп_угли2024 AS d ON (w.YEAR=d.YEAR) AND (w.NUMB1120=d.NUMB1120)) INNER JOIN имена_станций ON w.NUMB1120=имена_станций.NUMB;
