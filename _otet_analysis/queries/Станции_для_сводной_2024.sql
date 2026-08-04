SELECT Имена_станций.NAME, Имена_ОЭС.abbr AS oesname, Имена_областей.NAME AS oblname, Имена_станций.ordnumb, Станции2024.Year, Станции2024.NUST, Станции2024.nr, Станции2024.E, Станции2024.EOTP, Станции2024.EURT, Станции2024.EUST, Станции2024.Q, Станции2024.TURT, Станции2024.TUST, Станции2024.B, Станции2024.GAZ, Доп_угли2024.gaz_prir, Доп_угли2024.gazpp, Станции2024.MAZUT, Доп_угли2024.maztop, Доп_угли2024.gtt, Доп_угли2024.nft_proch, Доп_угли2024.disel, Станции2024.TORF, Станции2024.SLAN, Станции2024.ISK_GAZ, Доп_угли2024.domen_g, Доп_угли2024.koks_g, Доп_угли2024.prochgaz, Станции2024.PROCH, Доп_угли2024.tvproch, Доп_угли2024.szh_gaz, Доп_угли2024.inoe, Станции2024.UGOL, Станции2024.DON, Станции2024.PODM, Станции2024.PECH, Доп_угли2024.intin, Доп_угли2024.vork, Станции2024.ARKT, Станции2024.KUZN, Доп_угли2024.kuzngd, Доп_угли2024.kuznt, Доп_угли2024.kuznss, Доп_угли2024.kuznun, Станции2024.URAL, Доп_угли2024.sver, Доп_угли2024.chel, Доп_угли2024.kizel, Станции2024.BASHK, Станции2024.KAN, Доп_угли2024.nazar, Доп_угли2024.ibor, Доп_угли2024.berez, Доп_угли2024.per, Доп_угли2024.irbei, Доп_угли2024.kansk, Станции2024.TUNG, Доп_угли2024.jer, Доп_угли2024.karab, Станции2024.IRKUT, Доп_угли2024.azey, Доп_угли2024.mug, Доп_угли2024.cher, Станции2024.HAK, Станции2024.TUV, Станции2024.BUR, Доп_угли2024.gusin, Доп_угли2024.tugn, Доп_угли2024.okino, Станции2024.CHIT, Доп_угли2024.har, Доп_угли2024.urt, Доп_угли2024.tataur, Доп_угли2024.tarbag, Доп_угли2024.zab_kam, Станции2024.YAKUT, Доп_угли2024.neru, Доп_угли2024.zyryan, Доп_угли2024.pyak, Станции2024.AMUR, Доп_угли2024.rai, Доп_угли2024.erk, Доп_угли2024.ogodj, Станции2024.URG, Станции2024.USHUM, Станции2024.PRIM, Доп_угли2024.bikin, Доп_угли2024.razdol, Доп_угли2024.hankai, Станции2024.MAG, Станции2024.SAH, Станции2024.KAMCH, Станции2024.CHUKOT, Доп_угли2024.anad, Доп_угли2024.bering, Станции2024.KAZAH, Доп_угли2024.ekib, Доп_угли2024.maikub, Доп_угли2024.karag, Доп_угли2024.karajyra, Доп_угли2024.teniz, IIf(IsNull([DON]),0,[DON]) + IIf(IsNull([HAK]),0,[HAK]) +
IIf(IsNull([TUV]),0,[TUV]) +
         IIf(IsNull([URG]),0,[URG]) + IIf(IsNull([MAG]),0,[MAG]) +
IIf(IsNull([KAMCH]),0,[KAMCH]) +
         IIf(IsNull([tugn]),0,[tugn]) + IIf(IsNull([cher]),0,[cher]) +
IIf(IsNull([jer]),0,[jer]) +
         IIf(IsNull([karab]),0,[karab]) + IIf(IsNull([vork]),0,[vork]) +
IIf(IsNull([intin]),0,[intin]) +
         IIf(IsNull([kizel]),0,[kizel]) + IIf(IsNull([zab_kam]),0,[zab_kam]) 
+ IIf(IsNull([ogodj]),0,[ogodj]) +
         IIf(IsNull([razdol]),0,[razdol]) + IIf(IsNull([neru]),0,[neru]) +
IIf(IsNull([zyryan]),0,[zyryan]) +
         IIf(IsNull([pyak]),0,[pyak]) + IIf(IsNull([kuzngd]),0,[kuzngd]) +
IIf(IsNull([kuznt]),0,[kuznt]) +
         IIf(IsNull([kuznss]),0,[kuznss]) + IIf(IsNull([kuznun]),0,[kuznun]) 
+ IIf(IsNull([bering]),0,[bering]) +
         IIf(IsNull([ekib]),0,[ekib]) + IIf(IsNull([karag]),0,[karag]) +
IIf(IsNull([karajyra]),0,[karajyra]) AS Kamennie, IIf(IsNull([PODM]),0,[PODM]) + IIf(IsNull([BASHK]),0,[BASHK]) +
IIf(IsNull([USHUM]),0,[USHUM]) +
         IIf(IsNull([SAH]),0,[SAH]) + IIf(IsNull([nazar]),0,[nazar]) +
IIf(IsNull([ibor]),0,[ibor]) +
         IIf(IsNull([berez]),0,[berez]) + IIf(IsNull([per]),0,[per]) +
