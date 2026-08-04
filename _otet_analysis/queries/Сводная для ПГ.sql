SELECT [Филиалы ГК].code, [Филиалы ГК].name, [Выбросы ПГ].name_st, [Выбросы ПГ].year, *
FROM ([Выбросы ПГ] INNER JOIN Имена_станций ON [Выбросы ПГ].numb1120 = Имена_станций.NUMB) INNER JOIN [Филиалы ГК] ON Имена_станций.GKF = [Филиалы ГК].code;
