# -*- coding: utf-8 -*-
"""
Маршруты страницы «Расчёт» (/fuel/calculation): этапы после «Коэфф».

- distribution_stage_routes — «Распред»
- fuel_stage_routes — «Топливо»

Сервисы по вкладкам: app.fuel.services.calculation.{coefficient|distribution|fuel}

Регистрация на fuel_bp — при импорте из app.fuel.routes.

- fuel_calculation_edit_data_routes — «Редактировать основные данные» (/fuel/calculation/equipment_group_fuel_params_edit_data),
  «Редактировать удельные показатели» (/fuel/calculation/equipment_group_specific_fuel_consumption_edit_data)
"""
