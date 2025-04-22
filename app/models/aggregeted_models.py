from app import db

class AggregatedPower(db.Model):
    __tablename__ = "aggregated_power"

    id = db.Column(db.Integer, primary_key=True)

    year = db.Column(db.Integer, nullable=False)
    power_type = db.Column(db.String(10), nullable=False)  # 'p_ust', 'p_ogr', 'p_rasp'

    # Уровень иерархии
    id_energy_unit = db.Column(db.Integer, db.ForeignKey("energy_unit.id"))
    id_regional_district = db.Column(db.Integer, db.ForeignKey("regional_district.id"))
    id_regional_energy_system = db.Column(db.Integer, db.ForeignKey("regional_energy_system.id"))
    id_union_energy_system = db.Column(db.Integer, db.ForeignKey("union_energy_system.id"))
    id_energy_system_type = db.Column(db.Integer, db.ForeignKey("energy_system_type.id"))
    id_energy_area = db.Column(db.Integer, db.ForeignKey("energy_area.id"))  # новая энергозона

    # Разрезы
    id_station_type = db.Column(db.Integer, db.ForeignKey("station_type.id"))
    id_machine_type = db.Column(db.Integer, db.ForeignKey("machine_type.id"))
    id_tes_type = db.Column(db.Integer, db.ForeignKey("tes_type.id"))
    id_fuel_type = db.Column(db.Integer, db.ForeignKey("fuel_type.id"))

    # Значение мощности
    value = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    __table_args__ = (
        db.Index(
            "ix_aggregated_power_all",
            "year", "power_type",
            "id_energy_unit", "id_regional_district", "id_regional_energy_system", 
            "id_union_energy_system", "id_energy_system_type", "id_energy_area",
            "id_station_type", "id_machine_type", "id_tes_type", "id_fuel_type"
        ),
    )


