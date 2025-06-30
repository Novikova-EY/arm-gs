from app.services.aggregation_services.aggregation_generic import aggregate_by_all_generic, JOIN_CHAINS

def aggregate_level_with_total(level_prefix, pagination, rounding_digits, start_year, end_year):
    join_info = JOIN_CHAINS.get(level_prefix)
    if not join_info:
        raise ValueError(f"Не найдена информация о связях JOIN для уровня '{level_prefix}'.")

    return aggregate_by_all_generic(
        pagination=pagination,
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        join_info=join_info,
        level_prefix=level_prefix,
    )

def get_all_aggregations(pagination, rounding_digits, start_year, end_year):
    return {
        f"{level}_data": aggregate_level_with_total(level, pagination, rounding_digits, start_year, end_year)
        for level in JOIN_CHAINS.keys()
    }




