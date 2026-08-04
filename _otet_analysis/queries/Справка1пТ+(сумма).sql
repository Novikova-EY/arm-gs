SELECT "Всего" AS name, Null AS numb1, Null AS numb1120, [Справка1пТ+].h, Null AS obl, Null AS oes, Null AS oblname, Null AS oesname, Sum([Справка1пТ+].f1) AS f1, Sum([Справка1пТ+].f2) AS f2, Sum([Справка1пТ+].f3) AS f3, Sum([Справка1пТ+].f4) AS f4, Sum([Справка1пТ+].f5) AS f5, Sum([Справка1пТ+].f6) AS f6, Sum([Справка1пТ+].f7) AS f7, Sum([Справка1пТ+].f8) AS f8, Sum([Справка1пТ+].f9) AS f9, Sum([Справка1пТ+].f10) AS f10
FROM [Справка1пТ+]
GROUP BY [Справка1пТ+].h;
