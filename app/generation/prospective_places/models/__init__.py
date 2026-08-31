# Prospective places models
from app.generation.prospective_places.models.aes import (
    StationProspectivePlaceAES,
    MachineProspectivePlaceAES,
    ProspectivePlaceTypeAES,
)
from app.generation.prospective_places.models.ges import (
    StationProspectivePlaceGES,
    ProspectivePlaceGesTepSource,
    ProspectivePlaceTypeGES,
)
from app.generation.prospective_places.models.gaes import (
    StationProspectivePlaceGAES,
    ProspectivePlaceGaesTepSource,
    ProspectivePlaceTypeGAES,
)
from app.generation.prospective_places.models.tep_price_conversion_coefficient_model import (
    TepPriceConversionCoefficient,
)
from app.generation.prospective_places.models.prospective_place_hydro_energy_forecast_model import (
    ProspectivePlaceHydroEnergyForecast,
)
