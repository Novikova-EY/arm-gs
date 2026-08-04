SELECT DISTINCTROW Станции99.NAME AS Выражение1, Станции99.UGOL AS Выражение2, U([DON],[PODM],[PECH],[ARKT],[KUZN],[URAL],[BASHK],[EKIB],[KARAG],[KAN],[HAK],[TUV],[IRKUT],[BUR],[CHIT],[HER],[RAICH],[URG],[LUCH],[MAG],[SAH]) AS в_том_числе
FROM Станции99
WHERE (((Станции99.UGOL)>0))
ORDER BY Станции99.NUMB1;
