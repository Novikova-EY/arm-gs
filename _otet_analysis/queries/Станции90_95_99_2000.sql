SELECT [Станции(архив)].*
FROM [Станции(архив)]
where year=1990 or year=1995 or year=1999 or year=2000
UNION SELECT [Станции2000].*
FROM [Станции2000];
