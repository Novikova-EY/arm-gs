UPDATE Списки_агрегатов SET Списки_агрегатов.name = repstring([name],"T","Т")
WHERE (((InStr([name],"T"))>0));
