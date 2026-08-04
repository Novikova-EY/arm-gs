SELECT DISTINCTROW [Доп_угли_1135(до_2005)].*
FROM [Доп_угли_1135(до_2005)]
UNION SELECT DISTINCTROW [Доп_угли_1135].*
FROM [Доп_угли_1135]
where(year>1999);
