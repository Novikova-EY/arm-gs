SELECT Станции2013.NAME, Натура99.YEAR, Станции2013.UGOL, Натура99.NUMB1120
FROM Натура99 INNER JOIN Станции2013 ON Натура99.NUMB1120=Станции2013.NUMB1120
WHERE (((Натура99.YEAR)=2013) AND ((Станции2013.UGOL)=0 Or (Станции2013.UGOL) Is Null));
