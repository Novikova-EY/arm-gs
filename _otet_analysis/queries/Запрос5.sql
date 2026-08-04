SELECT Sum(Станции2005.NUST) AS [Sum-NUST], Sum(Станции2005.EUST) AS [Sum-EUST], Sum(Станции2005.EOTP) AS [Sum-EOTP]
FROM Станции2005
WHERE (((Станции2005.VED)=2 Or (Станции2005.VED)=3) AND ((Abs(z([gaz])+z([mazut])-z([b])))<1));
