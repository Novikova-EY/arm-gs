SELECT Все_Затраты.NUMB1120, Все_Затраты.Year, Все_Затраты.ZATRATY_SUM, Все_Затраты.Zatr_E, Все_Затраты.Zatr_P, Все_Затраты.Zatr_Q
FROM Все_Затраты LEFT JOIN Имена_затраты ON Все_Затраты.code_zatr = Имена_затраты.code_zatr
WHERE (((Все_Затраты.code_zatr) In (110)));
