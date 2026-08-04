UPDATE Имена_станций INNER JOIN Турбины ON Имена_станций.NUMB=Турбины.grcode SET Турбины.numb = Имена_станций!ordnumb;
