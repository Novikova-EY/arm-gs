SELECT перетоки_табл.oes, Max(перетоки_табл.id) AS [Max-id]
FROM перетоки_табл
GROUP BY перетоки_табл.oes;
