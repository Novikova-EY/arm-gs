SELECT 
  Списки_агрегатов.grcode,
  First(Списки_агрегатов.stcode) AS [First-stcode],
  2023 AS Год,
  Count(Списки_агрегатов.[2023]) AS Количество
FROM Списки_агрегатов
WHERE Списки_агрегатов.ur = 1 AND Списки_агрегатов.[2023] > 0
GROUP BY Списки_агрегатов.grcode

UNION ALL

SELECT 
  Списки_агрегатов.grcode,
  First(Списки_агрегатов.stcode),
  2022,
  Count(Списки_агрегатов.[2022])
FROM Списки_агрегатов
WHERE Списки_агрегатов.ur = 1 AND Списки_агрегатов.[2022] > 0
GROUP BY Списки_агрегатов.grcode

UNION ALL

SELECT 
  Списки_агрегатов.grcode,
  First(Списки_агрегатов.stcode),
  2021,
  Count(Списки_агрегатов.[2021])
FROM Списки_агрегатов
WHERE Списки_агрегатов.ur = 1 AND Списки_агрегатов.[2021] > 0
GROUP BY Списки_агрегатов.grcode

UNION ALL

SELECT 
  Списки_агрегатов.grcode,
  First(Списки_агрегатов.stcode),
  2020,
  Count(Списки_агрегатов.[2020])
FROM Списки_агрегатов
WHERE Списки_агрегатов.ur = 1 AND Списки_агрегатов.[2020] > 0
GROUP BY Списки_агрегатов.grcode

UNION ALL

SELECT 
  Списки_агрегатов.grcode,
  First(Списки_агрегатов.stcode),
  2019,
  Count(Списки_агрегатов.[2019])
FROM Списки_агрегатов
WHERE Списки_агрегатов.ur = 1 AND Списки_агрегатов.[2019] > 0
GROUP BY Списки_агрегатов.grcode

UNION ALL SELECT 
  Списки_агрегатов.grcode,
  First(Списки_агрегатов.stcode),
  2018,
  Count(Списки_агрегатов.[2018])
FROM Списки_агрегатов
WHERE Списки_агрегатов.ur = 1 AND Списки_агрегатов.[2018] > 0
GROUP BY Списки_агрегатов.grcode

UNION ALL SELECT 
  Списки_агрегатов.grcode,
  First(Списки_агрегатов.stcode),
  2017,
  Count(Списки_агрегатов.[2017])
FROM Списки_агрегатов
WHERE Списки_агрегатов.ur = 1 AND Списки_агрегатов.[2017] > 0
GROUP BY Списки_агрегатов.grcode;
