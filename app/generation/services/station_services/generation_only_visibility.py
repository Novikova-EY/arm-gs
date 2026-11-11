"""Generation-only stations are opt-in, including their directly owned records."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

from sqlalchemy import event, or_, select
from flask_sqlalchemy.session import Session
from sqlalchemy.orm import with_loader_criteria

from app.extensions import db

_generation_only_visible = ContextVar("generation_only_visible", default=False)
_generation_only_station_id = ContextVar("generation_only_station_id", default=None)


def generation_only_visible():
    return _generation_only_visible.get()


def generation_visibility_cache_key():
    return generation_only_visible(), _generation_only_station_id.get()


@contextmanager
def include_generation_only(station_id=None):
    token = _generation_only_visible.set(station_id is None)
    station_token = _generation_only_station_id.set(station_id)
    try:
        yield
    finally:
        _generation_only_station_id.reset(station_token)
        _generation_only_visible.reset(token)


def generation_page_data(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with include_generation_only():
            return function(*args, **kwargs)
    return wrapped


def generation_station_card(function):
    @wraps(function)
    def wrapped(station_id, *args, **kwargs):
        with include_generation_only(station_id=station_id):
            return function(station_id, *args, **kwargs)
    return wrapped


@event.listens_for(Session, "do_orm_execute")
def exclude_generation_only(execute_state):
    if not execute_state.is_select or generation_only_visible():
        return
    from app.generation.models.station.station_model import Station

    station_id = _generation_only_station_id.get()
    station_criterion = Station.is_generation_only.is_(False)
    if station_id is not None:
        station_criterion = or_(station_criterion, Station.id == station_id)
    statement = execute_state.statement.options(
        with_loader_criteria(Station, station_criterion, include_aliases=True)
    )
    # Use a Core subquery: ORM criteria must not hide its excluded IDs.
    stations = Station.__table__
    hidden_ids = select(stations.c.id).where(stations.c.is_generation_only.is_(True))
    if station_id is not None:
        hidden_ids = hidden_ids.where(stations.c.id != station_id)
    from app.generation.models.machine.machine_model import Machine
    from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine

    machines = Machine.__table__
    pgu_machines = PGUMachine.__table__
    hidden_machine_ids = select(machines.c.id).where(machines.c.id_station.in_(hidden_ids))
    hidden_pgu_ids = select(pgu_machines.c.id).where(
        pgu_machines.c.id_parent_machine.in_(hidden_machine_ids)
    )
    hidden_owner_ids = {
        stations.c.id: hidden_ids,
        machines.c.id: hidden_machine_ids,
        pgu_machines.c.id: hidden_pgu_ids,
    }
    for mapper in db.Model.registry.mappers:
        if mapper.class_ is Station:
            continue
        for column in mapper.columns:
            for fk in column.foreign_keys:
                blocked_ids = hidden_owner_ids.get(fk.column)
                if blocked_ids is not None:
                    # ORM annotations let joinedload adapt this expression to its table alias.
                    attribute = getattr(mapper.class_, mapper.get_property_by_column(column).key)
                    statement = statement.options(with_loader_criteria(
                        mapper.class_, or_(attribute.is_(None), attribute.not_in(blocked_ids)),
                        include_aliases=True,
                    ))
    execute_state.statement = statement
