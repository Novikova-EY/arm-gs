SELECT [EWTP по годам].name, [EWTP по годам].numb1, [EWTP по годам].[1990], [EWTP по годам].[2004]
FROM [EWTP по годам]
WHERE ((([EWTP по годам].[1990])>0) AND (([EWTP по годам].[2004]) Is Null));
