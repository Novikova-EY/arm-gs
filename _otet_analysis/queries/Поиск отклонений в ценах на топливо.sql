SELECT C.NAME, C.Year, C.GAZ_c, C.MAZUT_c, C.ISK_GAZ_c, C.PROCH_c, NUMB1120
FROM Цена2022 AS C
WHERE (
        C.GAZ_c > 0 AND 
        (
            C.GAZ_c > (
                SELECT Avg(IIf(GAZ_c > 0, GAZ_c, Null)) * 2.5 FROM Цена2022
            ) 
            OR 
            C.GAZ_c < (
                SELECT Avg(IIf(GAZ_c > 0, GAZ_c, Null)) * 0.3 FROM Цена2022
            )
        )
    )
    OR
    (
        C.MAZUT_c > 0 AND 
        (
            C.MAZUT_c > (
                SELECT Avg(IIf(MAZUT_c > 0, MAZUT_c, Null)) * 2.5 FROM Цена2022
            )
            OR 
            C.MAZUT_c < (
                SELECT Avg(IIf(MAZUT_c > 0, MAZUT_c, Null)) * 0.3 FROM Цена2022
            )
        )
    )
    OR
    (
        C.ISK_GAZ_c > 0 AND 
        (
            C.ISK_GAZ_c > (
                SELECT Avg(IIf(ISK_GAZ_c > 0, ISK_GAZ_c, Null)) * 2 FROM Цена2022
            )
            OR 
            C.ISK_GAZ_c < (
                SELECT Avg(IIf(ISK_GAZ_c > 0, ISK_GAZ_c, Null)) * 0.3 FROM Цена2022
            )
        )
    )
    OR
    (
        C.PROCH_c > 0 AND 
        (
            C.PROCH_c > (
                SELECT Avg(IIf(PROCH_c > 0, PROCH_c, Null)) * 2 FROM Цена2022
            )
            OR 
            C.PROCH_c < (
                SELECT Avg(IIf(PROCH_c > 0, PROCH_c, Null)) * 0.3 FROM Цена2022
            )
        )
    );
