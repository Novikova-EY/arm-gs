SELECT First(ОРГРЭС98.name) AS [First-name], ОРГРЭС98.NUMB, Avg(ОРГРЭС98.NUST) AS [Avg-NUST], Avg(ОРГРЭС98.NT) AS [Avg-NT], Sum(ОРГРЭС98.Q) AS [Sum-Q], Sum(ОРГРЭС98.QOTR) AS [Sum-QOTR]
FROM ОРГРЭС98
GROUP BY ОРГРЭС98.NUMB;
