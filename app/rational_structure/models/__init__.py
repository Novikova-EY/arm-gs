from .equipment_technical_characteristic_model import EquipmentTechnicalCharacteristic
from .calculation_workbook_model import CalculationWorkbook
from .technical_inspection_code_model import TechnicalInspectionCode
from .territory_technology_model import TerritoryTechnology, TerritoryTransferSection
from .territory_input_model import TerritoryInput
from .territory_discount_rate_model import TerritoryDiscountRate

# Старое имя используется сервисами импорта и страницами турбин.
TurbineTechnicalCharacteristic = EquipmentTechnicalCharacteristic

__all__ = [
    "CalculationWorkbook",
    "EquipmentTechnicalCharacteristic",
    "TechnicalInspectionCode",
    "TerritoryTechnology",
    "TerritoryTransferSection",
    "TerritoryInput",
    "TerritoryDiscountRate",
    "TurbineTechnicalCharacteristic",
]
