SELECT Натура99.YEAR, Имена_станций.NAME, [nazar]*7000 AS [nazar-koef], [kansk]*7000 AS kan_koef, [gusin]*7000 AS gus_koeff, [tugn]*7000 AS tugn_koef, [urt]*7000 AS urt_koef, [zyryan]*7000 AS zyr_koef, [rai]*7000 AS rai_koeff, [erk]*7000 AS erk_koef, [ogodj]*7000 AS ogodj_koef, [ekib]*7000 AS ekib_koef, [maikub]*7000 AS maikub_koef, [karag]*7000 AS karag_koef, [karajyra]*7000 AS karajyra_koef, [teniz]*7000 AS teniz_koef, *
FROM Имена_станций INNER JOIN Натура99 ON Имена_станций.NUMB = Натура99.NUMB1120
WHERE (((Натура99.YEAR)>2016) AND (([teniz]*7000)>0));
