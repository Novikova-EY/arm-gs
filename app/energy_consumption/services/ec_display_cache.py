# -*- coding: utf-8 -*-
"""
Сброс кэшей отображения модуля «Спрос» после любого изменения данных.

У сводок Спроса нет Redis JSON data.json (как у Нагрузок), но есть:
- LRU заряда ГАЭС на сводках;
- request-кэш текстов формул;
- индекс потребления для ЧЧИ/ЭЭ на сводках «Нагрузки» (pd_ec_consumption_index),
  который также инвалидирует pd_summary_page_cache.
"""

from __future__ import annotations


def invalidate_energy_consumption_display_caches(
    *,
    version_id: int | None = None,
) -> None:
    """
    Полный сброс кэшей, влияющих на отображение сводок «Спрос» и связанных
    сегментов «Нагрузки». Вызывать после успешного commit на всех путях записи.
    """
    from app.energy_consumption.services.energy_consumption_summary_services import (
        clear_gaes_charge_summary_cache,
    )
    from app.energy_consumption.services.formula_text.energy_consumption_summary_formula_text_services import (
        clear_formula_text_override_cache,
    )
    from app.power_demand.services.pd_ec_consumption_index_cache import (
        invalidate_pd_ec_consumption_index_cache,
    )

    clear_gaes_charge_summary_cache()
    clear_formula_text_override_cache()
    invalidate_pd_ec_consumption_index_cache(version_id=version_id)
