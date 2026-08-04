UPDATE [Доп_угли(архив)] AS DOP INNER JOIN [Станции(архив)] AS STAN ON (DOP.YEAR = STAN.YEAR) AND (DOP.NUMB1120 = STAN.NUMB1120) SET DOP.gaz_prir = IIf([STAN]![GAZ]>0,IIf([DOP]![gazpp]>0,[STAN]![GAZ]-[DOP]![gazpp],[STAN]![GAZ]),0)
WHERE ((([DOP]![YEAR])=2017));
