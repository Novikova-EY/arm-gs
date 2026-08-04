SELECT NUMB1120, AVG(IIF(gaz_c IS NOT NULL OR gaz_c > 0, gaz_c, NULL)) AS avg_gaz_c, SUM(IIF(DON_c > 0, DON_c, 0)
        + IIF(PODM_c > 0, PODM_c, 0)

        + IIF(vork_c > 0, vork_c, 0)
        + IIF(intin_c > 0, intin_c, 0)
       
        + IIF(kuzngd_c > 0, kuzngd_c, 0)
        + IIF(kuznt_c > 0, kuznt_c, 0)
        + IIF(kuznss_c > 0, kuznss_c, 0)
        + IIF(kuznun_c > 0, kuznun_c, 0)
        + IIF(URAL_c > 0, URAL_c, 0)
        + IIF(sver_c > 0, sver_c, 0)
        + IIF(chel_c > 0, chel_c, 0)
        + IIF(kizel_c > 0, kizel_c, 0)
        + IIF(BASHK_c > 0, BASHK_c, 0)
  
        + IIF(ekib_c > 0, ekib_c, 0)
        + IIF(maikub_c > 0, maikub_c, 0)

        + IIF(nazar_c > 0, nazar_c, 0)
        + IIF(ibor_c > 0, ibor_c, 0)
        + IIF(berez_c > 0, berez_c, 0)
        + IIF(per_c > 0, per_c, 0)
        + IIF(irbei_c > 0, irbei_c, 0)
        + IIF(kansk_c > 0, kansk_c, 0)

        + IIF(azey_c > 0, azey_c, 0)
        + IIF(mug_c > 0, mug_c, 0)
        + IIF(cher_c > 0, cher_c, 0)

        + IIF(jer_c > 0, jer_c, 0)
        + IIF(karab_c > 0, karab_c, 0)
        + IIF(HAK_c > 0, HAK_c, 0)
        + IIF(TUV_c > 0, TUV_c, 0)

        + IIF(gusin_c > 0, gusin_c, 0)
        + IIF(tugn_c > 0, tugn_c, 0)
        + IIF(okino_c > 0, okino_c, 0)

        + IIF(har_c > 0, har_c, 0)
        + IIF(urt_c > 0, urt_c, 0)
        + IIF(tataur_c > 0, tataur_c, 0)
        + IIF(tarbag_c > 0, tarbag_c, 0)
        + IIF(zab_kam_c > 0, zab_kam_c, 0)

        + IIF(rai_c > 0, rai_c, 0)
        + IIF(erk_c > 0, erk_c, 0)
        + IIF(URG_c > 0, URG_c, 0)
        + IIF(USHUM_c > 0, USHUM_c, 0)

        + IIF(bikin_c > 0, bikin_c, 0)
        + IIF(razdol_c > 0, razdol_c, 0)
        + IIF(hankai_c > 0, hankai_c, 0)

        + IIF(neru_c > 0, neru_c, 0)
        + IIF(zyryan_c > 0, zyryan_c, 0)
        + IIF(pyak_c > 0, pyak_c, 0)
        + IIF(MAG_c > 0, MAG_c, 0)

        + IIF(anad_c > 0, anad_c, 0)
        + IIF(bering_c > 0, bering_c, 0)
        + IIF(KAMCH_c > 0, KAMCH_c, 0)
        + IIF(SAH_c > 0, SAH_c, 0)) AS сумма_строки, SUM(
        IIF(DON_c > 0, 1, 0) +
        IIF(PODM_c > 0, 1, 0) +

        IIF(vork_c > 0, 1, 0) +
        IIF(intin_c > 0, 1, 0) +

        IIF(kuzngd_c > 0, 1, 0) +
        IIF(kuznt_c > 0, 1, 0) +
        IIF(kuznss_c > 0, 1, 0) +
        IIF(kuznun_c > 0, 1, 0) +

        IIF(sver_c > 0, 1, 0) +
        IIF(chel_c > 0, 1, 0) +
        IIF(kizel_c > 0, 1, 0) +
        IIF(BASHK_c > 0, 1, 0) +

        IIF(ekib_c > 0, 1, 0) +
        IIF(maikub_c > 0, 1, 0) +

        IIF(nazar_c > 0, 1, 0) +
        IIF(ibor_c > 0, 1, 0) +
        IIF(berez_c > 0, 1, 0) +
        IIF(per_c > 0, 1, 0) +
        IIF(irbei_c > 0, 1, 0) +
        IIF(kansk_c > 0, 1, 0) +

        IIF(azey_c > 0, 1, 0) +
        IIF(mug_c > 0, 1, 0) +
        IIF(cher_c > 0, 1, 0) +

        IIF(jer_c > 0, 1, 0) +
        IIF(karab_c > 0, 1, 0) +
        IIF(HAK_c > 0, 1, 0) +
        IIF(TUV_c > 0, 1, 0) +

        IIF(gusin_c > 0, 1, 0) +
        IIF(tugn_c > 0, 1, 0) +
        IIF(okino_c > 0, 1, 0) +

        IIF(har_c > 0, 1, 0) +
        IIF(urt_c > 0, 1, 0) +
        IIF(tataur_c > 0, 1, 0) +
        IIF(tarbag_c > 0, 1, 0) +
        IIF(zab_kam_c > 0, 1, 0) +

        IIF(rai_c > 0, 1, 0) +
        IIF(erk_c > 0, 1, 0) +
        IIF(URG_c > 0, 1, 0) +
        IIF(USHUM_c > 0, 1, 0) +

        IIF(bikin_c > 0, 1, 0) +
        IIF(razdol_c > 0, 1, 0) +
        IIF(hankai_c > 0, 1, 0) +

        IIF(neru_c > 0, 1, 0) +
        IIF(zyryan_c > 0, 1, 0) +
        IIF(pyak_c > 0, 1, 0) +
        IIF(MAG_c > 0, 1, 0) +

        IIF(anad_c > 0, 1, 0) +
        IIF(bering_c > 0, 1, 0) +
        IIF(KAMCH_c > 0, 1, 0) +
        IIF(SAH_c > 0, 1, 0)
    ) AS количество_непустых_ячеек, IIF( [количество_непустых_ячеек]> 0, [сумма_строки] / [количество_непустых_ячеек], 0) AS avg_ugol
FROM Цена2023
GROUP BY NUMB1120;
