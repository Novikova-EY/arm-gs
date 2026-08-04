SELECT Имена_областей.NAME AS obl, Станции2024.NAME, Станции2024.B, Nz([EUST],0)+Nz([TUST],0) AS summ, [B]-[summ] AS d
FROM Имена_областей INNER JOIN Станции2024 ON Имена_областей.OBL = Станции2024.OBL
WHERE (((Станции2024.B)>0) AND ((Nz([EUST],0)+Nz([TUST],0))=0 Or (Nz([EUST],0)+Nz([TUST],0)) Is Null));
