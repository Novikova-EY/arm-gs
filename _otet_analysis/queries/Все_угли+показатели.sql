SELECT Европ_угли.*
FROM Европ_угли
UNION SELECT Сибирские_угли.*
FROM Сибирские_угли
UNION SELECT Восточные_угли.*
FROM Восточные_угли
UNION SELECT  Показатели_в_столбец.*
FROM  Показатели_в_столбец;
