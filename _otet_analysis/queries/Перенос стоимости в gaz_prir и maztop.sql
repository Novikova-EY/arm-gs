UPDATE Стоимость2021 SET Стоимость2021.gaz_prir = IIf([gazpp]>0,[GAZ]-[gazpp],[GAZ]), Стоимость2021.maztop = [Стоимость2021]![MAZUT];
