SELECT [Доп_угли(архив)].*
FROM [Доп_угли(архив)]
where year=1990 or year=1998 or year=1999
union
SELECT [Доп_угли2000].*
FROM [Доп_угли2000]
UNION SELECT [Доп_угли2001].*
FROM [Доп_угли2001];