IIf(IsNull([irbei]),0,[irbei]) +
         IIf(IsNull([kansk]),0,[kansk]) + IIf(IsNull([gusin]),0,[gusin]) +
IIf(IsNull([okino]),0,[okino]) +
         IIf(IsNull([azey]),0,[azey]) + IIf(IsNull([mug]),0,[mug]) +
IIf(IsNull([sver]),0,[sver]) +
         IIf(IsNull([chel]),0,[chel]) + IIf(IsNull([har]),0,[har]) +
IIf(IsNull([urt]),0,[urt]) +
         IIf(IsNull([tataur]),0,[tataur]) + IIf(IsNull([tarbag]),0,[tarbag]) 
+ IIf(IsNull([rai]),0,[rai]) +
         IIf(IsNull([erk]),0,[erk]) + IIf(IsNull([svo]),0,[svo]) +
IIf(IsNull([bikin]),0,[bikin]) +
         IIf(IsNull([hankai]),0,[hankai]) + IIf(IsNull([anad]),0,[anad]) +
IIf(IsNull([maikub]),0,[maikub]) +
         IIf(IsNull([teniz]),0,[teniz]) AS Burie, Станции2024.QOTR, Станции2024.SNK, Станции2024.EWTP, Станции2024.NT, Станции2024.OBOR, Станции2024.VED, Станции2024.OBL, Станции2024.DEP, Станции2024.OES, Станции2024.ER, Станции2024.NUMB1120, Имена_станций.Ведомство AS вед, IIf([вед]=1 Or [вед]=4,1,IIf([вед]=2 Or
[вед]=3,2,0)) AS кэстэц, Имена_станций.D, Имена_станций.R, IIf([ved]>0,0,1) AS sost, IIf([main]>0,1,0) AS [group], Имена_станций.FO, Имена_станций.форэм, Имена_станций.GK, Имена_станций.BE, имена_ГК.name AS namegk, [Филиалы ГК].name AS filial, IIf([OBOR]=20 Or
[OBOR]=90,"ГТУ",IIf([OBOR]=21 Or
[OBOR]=91,"ПГУ",IIf([OBOR]=22,"Диз",IIf([OBOR]=23,"ГУБТ",IIf([OBOR]=24 Or
[OBOR]=89,"ГПА","ПСУ"))))) AS тип, Станции2024.SNt, Имена_станций.n1 AS [мощность блока], IIf([B]>0,[gaz_prir]/[B]*100,0) AS dolya_gaz_prir, IIf([B]>0,[gazpp]/[B]*100,0) AS dolya_gazpp, IIf([B]>0,[UGOL]/[B]*100,0) AS dolya_ugol, IIf([B]>0,[MAZUT]/[B]*100,0) AS dolya_mazut, IIf([B]>0,[TORF]/[B]*100,0) AS dolya_torf, IIf([B]>0,[SLAN]/[B]*100,0) AS dolya_slan, IIf([B]>0,[PROCH]/[B]*100,0) AS dolya_proch, IIf([E]>0,[EWTP]/[E]*100,0) AS dolya_ewtp, IIf([Q]>0,[QOTR]/[Q]*100,0) AS dolya_qotr, IIf([B]>0 And
[domen_g]>0,[domen_g]/[B]*100,0) AS dolya_domen_g, IIf([B]>0 And
[koks_g]>0,[koks_g]/[B]*100,0) AS dolya_koks_g, IIf([B]>0 And
[prochgaz]>0,[prochgaz]/[B]*100,0) AS dolya_prochgaz, IIf([B]>0,IIf([dolya_gaz_prir]>=50,"gaz_prir",IIf([dolya_gazpp]>=50,"gazpp",IIf([dolya_domen_g]>=50,"domen_g",IIf([dolya_koks_g]>=50,"koks_g",IIf([dolya_prochgaz]>=50,"prochgaz",IIf([dolya_ugol]>=50,"ugol",IIf([dolya_mazut]>=50,"neftetopl","prochee"))))))),"net
topliva") AS nov_Belyaev, [EUST]/[B] AS [dolya topl na ee], [TUST]/[B] AS [dolya topl na q], Имена_областей.Terr_Belyaev, IIf([E]>0,([E]-[EOTP])/[E]*100,0) AS [%_sn], IIf([Имена_станций.BE]=9,"Пром.предпр.","Минэнерго") AS BLST_BE, IIf([Ведомство]=1,"Минэнерго","Пром.предпр.") AS BLST_V, IIf([вед]=1,"Минэнерго","Пром.предпр.") AS BLST_ved, Типы_оборудования.gruppa_oborud
FROM (((Имена_станций INNER JOIN (Имена_областей RIGHT JOIN (Имена_ОЭС INNER JOIN (Станции2024 LEFT JOIN Доп_угли2024 ON (Станции2024.YEAR =
Доп_угли2024.YEAR) AND (Станции2024.NUMB1120 = Доп_угли2024.NUMB1120)) ON Имена_ОЭС.oes = Станции2024.OES) ON Имена_областей.OBL = Станции2024.OBL) ON Имена_станций.NUMB = Станции2024.NUMB1120) LEFT JOIN имена_ГК ON Имена_станций.GK = имена_ГК.code) LEFT JOIN [Филиалы ГК] ON Имена_станций.GKF = [Филиалы ГК].code) INNER JOIN Типы_оборудования ON Станции2024.OBOR = Типы_оборудования.code;
