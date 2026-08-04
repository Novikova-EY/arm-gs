SELECT Имена_станций.NAME, Сообщения.stnumb AS Выражение1, Сообщения.msgtxt AS Выражение2, Сообщения.numb1120 AS Выражение3
FROM Сообщения, Имена_станций
WHERE (((InStr([msgtxt],"замена"))="0") AND ((InStr([msgtxt],"год"))="0"))
ORDER BY Имена_станций.ordnumb;
