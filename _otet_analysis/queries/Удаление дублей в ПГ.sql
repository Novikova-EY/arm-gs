DELETE *
FROM [Выбросы ПГ]
WHERE EXISTS (
    SELECT 1 FROM [Восстановление ПГ]
    WHERE [Выбросы ПГ].[NUMB1120] = [Восстановление ПГ].[NUMB1120]
    AND [Выбросы ПГ].[Year] = [Восстановление ПГ].[Year]
);
