UPDATE Станции2014 INNER JOIN (Станции2013 INNER JOIN Имена_станций ON Станции2013.NUMB1120=Имена_станций.NUMB) ON Станции2014.NUMB1120=Имена_станций.NUMB SET Станции2014.numb1 = Имена_станций!ordnumb
WHERE (((Станции2014.OBL)=18));
