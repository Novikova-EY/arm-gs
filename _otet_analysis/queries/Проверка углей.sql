SELECT Имена_областей.NAME AS obl, Станции2024.NAME, Станции2024.UGOL, [Станции2024].[UGOL]-[don]-[podm]-[pech]-[ARKT]-[kuzn]-[ural]-[bashk]-[KAZAH]-[KAN]-[tung]-[IRKUT]-[hak]-[tuv]-[BUR]-[chit]-[YAKUT]-[AMUR]-[prim]-[urg]-[mag]-[sah]-[kamch]-[CHUKOT]-[ushum] AS d
FROM Имена_областей INNER JOIN Станции2024 ON Имена_областей.OBL = Станции2024.OBL
WHERE (((Станции2024.UGOL)>0));
