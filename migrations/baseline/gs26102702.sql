-- Schema snapshot of gs_gen at gs26102702 (2026-10-29, PostgreSQL 15).
-- Astra MAC policies and external FDW connections are managed by the administrator.
-- Alembic owns its version table. No application rows are included.
SET LOCAL standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', true);
SET LOCAL check_function_bodies = false;


CREATE SCHEMA IF NOT EXISTS gs_auth;

COMMENT ON SCHEMA gs_auth IS 'Пользователи, роли и связи авторизации приложения';

CREATE SCHEMA IF NOT EXISTS gs_bem;

COMMENT ON SCHEMA gs_bem IS 'Баланс электроэнергии: выработка и перетоки по станциям, РЭС и ЭСПП';

CREATE SCHEMA IF NOT EXISTS gs_ec;

COMMENT ON SCHEMA gs_ec IS 'Потребление электрической энергии по территориям и объектам энергосистемы';

CREATE SCHEMA IF NOT EXISTS gs_eco;

CREATE SCHEMA IF NOT EXISTS gs_ei;

COMMENT ON SCHEMA gs_ei IS 'Электроемкость и долгосрочные показатели спроса по ВЭД, РФ и ФО';

CREATE SCHEMA IF NOT EXISTS gs_ekp;

COMMENT ON SCHEMA gs_ekp IS 'Экономические показатели: ВЭД, население, выпуск продукции, инвестиции и доходы';

CREATE SCHEMA IF NOT EXISTS gs_fue;

COMMENT ON SCHEMA gs_fue IS 'Топливный модуль: группы оборудования, параметры топлива, ограничения, цены, стоимости и коэффициенты';

CREATE SCHEMA IF NOT EXISTS gs_fue_em;

COMMENT ON SCHEMA gs_fue_em IS 'Внешние маппинги справочников топливного модуля';

CREATE SCHEMA IF NOT EXISTS gs_gen;

COMMENT ON SCHEMA gs_gen IS 'Генерация: станции, агрегаты, мощности, выработка, документы и перспективные площадки';

CREATE SCHEMA IF NOT EXISTS gs_logs;

COMMENT ON SCHEMA gs_logs IS 'Журнал аудита действий пользователей и изменений сущностей';

CREATE SCHEMA IF NOT EXISTS gs_pd;

COMMENT ON SCHEMA gs_pd IS 'Параметры нагрузки и максимумов потребления мощности';

CREATE SCHEMA IF NOT EXISTS gs_rs;

CREATE SCHEMA IF NOT EXISTS gs_sys;

COMMENT ON SCHEMA gs_sys IS 'Системные и общие справочники, версии БД, годы, территории, энергосистемы, топлива и ВЭД';

CREATE SCHEMA IF NOT EXISTS gs_ter;

COMMENT ON SCHEMA gs_ter IS 'Территориальные данные и показатели перетоков энергоузлов';



CREATE TYPE gs_sys.technology_type_enum AS ENUM (
    'открытая',
    'закрытая',
    'перспективная'
);

CREATE TABLE gs_auth.roles (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    name_full character varying(50) NOT NULL,
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_auth.roles IS 'Роли пользователей системы';

COMMENT ON COLUMN gs_auth.roles.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_auth.roles.name IS 'Системное имя роли пользователя';

COMMENT ON COLUMN gs_auth.roles.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_auth.roles.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_auth.roles.name_full IS 'Полное наименование роли пользователя';

COMMENT ON COLUMN gs_auth.roles.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_auth.roles.modified_by IS 'Пользователь, последним изменивший запись';

CREATE SEQUENCE gs_auth.roles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_auth.roles_id_seq OWNED BY gs_auth.roles.id;

CREATE TABLE gs_auth.user_roles (
    user_id integer NOT NULL,
    role_id integer NOT NULL
);

COMMENT ON TABLE gs_auth.user_roles IS 'Служебная таблица связи пользователей и ролей many-to-many';

COMMENT ON COLUMN gs_auth.user_roles.user_id IS 'Пользователь в связи many-to-many с ролью';

COMMENT ON COLUMN gs_auth.user_roles.role_id IS 'Роль в связи many-to-many с пользователем';

CREATE TABLE gs_auth.users (
    id integer NOT NULL,
    username character varying(150) NOT NULL,
    email character varying(150) NOT NULL,
    password_hash character varying(256) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    last_database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_auth.users IS 'Пользователи системы';

COMMENT ON COLUMN gs_auth.users.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_auth.users.username IS 'Имя пользователя системы';

COMMENT ON COLUMN gs_auth.users.email IS 'Email пользователя системы';

COMMENT ON COLUMN gs_auth.users.password_hash IS 'Хэш пароля пользователя';

COMMENT ON COLUMN gs_auth.users.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_auth.users.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_auth.users.last_database_version_id IS 'Последняя выбранная пользователем версия базы данных';

COMMENT ON COLUMN gs_auth.users.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_auth.users.modified_by IS 'Пользователь, последним изменивший запись';

CREATE SEQUENCE gs_auth.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_auth.users_id_seq OWNED BY gs_auth.users.id;

CREATE TABLE gs_bem.gs_bem_balance_row_notes (
    id integer NOT NULL,
    sheet_slug character varying(128) NOT NULL,
    balance_kind character varying(16) NOT NULL,
    row_key character varying(256) NOT NULL,
    note_text text DEFAULT ''::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255)
);

CREATE SEQUENCE gs_bem.gs_bem_balance_row_notes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_bem.gs_bem_balance_row_notes_id_seq OWNED BY gs_bem.gs_bem_balance_row_notes.id;

CREATE TABLE gs_bem.gs_bem_ee_balance_custom_flow_rows (
    id integer NOT NULL,
    sheet_slug character varying(128) NOT NULL,
    direction character varying(16) NOT NULL,
    parent_key character varying(128),
    label character varying(500) DEFAULT ''::character varying NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

CREATE SEQUENCE gs_bem.gs_bem_ee_balance_custom_flow_rows_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_bem.gs_bem_ee_balance_custom_flow_rows_id_seq OWNED BY gs_bem.gs_bem_ee_balance_custom_flow_rows.id;

CREATE TABLE gs_bem.gs_bem_ee_balance_custom_flow_values (
    id integer NOT NULL,
    id_row integer NOT NULL,
    year_number integer NOT NULL,
    value_mln_kvtch numeric(25,16),
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

CREATE SEQUENCE gs_bem.gs_bem_ee_balance_custom_flow_values_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_bem.gs_bem_ee_balance_custom_flow_values_id_seq OWNED BY gs_bem.gs_bem_ee_balance_custom_flow_values.id;

CREATE TABLE gs_bem.gs_bem_ee_balance_manual_generation_values (
    id integer NOT NULL,
    sheet_slug character varying(128) NOT NULL,
    row_key character varying(64) NOT NULL,
    year_number integer NOT NULL,
    value_mln_kvtch numeric(25,16),
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

CREATE SEQUENCE gs_bem.gs_bem_ee_balance_manual_generation_values_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_bem.gs_bem_ee_balance_manual_generation_values_id_seq OWNED BY gs_bem.gs_bem_ee_balance_manual_generation_values.id;

CREATE TABLE gs_bem.gs_bem_ee_balance_station_group_values (
    id integer NOT NULL,
    id_station_group integer NOT NULL,
    page_key character varying(16) NOT NULL,
    year_number integer NOT NULL,
    energy numeric(25,16),
    own_needs numeric(25,16),
    own_needs_percent numeric(25,16),
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_ee_balance_group_page CHECK (((page_key)::text = ANY ((ARRAY['aes'::character varying, 'ges'::character varying, 'ses-ves'::character varying])::text[])))
);

CREATE SEQUENCE gs_bem.gs_bem_ee_balance_station_group_values_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_bem.gs_bem_ee_balance_station_group_values_id_seq OWNED BY gs_bem.gs_bem_ee_balance_station_group_values.id;

CREATE TABLE gs_bem.gs_bem_ee_balance_station_own_needs_coefficients (
    id integer NOT NULL,
    id_station integer NOT NULL,
    station_type_key character varying(8) NOT NULL,
    coefficient numeric(25,16),
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    year_number integer
);

CREATE SEQUENCE gs_bem.gs_bem_ee_balance_station_own_needs_coefficients_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_bem.gs_bem_ee_balance_station_own_needs_coefficients_id_seq OWNED BY gs_bem.gs_bem_ee_balance_station_own_needs_coefficients.id;

CREATE TABLE gs_bem.gs_bem_ee_balance_tes_monthly_values (
    id integer NOT NULL,
    sheet_slug character varying(128) NOT NULL,
    row_key character varying(80) NOT NULL,
    year_number integer NOT NULL,
    month_number integer NOT NULL,
    value_mln_kvtch numeric(25,16),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255)
);

CREATE SEQUENCE gs_bem.gs_bem_ee_balance_tes_monthly_values_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_bem.gs_bem_ee_balance_tes_monthly_values_id_seq OWNED BY gs_bem.gs_bem_ee_balance_tes_monthly_values.id;

CREATE TABLE gs_bem.gs_bem_ee_import_export_oes_values (
    id integer NOT NULL,
    id_union_energy_system integer NOT NULL,
    id_foreign_border_country integer NOT NULL,
    year_number integer NOT NULL,
    transfer_value numeric(25,16),
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

CREATE SEQUENCE gs_bem.gs_bem_ee_import_export_oes_values_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_bem.gs_bem_ee_import_export_oes_values_id_seq OWNED BY gs_bem.gs_bem_ee_import_export_oes_values.id;

CREATE TABLE gs_bem.gs_bem_ee_receive_transfer_oes_values (
    id integer NOT NULL,
    id_source_union_energy_system integer NOT NULL,
    id_target_union_energy_system integer NOT NULL,
    year_number integer NOT NULL,
    transfer_value numeric(25,16),
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

CREATE SEQUENCE gs_bem.gs_bem_ee_receive_transfer_oes_values_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_bem.gs_bem_ee_receive_transfer_oes_values_id_seq OWNED BY gs_bem.gs_bem_ee_receive_transfer_oes_values.id;

CREATE TABLE gs_bem.gs_bem_espp_energy_generations (
    id integer NOT NULL,
    year_number integer,
    month_number integer DEFAULT 0 NOT NULL,
    id_regional_energy_system integer,
    electricity_generation numeric(25,16),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_bem.gs_bem_espp_energy_generations IS 'Сводная выработка электроэнергии по ЭСПП в разрезе РЭС';

COMMENT ON COLUMN gs_bem.gs_bem_espp_energy_generations.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_bem.gs_bem_espp_energy_generations.year_number IS 'Календарный год значения выработки';

COMMENT ON COLUMN gs_bem.gs_bem_espp_energy_generations.month_number IS 'Номер месяца; 0 означает годовое значение';

COMMENT ON COLUMN gs_bem.gs_bem_espp_energy_generations.id_regional_energy_system IS 'Региональная энергосистема ЭСПП';

COMMENT ON COLUMN gs_bem.gs_bem_espp_energy_generations.electricity_generation IS 'Выработка электроэнергии, млн кВт·ч';

COMMENT ON COLUMN gs_bem.gs_bem_espp_energy_generations.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_bem.gs_bem_espp_energy_generations.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_bem.gs_bem_espp_energy_generations.database_version_id IS 'Версия базы данных';

COMMENT ON COLUMN gs_bem.gs_bem_espp_energy_generations.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_bem.gs_bem_espp_energy_generations.modified_by IS 'Пользователь, последним изменивший запись';

CREATE TABLE gs_bem.gs_bem_power_balance_custom_flow_rows (
    id integer NOT NULL,
    sheet_slug character varying(128) NOT NULL,
    direction character varying(16) NOT NULL,
    label character varying(500) DEFAULT ''::character varying NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    parent_key character varying(128)
);

CREATE SEQUENCE gs_bem.gs_bem_power_balance_custom_flow_rows_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_bem.gs_bem_power_balance_custom_flow_rows_id_seq OWNED BY gs_bem.gs_bem_power_balance_custom_flow_rows.id;

CREATE TABLE gs_bem.gs_bem_power_balance_custom_flow_values (
    id integer NOT NULL,
    id_row integer NOT NULL,
    year_number integer NOT NULL,
    value_mw numeric(25,16),
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

CREATE SEQUENCE gs_bem.gs_bem_power_balance_custom_flow_values_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_bem.gs_bem_power_balance_custom_flow_values_id_seq OWNED BY gs_bem.gs_bem_power_balance_custom_flow_values.id;

CREATE TABLE gs_bem.gs_bem_power_balance_demand_cold_values (
    id integer NOT NULL,
    sheet_slug character varying(128) NOT NULL,
    year_number integer NOT NULL,
    value_mw numeric(25,16),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255)
);

CREATE SEQUENCE gs_bem.gs_bem_power_balance_demand_cold_values_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_bem.gs_bem_power_balance_demand_cold_values_id_seq OWNED BY gs_bem.gs_bem_power_balance_demand_cold_values.id;

CREATE TABLE gs_bem.gs_bem_power_balance_export_values (
    id integer NOT NULL,
    sheet_slug character varying(128) NOT NULL,
    year_number integer NOT NULL,
    value_mw numeric(25,16),
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

CREATE SEQUENCE gs_bem.gs_bem_power_balance_export_values_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_bem.gs_bem_power_balance_export_values_id_seq OWNED BY gs_bem.gs_bem_power_balance_export_values.id;

CREATE TABLE gs_bem.gs_bem_regional_energy_system_ee_exports (
    id integer NOT NULL,
    year_number integer,
    month_number integer DEFAULT 0 NOT NULL,
    id_from_regional_energy_system integer,
    id_from_regional_district integer,
    id_to_regional_energy_system integer,
    id_to_foreign_border_country integer,
    id_to_regional_district integer,
    id_to_energy_unit integer,
    id_union_energy_system integer,
    source_oes_name character varying(500),
    export_value numeric(25,16),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    CONSTRAINT ck_ee_export_from_source CHECK ((((id_from_regional_energy_system IS NOT NULL) AND (id_from_regional_district IS NULL)) OR ((id_from_regional_energy_system IS NULL) AND (id_from_regional_district IS NOT NULL)))),
    CONSTRAINT ck_ee_export_to_target CHECK ((((id_to_regional_energy_system IS NOT NULL) AND (id_to_foreign_border_country IS NULL) AND (id_to_regional_district IS NULL) AND (id_to_energy_unit IS NULL)) OR ((id_to_regional_energy_system IS NULL) AND (id_to_foreign_border_country IS NOT NULL) AND (id_to_regional_district IS NULL) AND (id_to_energy_unit IS NULL)) OR ((id_to_regional_energy_system IS NULL) AND (id_to_foreign_border_country IS NULL) AND (id_to_regional_district IS NOT NULL) AND (id_to_energy_unit IS NULL)) OR ((id_to_regional_energy_system IS NULL) AND (id_to_foreign_border_country IS NULL) AND (id_to_regional_district IS NULL) AND (id_to_energy_unit IS NOT NULL))))
);

CREATE SEQUENCE gs_bem.gs_bem_regional_energy_system_ee_exports_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_bem.gs_bem_regional_energy_system_ee_exports_id_seq OWNED BY gs_bem.gs_bem_regional_energy_system_ee_exports.id;

CREATE TABLE gs_bem.gs_bem_regional_energy_system_em_exports (
    id integer NOT NULL,
    year_number integer,
    month_number integer DEFAULT 0 NOT NULL,
    id_from_regional_energy_system integer,
    id_from_regional_district integer,
    id_to_regional_energy_system integer,
    id_to_foreign_border_country integer,
    id_to_regional_district integer,
    id_to_energy_unit integer,
    id_union_energy_system integer,
    source_oes_name character varying(500),
    export_value numeric(25,16),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    CONSTRAINT ck_em_export_from_source CHECK ((((id_from_regional_energy_system IS NOT NULL) AND (id_from_regional_district IS NULL)) OR ((id_from_regional_energy_system IS NULL) AND (id_from_regional_district IS NOT NULL)))),
    CONSTRAINT ck_em_export_to_target CHECK ((((id_to_regional_energy_system IS NOT NULL) AND (id_to_foreign_border_country IS NULL) AND (id_to_regional_district IS NULL) AND (id_to_energy_unit IS NULL)) OR ((id_to_regional_energy_system IS NULL) AND (id_to_foreign_border_country IS NOT NULL) AND (id_to_regional_district IS NULL) AND (id_to_energy_unit IS NULL)) OR ((id_to_regional_energy_system IS NULL) AND (id_to_foreign_border_country IS NULL) AND (id_to_regional_district IS NOT NULL) AND (id_to_energy_unit IS NULL)) OR ((id_to_regional_energy_system IS NULL) AND (id_to_foreign_border_country IS NULL) AND (id_to_regional_district IS NULL) AND (id_to_energy_unit IS NOT NULL))))
);

CREATE SEQUENCE gs_bem.gs_bem_regional_energy_system_em_exports_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_bem.gs_bem_regional_energy_system_em_exports_id_seq OWNED BY gs_bem.gs_bem_regional_energy_system_em_exports.id;

CREATE TABLE gs_bem.gs_bem_regional_energy_system_energy_generations (
    id integer NOT NULL,
    year_number integer,
    month_number integer DEFAULT 0 NOT NULL,
    id_regional_energy_system integer,
    electricity_generation numeric(25,16),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_bem.gs_bem_regional_energy_system_energy_generations IS 'Контрольная выработка электроэнергии по РЭС';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_energy_generations.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_energy_generations.year_number IS 'Календарный год контрольной выработки';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_energy_generations.month_number IS 'Номер месяца; 0 означает годовое значение';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_energy_generations.id_regional_energy_system IS 'Региональная энергосистема контрольного значения';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_energy_generations.electricity_generation IS 'Выработка электроэнергии, млн кВт·ч';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_energy_generations.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_energy_generations.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_energy_generations.database_version_id IS 'Версия базы данных';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_energy_generations.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_energy_generations.modified_by IS 'Пользователь, последним изменивший запись';

CREATE TABLE gs_bem.gs_bem_regional_energy_system_transfers (
    id integer NOT NULL,
    year_number integer,
    month_number integer DEFAULT 0 NOT NULL,
    id_from_regional_energy_system integer,
    id_to_regional_energy_system integer,
    id_union_energy_system integer,
    source_oes_name character varying(500),
    transfer_value numeric(25,16),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    id_to_foreign_border_country integer,
    id_from_regional_district integer,
    id_to_regional_district integer,
    id_to_energy_unit integer,
    CONSTRAINT ck_ee_transfer_from_source CHECK ((((id_from_regional_energy_system IS NOT NULL) AND (id_from_regional_district IS NULL)) OR ((id_from_regional_energy_system IS NULL) AND (id_from_regional_district IS NOT NULL)))),
    CONSTRAINT ck_ee_transfer_to_target CHECK ((((id_to_regional_energy_system IS NOT NULL) AND (id_to_foreign_border_country IS NULL) AND (id_to_regional_district IS NULL) AND (id_to_energy_unit IS NULL)) OR ((id_to_regional_energy_system IS NULL) AND (id_to_foreign_border_country IS NOT NULL) AND (id_to_regional_district IS NULL) AND (id_to_energy_unit IS NULL)) OR ((id_to_regional_energy_system IS NULL) AND (id_to_foreign_border_country IS NULL) AND (id_to_regional_district IS NOT NULL) AND (id_to_energy_unit IS NULL)) OR ((id_to_regional_energy_system IS NULL) AND (id_to_foreign_border_country IS NULL) AND (id_to_regional_district IS NULL) AND (id_to_energy_unit IS NOT NULL))))
);

COMMENT ON TABLE gs_bem.gs_bem_regional_energy_system_transfers IS 'Перетоки электроэнергии между энергосистемами и смежными получателями';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_transfers.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_transfers.year_number IS 'Календарный год перетока';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_transfers.month_number IS 'Номер месяца; 0 означает годовое значение';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_transfers.id_from_regional_energy_system IS 'РЭС-источник перетока';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_transfers.id_to_regional_energy_system IS 'РЭС-получатель перетока';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_transfers.id_union_energy_system IS 'ОЭС, к которой относится переток';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_transfers.source_oes_name IS 'Наименование исходной ОЭС из импортируемого файла';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_transfers.transfer_value IS 'Значение перетока электроэнергии, млн кВт·ч';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_transfers.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_transfers.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_transfers.database_version_id IS 'Версия базы данных';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_transfers.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_transfers.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_transfers.id_to_foreign_border_country IS 'Зарубежная страна-получатель перетока';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_transfers.id_from_regional_district IS 'Субъект РФ-источник перетока';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_transfers.id_to_regional_district IS 'Субъект РФ-получатель перетока';

COMMENT ON COLUMN gs_bem.gs_bem_regional_energy_system_transfers.id_to_energy_unit IS 'Энергоузел-получатель перетока';

CREATE SEQUENCE gs_bem.gs_bem_regional_energy_system_transfers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_bem.gs_bem_regional_energy_system_transfers_id_seq OWNED BY gs_bem.gs_bem_regional_energy_system_transfers.id;

CREATE TABLE gs_bem.gs_bem_station_energy_generations (
    id integer NOT NULL,
    year_number integer,
    id_station integer,
    electricity_generation numeric(25,16),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    month_number integer DEFAULT 0 NOT NULL,
    own_needs numeric(25,16),
    own_needs_percent numeric(36,16)
);

COMMENT ON TABLE gs_bem.gs_bem_station_energy_generations IS 'выработка электроэнергии электростанцией по годам (млн кВт·ч)';

COMMENT ON COLUMN gs_bem.gs_bem_station_energy_generations.id IS 'идентификатор';

COMMENT ON COLUMN gs_bem.gs_bem_station_energy_generations.year_number IS 'номер года (FK)';

COMMENT ON COLUMN gs_bem.gs_bem_station_energy_generations.id_station IS 'идентификатор электростанции (FK)';

COMMENT ON COLUMN gs_bem.gs_bem_station_energy_generations.electricity_generation IS 'выработка, млн кВт·ч (точность как у мощностей / импорта excel)';

COMMENT ON COLUMN gs_bem.gs_bem_station_energy_generations.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_bem.gs_bem_station_energy_generations.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_bem.gs_bem_station_energy_generations.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_bem.gs_bem_station_energy_generations.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_bem.gs_bem_station_energy_generations.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_bem.gs_bem_station_energy_generations.month_number IS 'Номер месяца; 0 означает годовое значение';

CREATE SEQUENCE gs_bem.gs_gen_espp_energy_generations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_bem.gs_gen_espp_energy_generations_id_seq OWNED BY gs_bem.gs_bem_espp_energy_generations.id;

CREATE SEQUENCE gs_bem.gs_gen_regional_energy_system_energy_generations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_bem.gs_gen_regional_energy_system_energy_generations_id_seq OWNED BY gs_bem.gs_bem_regional_energy_system_energy_generations.id;

CREATE SEQUENCE gs_bem.gs_gen_station_energy_generations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_bem.gs_gen_station_energy_generations_id_seq OWNED BY gs_bem.gs_bem_station_energy_generations.id;

CREATE TABLE gs_ec.gs_ec_centralized_zone_consumption_params (
    id integer NOT NULL,
    year_number integer,
    energy_consumption_mln_kvt_ch numeric(25,16),
    energy_consumption_sipr_mln_kvt_ch numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    perimeter_variant_code character varying(64)
);

COMMENT ON TABLE gs_ec.gs_ec_centralized_zone_consumption_params IS 'Параметры потребления электроэнергии для централизованной зоны (агрегат без FK)';

COMMENT ON COLUMN gs_ec.gs_ec_centralized_zone_consumption_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ec.gs_ec_centralized_zone_consumption_params.year_number IS 'Год';

COMMENT ON COLUMN gs_ec.gs_ec_centralized_zone_consumption_params.energy_consumption_mln_kvt_ch IS 'Потребление электрической энергии, млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_centralized_zone_consumption_params.energy_consumption_sipr_mln_kvt_ch IS 'Потребление электрической энергии (СиПР), млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_centralized_zone_consumption_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ec.gs_ec_centralized_zone_consumption_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ec.gs_ec_centralized_zone_consumption_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ec.gs_ec_centralized_zone_consumption_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ec.gs_ec_centralized_zone_consumption_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ec.gs_ec_centralized_zone_consumption_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_ec.gs_ec_centralized_zone_consumption_params.perimeter_variant_code IS 'Код варианта периметра (NULL — без варианта)';

CREATE SEQUENCE gs_ec.gs_ec_centralized_zone_consumption_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ec.gs_ec_centralized_zone_consumption_params_id_seq OWNED BY gs_ec.gs_ec_centralized_zone_consumption_params.id;

CREATE TABLE gs_ec.gs_ec_ees_consumption_params (
    id integer NOT NULL,
    year_number integer,
    energy_consumption_mln_kvt_ch numeric(25,16),
    energy_consumption_sipr_mln_kvt_ch numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    perimeter_variant_code character varying(64)
);

COMMENT ON TABLE gs_ec.gs_ec_ees_consumption_params IS 'Параметры потребления электроэнергии для ЭЭС (без FK на справочник)';

COMMENT ON COLUMN gs_ec.gs_ec_ees_consumption_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ec.gs_ec_ees_consumption_params.year_number IS 'Номер года';

COMMENT ON COLUMN gs_ec.gs_ec_ees_consumption_params.energy_consumption_mln_kvt_ch IS 'Потребление электроэнергии, млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_ees_consumption_params.energy_consumption_sipr_mln_kvt_ch IS 'Потребление электроэнергии (СИПР), млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_ees_consumption_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ec.gs_ec_ees_consumption_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ec.gs_ec_ees_consumption_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ec.gs_ec_ees_consumption_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ec.gs_ec_ees_consumption_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ec.gs_ec_ees_consumption_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_ec.gs_ec_ees_consumption_params.perimeter_variant_code IS 'Код варианта периметра (NULL — без варианта)';

CREATE SEQUENCE gs_ec.gs_ec_ees_consumption_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ec.gs_ec_ees_consumption_params_id_seq OWNED BY gs_ec.gs_ec_ees_consumption_params.id;

CREATE TABLE gs_ec.gs_ec_ees_russia_consumption_params (
    id integer NOT NULL,
    year_number integer,
    energy_consumption_mln_kvt_ch numeric(25,16),
    energy_consumption_sipr_mln_kvt_ch numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    perimeter_variant_code character varying(64)
);

COMMENT ON TABLE gs_ec.gs_ec_ees_russia_consumption_params IS 'Параметры потребления для ЕЭС России';

COMMENT ON COLUMN gs_ec.gs_ec_ees_russia_consumption_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ec.gs_ec_ees_russia_consumption_params.year_number IS 'Номер года';

COMMENT ON COLUMN gs_ec.gs_ec_ees_russia_consumption_params.energy_consumption_mln_kvt_ch IS 'Потребление электроэнергии, млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_ees_russia_consumption_params.energy_consumption_sipr_mln_kvt_ch IS 'Потребление электроэнергии (СИПР), млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_ees_russia_consumption_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ec.gs_ec_ees_russia_consumption_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ec.gs_ec_ees_russia_consumption_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ec.gs_ec_ees_russia_consumption_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ec.gs_ec_ees_russia_consumption_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ec.gs_ec_ees_russia_consumption_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_ec.gs_ec_ees_russia_consumption_params.perimeter_variant_code IS 'Код варианта периметра (NULL — без варианта)';

CREATE SEQUENCE gs_ec.gs_ec_ees_russia_consumption_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ec.gs_ec_ees_russia_consumption_params_id_seq OWNED BY gs_ec.gs_ec_ees_russia_consumption_params.id;

CREATE TABLE gs_ec.gs_ec_energy_area_consumption_params (
    id integer NOT NULL,
    id_energy_area integer NOT NULL,
    year_number integer,
    energy_consumption_mln_kvt_ch numeric(25,16),
    energy_consumption_sipr_mln_kvt_ch numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    perimeter_variant_code character varying(64)
);

COMMENT ON TABLE gs_ec.gs_ec_energy_area_consumption_params IS 'Параметры потребления для энергорайона (EnergyArea)';

COMMENT ON COLUMN gs_ec.gs_ec_energy_area_consumption_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ec.gs_ec_energy_area_consumption_params.id_energy_area IS 'Энергорайон (FK -> gs_sys.gs_sys_energy_areas)';

COMMENT ON COLUMN gs_ec.gs_ec_energy_area_consumption_params.year_number IS 'Номер года';

COMMENT ON COLUMN gs_ec.gs_ec_energy_area_consumption_params.energy_consumption_mln_kvt_ch IS 'Потребление электроэнергии, млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_energy_area_consumption_params.energy_consumption_sipr_mln_kvt_ch IS 'Потребление электроэнергии (СИПР), млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_energy_area_consumption_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ec.gs_ec_energy_area_consumption_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ec.gs_ec_energy_area_consumption_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ec.gs_ec_energy_area_consumption_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ec.gs_ec_energy_area_consumption_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ec.gs_ec_energy_area_consumption_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_ec.gs_ec_energy_area_consumption_params.perimeter_variant_code IS 'Код варианта периметра (NULL — без варианта)';

CREATE SEQUENCE gs_ec.gs_ec_energy_area_consumption_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ec.gs_ec_energy_area_consumption_params_id_seq OWNED BY gs_ec.gs_ec_energy_area_consumption_params.id;

CREATE TABLE gs_ec.gs_ec_energy_system_type_consumption_params (
    id integer NOT NULL,
    id_energy_system_type integer NOT NULL,
    year_number integer,
    energy_consumption_mln_kvt_ch numeric(25,16),
    energy_consumption_sipr_mln_kvt_ch numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    perimeter_variant_code character varying(64)
);

COMMENT ON TABLE gs_ec.gs_ec_energy_system_type_consumption_params IS 'Параметры потребления для типа энергосистемы';

COMMENT ON COLUMN gs_ec.gs_ec_energy_system_type_consumption_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ec.gs_ec_energy_system_type_consumption_params.id_energy_system_type IS 'Тип энергосистемы (FK -> gs_sys.gs_sys_energy_system_types)';

COMMENT ON COLUMN gs_ec.gs_ec_energy_system_type_consumption_params.year_number IS 'Номер года';

COMMENT ON COLUMN gs_ec.gs_ec_energy_system_type_consumption_params.energy_consumption_mln_kvt_ch IS 'Потребление электроэнергии, млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_energy_system_type_consumption_params.energy_consumption_sipr_mln_kvt_ch IS 'Потребление электроэнергии (СИПР), млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_energy_system_type_consumption_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ec.gs_ec_energy_system_type_consumption_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ec.gs_ec_energy_system_type_consumption_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ec.gs_ec_energy_system_type_consumption_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ec.gs_ec_energy_system_type_consumption_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ec.gs_ec_energy_system_type_consumption_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_ec.gs_ec_energy_system_type_consumption_params.perimeter_variant_code IS 'Код варианта периметра (NULL — без варианта)';

CREATE SEQUENCE gs_ec.gs_ec_energy_system_type_consumption_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ec.gs_ec_energy_system_type_consumption_params_id_seq OWNED BY gs_ec.gs_ec_energy_system_type_consumption_params.id;

CREATE TABLE gs_ec.gs_ec_energy_unit_consumption_params (
    id integer NOT NULL,
    id_energy_unit integer NOT NULL,
    year_number integer,
    energy_consumption_mln_kvt_ch numeric(25,16),
    energy_consumption_sipr_mln_kvt_ch numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    perimeter_variant_code character varying(64)
);

COMMENT ON TABLE gs_ec.gs_ec_energy_unit_consumption_params IS 'Параметры потребления для энергоузла';

COMMENT ON COLUMN gs_ec.gs_ec_energy_unit_consumption_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ec.gs_ec_energy_unit_consumption_params.id_energy_unit IS 'Энергоузел (FK -> gs_sys.gs_sys_energy_units)';

COMMENT ON COLUMN gs_ec.gs_ec_energy_unit_consumption_params.year_number IS 'Номер года';

COMMENT ON COLUMN gs_ec.gs_ec_energy_unit_consumption_params.energy_consumption_mln_kvt_ch IS 'Потребление электроэнергии, млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_energy_unit_consumption_params.energy_consumption_sipr_mln_kvt_ch IS 'Потребление электроэнергии (СИПР), млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_energy_unit_consumption_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ec.gs_ec_energy_unit_consumption_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ec.gs_ec_energy_unit_consumption_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ec.gs_ec_energy_unit_consumption_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ec.gs_ec_energy_unit_consumption_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ec.gs_ec_energy_unit_consumption_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_ec.gs_ec_energy_unit_consumption_params.perimeter_variant_code IS 'Код варианта периметра (NULL — без варианта)';

CREATE SEQUENCE gs_ec.gs_ec_energy_unit_consumption_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ec.gs_ec_energy_unit_consumption_params_id_seq OWNED BY gs_ec.gs_ec_energy_unit_consumption_params.id;

CREATE TABLE gs_ec.gs_ec_energy_zone_consumption_params (
    id integer NOT NULL,
    id_energy_zone integer NOT NULL,
    year_number integer,
    energy_consumption_mln_kvt_ch numeric(25,16),
    energy_consumption_sipr_mln_kvt_ch numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    perimeter_variant_code character varying(64)
);

COMMENT ON TABLE gs_ec.gs_ec_energy_zone_consumption_params IS 'Параметры потребления для энергозоны';

COMMENT ON COLUMN gs_ec.gs_ec_energy_zone_consumption_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ec.gs_ec_energy_zone_consumption_params.id_energy_zone IS 'Энергозона (FK -> gs_sys.gs_sys_energy_zones)';

COMMENT ON COLUMN gs_ec.gs_ec_energy_zone_consumption_params.year_number IS 'Номер года';

COMMENT ON COLUMN gs_ec.gs_ec_energy_zone_consumption_params.energy_consumption_mln_kvt_ch IS 'Потребление электроэнергии, млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_energy_zone_consumption_params.energy_consumption_sipr_mln_kvt_ch IS 'Потребление электроэнергии (СИПР), млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_energy_zone_consumption_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ec.gs_ec_energy_zone_consumption_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ec.gs_ec_energy_zone_consumption_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ec.gs_ec_energy_zone_consumption_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ec.gs_ec_energy_zone_consumption_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ec.gs_ec_energy_zone_consumption_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_ec.gs_ec_energy_zone_consumption_params.perimeter_variant_code IS 'Код варианта периметра (NULL — без варианта)';

CREATE SEQUENCE gs_ec.gs_ec_energy_zone_consumption_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ec.gs_ec_energy_zone_consumption_params_id_seq OWNED BY gs_ec.gs_ec_energy_zone_consumption_params.id;

CREATE TABLE gs_ec.gs_ec_federal_district_consumption_params (
    id integer NOT NULL,
    id_federal_district integer NOT NULL,
    year_number integer,
    energy_consumption_mln_kvt_ch numeric(25,16),
    energy_consumption_sipr_mln_kvt_ch numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    perimeter_variant_code character varying(64)
);

COMMENT ON TABLE gs_ec.gs_ec_federal_district_consumption_params IS 'Параметры потребления для федерального округа';

COMMENT ON COLUMN gs_ec.gs_ec_federal_district_consumption_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ec.gs_ec_federal_district_consumption_params.id_federal_district IS 'Федеральный округ (FK -> gs_sys.gs_sys_federal_districts)';

COMMENT ON COLUMN gs_ec.gs_ec_federal_district_consumption_params.year_number IS 'Номер года';

COMMENT ON COLUMN gs_ec.gs_ec_federal_district_consumption_params.energy_consumption_mln_kvt_ch IS 'Потребление электроэнергии, млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_federal_district_consumption_params.energy_consumption_sipr_mln_kvt_ch IS 'Потребление электроэнергии (СИПР), млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_federal_district_consumption_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ec.gs_ec_federal_district_consumption_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ec.gs_ec_federal_district_consumption_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ec.gs_ec_federal_district_consumption_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ec.gs_ec_federal_district_consumption_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ec.gs_ec_federal_district_consumption_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_ec.gs_ec_federal_district_consumption_params.perimeter_variant_code IS 'Код варианта периметра (NULL — без варианта)';

CREATE SEQUENCE gs_ec.gs_ec_federal_district_consumption_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ec.gs_ec_federal_district_consumption_params_id_seq OWNED BY gs_ec.gs_ec_federal_district_consumption_params.id;

CREATE TABLE gs_ec.gs_ec_regional_district_consumption_params (
    id integer NOT NULL,
    id_regional_district integer NOT NULL,
    year_number integer,
    energy_consumption_mln_kvt_ch numeric(25,16),
    energy_consumption_sipr_mln_kvt_ch numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    perimeter_variant_code character varying(64)
);

COMMENT ON TABLE gs_ec.gs_ec_regional_district_consumption_params IS 'Параметры потребления для субъекта РФ';

COMMENT ON COLUMN gs_ec.gs_ec_regional_district_consumption_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ec.gs_ec_regional_district_consumption_params.id_regional_district IS 'Субъект РФ (FK -> gs_sys.gs_sys_regional_districts)';

COMMENT ON COLUMN gs_ec.gs_ec_regional_district_consumption_params.year_number IS 'Номер года';

COMMENT ON COLUMN gs_ec.gs_ec_regional_district_consumption_params.energy_consumption_mln_kvt_ch IS 'Потребление электроэнергии, млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_regional_district_consumption_params.energy_consumption_sipr_mln_kvt_ch IS 'Потребление электроэнергии (СИПР), млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_regional_district_consumption_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ec.gs_ec_regional_district_consumption_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ec.gs_ec_regional_district_consumption_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ec.gs_ec_regional_district_consumption_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ec.gs_ec_regional_district_consumption_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ec.gs_ec_regional_district_consumption_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_ec.gs_ec_regional_district_consumption_params.perimeter_variant_code IS 'Код варианта периметра (NULL — без варианта)';

CREATE SEQUENCE gs_ec.gs_ec_regional_district_consumption_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ec.gs_ec_regional_district_consumption_params_id_seq OWNED BY gs_ec.gs_ec_regional_district_consumption_params.id;

CREATE TABLE gs_ec.gs_ec_regional_energy_system_consumption_params (
    id integer NOT NULL,
    id_regional_energy_system integer NOT NULL,
    year_number integer,
    energy_consumption_mln_kvt_ch numeric(25,16),
    energy_consumption_sipr_mln_kvt_ch numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    perimeter_variant_code character varying(64)
);

COMMENT ON TABLE gs_ec.gs_ec_regional_energy_system_consumption_params IS 'Параметры потребления для региональной энергосистемы';

COMMENT ON COLUMN gs_ec.gs_ec_regional_energy_system_consumption_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ec.gs_ec_regional_energy_system_consumption_params.id_regional_energy_system IS 'Региональная энергосистема (FK -> gs_sys.gs_sys_regional_energy_systems)';

COMMENT ON COLUMN gs_ec.gs_ec_regional_energy_system_consumption_params.year_number IS 'Номер года';

COMMENT ON COLUMN gs_ec.gs_ec_regional_energy_system_consumption_params.energy_consumption_mln_kvt_ch IS 'Потребление электроэнергии, млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_regional_energy_system_consumption_params.energy_consumption_sipr_mln_kvt_ch IS 'Потребление электроэнергии (СИПР), млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_regional_energy_system_consumption_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ec.gs_ec_regional_energy_system_consumption_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ec.gs_ec_regional_energy_system_consumption_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ec.gs_ec_regional_energy_system_consumption_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ec.gs_ec_regional_energy_system_consumption_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ec.gs_ec_regional_energy_system_consumption_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_ec.gs_ec_regional_energy_system_consumption_params.perimeter_variant_code IS 'Код варианта периметра (NULL — без варианта)';

CREATE SEQUENCE gs_ec.gs_ec_regional_energy_system_consumption_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ec.gs_ec_regional_energy_system_consumption_params_id_seq OWNED BY gs_ec.gs_ec_regional_energy_system_consumption_params.id;

CREATE TABLE gs_ec.gs_ec_russia_federation_consumption_params (
    id integer NOT NULL,
    year_number integer,
    energy_consumption_mln_kvt_ch numeric(25,16),
    energy_consumption_sipr_mln_kvt_ch numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    perimeter_variant_code character varying(64)
);

COMMENT ON TABLE gs_ec.gs_ec_russia_federation_consumption_params IS 'Параметры потребления для РФ (агрегат без строки справочника)';

COMMENT ON COLUMN gs_ec.gs_ec_russia_federation_consumption_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ec.gs_ec_russia_federation_consumption_params.year_number IS 'Номер года';

COMMENT ON COLUMN gs_ec.gs_ec_russia_federation_consumption_params.energy_consumption_mln_kvt_ch IS 'Потребление электроэнергии, млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_russia_federation_consumption_params.energy_consumption_sipr_mln_kvt_ch IS 'Потребление электроэнергии (СИПР), млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_russia_federation_consumption_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ec.gs_ec_russia_federation_consumption_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ec.gs_ec_russia_federation_consumption_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ec.gs_ec_russia_federation_consumption_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ec.gs_ec_russia_federation_consumption_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ec.gs_ec_russia_federation_consumption_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_ec.gs_ec_russia_federation_consumption_params.perimeter_variant_code IS 'Код варианта периметра (NULL — без варианта)';

CREATE SEQUENCE gs_ec.gs_ec_russia_federation_consumption_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ec.gs_ec_russia_federation_consumption_params_id_seq OWNED BY gs_ec.gs_ec_russia_federation_consumption_params.id;

CREATE TABLE gs_ec.gs_ec_summary_formula_texts (
    id integer NOT NULL,
    formula_key character varying(128) NOT NULL,
    formula_text text NOT NULL,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE gs_ec.gs_ec_summary_formula_texts IS 'Переопределения текстов формул (подсказки «i») для сводок потребления ЭЭ';

COMMENT ON COLUMN gs_ec.gs_ec_summary_formula_texts.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ec.gs_ec_summary_formula_texts.formula_key IS 'Ключ формулы';

COMMENT ON COLUMN gs_ec.gs_ec_summary_formula_texts.formula_text IS 'Текст формулы';

COMMENT ON COLUMN gs_ec.gs_ec_summary_formula_texts.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ec.gs_ec_summary_formula_texts.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ec.gs_ec_summary_formula_texts.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ec.gs_ec_summary_formula_texts.updated_at IS 'Дата и время последнего изменения записи';

CREATE SEQUENCE gs_ec.gs_ec_summary_formula_texts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ec.gs_ec_summary_formula_texts_id_seq OWNED BY gs_ec.gs_ec_summary_formula_texts.id;

CREATE TABLE gs_ec.gs_ec_synchronous_area_consumption_params (
    id integer NOT NULL,
    id_synchronous_area integer NOT NULL,
    year_number integer,
    energy_consumption_mln_kvt_ch numeric(25,16),
    energy_consumption_sipr_mln_kvt_ch numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    perimeter_variant_code character varying(64)
);

COMMENT ON TABLE gs_ec.gs_ec_synchronous_area_consumption_params IS 'Параметры потребления для синхронной зоны';

COMMENT ON COLUMN gs_ec.gs_ec_synchronous_area_consumption_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ec.gs_ec_synchronous_area_consumption_params.id_synchronous_area IS 'Синхронная зона (FK -> gs_sys.gs_sys_synchronous_areas)';

COMMENT ON COLUMN gs_ec.gs_ec_synchronous_area_consumption_params.year_number IS 'Номер года';

COMMENT ON COLUMN gs_ec.gs_ec_synchronous_area_consumption_params.energy_consumption_mln_kvt_ch IS 'Потребление электроэнергии, млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_synchronous_area_consumption_params.energy_consumption_sipr_mln_kvt_ch IS 'Потребление электроэнергии (СИПР), млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_synchronous_area_consumption_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ec.gs_ec_synchronous_area_consumption_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ec.gs_ec_synchronous_area_consumption_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ec.gs_ec_synchronous_area_consumption_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ec.gs_ec_synchronous_area_consumption_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ec.gs_ec_synchronous_area_consumption_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_ec.gs_ec_synchronous_area_consumption_params.perimeter_variant_code IS 'Код варианта периметра (NULL — без варианта)';

CREATE SEQUENCE gs_ec.gs_ec_synchronous_area_consumption_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ec.gs_ec_synchronous_area_consumption_params_id_seq OWNED BY gs_ec.gs_ec_synchronous_area_consumption_params.id;

CREATE TABLE gs_ec.gs_ec_union_energy_system_consumption_params (
    id integer NOT NULL,
    id_union_energy_system integer NOT NULL,
    year_number integer,
    energy_consumption_mln_kvt_ch numeric(25,16),
    energy_consumption_sipr_mln_kvt_ch numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    perimeter_variant_code character varying(64)
);

COMMENT ON TABLE gs_ec.gs_ec_union_energy_system_consumption_params IS 'Параметры потребления для объединённой энергосистемы';

COMMENT ON COLUMN gs_ec.gs_ec_union_energy_system_consumption_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ec.gs_ec_union_energy_system_consumption_params.id_union_energy_system IS 'Объединённая энергосистема (FK -> gs_sys.gs_sys_union_energy_systems)';

COMMENT ON COLUMN gs_ec.gs_ec_union_energy_system_consumption_params.year_number IS 'Номер года';

COMMENT ON COLUMN gs_ec.gs_ec_union_energy_system_consumption_params.energy_consumption_mln_kvt_ch IS 'Потребление электроэнергии, млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_union_energy_system_consumption_params.energy_consumption_sipr_mln_kvt_ch IS 'Потребление электроэнергии (СИПР), млн кВт·ч';

COMMENT ON COLUMN gs_ec.gs_ec_union_energy_system_consumption_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ec.gs_ec_union_energy_system_consumption_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ec.gs_ec_union_energy_system_consumption_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ec.gs_ec_union_energy_system_consumption_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ec.gs_ec_union_energy_system_consumption_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ec.gs_ec_union_energy_system_consumption_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_ec.gs_ec_union_energy_system_consumption_params.perimeter_variant_code IS 'Код варианта периметра (NULL — без варианта)';

CREATE SEQUENCE gs_ec.gs_ec_union_energy_system_consumption_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ec.gs_ec_union_energy_system_consumption_params_id_seq OWNED BY gs_ec.gs_ec_union_energy_system_consumption_params.id;

CREATE TABLE gs_eco.gs_eco_analysis_pg_params (
    id integer NOT NULL,
    sheet_slug character varying(40) NOT NULL,
    station_numb integer NOT NULL,
    year_number integer NOT NULL,
    gas_consumption_tce numeric(36,16),
    co2_from_gas_t numeric(36,16),
    oil_fuel_consumption_tce numeric(36,16),
    co2_from_oil_fuel_t numeric(36,16),
    solid_fuel_consumption_tce numeric(36,16),
    co2_from_solid_fuel_t numeric(36,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

COMMENT ON TABLE gs_eco.gs_eco_analysis_pg_params IS 'Параметры анализа ПГ: выверенная копия отчетных данных ГИС ТЭК для страниц pg-vse / pg-bez-kot';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_pg_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_pg_params.sheet_slug IS 'Страница анализа: pg-vse или pg-bez-kot';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_pg_params.station_numb IS 'Код группы оборудования: station_numb (numb1120) = EquipmentGroup.numb (без FK — numb не уникален)';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_pg_params.year_number IS 'Год: Year.number + database_version_id (composite FK)';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_pg_params.gas_consumption_tce IS 'Расход газа, тут (GAZ_ek)';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_pg_params.co2_from_gas_t IS 'Выбросы СО2 от сжигания газа, т (CO2_gaz)';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_pg_params.oil_fuel_consumption_tce IS 'Расход мазута, тут (MAZUT_ek)';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_pg_params.co2_from_oil_fuel_t IS 'Выбросы СО2 от сжигания мазута, т (CO2_mazut)';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_pg_params.solid_fuel_consumption_tce IS 'Расход твердого топлива, тут (TvTopl_ek)';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_pg_params.co2_from_solid_fuel_t IS 'Выбросы СО2 от сжигания твердого топлива, т (CO2_ugol)';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_pg_params.note IS 'Примечание';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_pg_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_pg_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_pg_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_pg_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_pg_params.database_version_id IS 'Версия базы данных, FK -> gs_sys.gs_database_versions';

CREATE SEQUENCE gs_eco.gs_eco_analysis_pg_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_eco.gs_eco_analysis_pg_params_id_seq OWNED BY gs_eco.gs_eco_analysis_pg_params.id;

CREATE TABLE gs_eco.gs_eco_analysis_zv_params (
    id integer NOT NULL,
    sheet_slug character varying(40) NOT NULL,
    station_numb integer NOT NULL,
    year_number integer NOT NULL,
    solid_substances numeric(36,16),
    sulfur_dioxide numeric(36,16),
    carbon_monoxide numeric(36,16),
    nitrogen_oxides numeric(36,16),
    hydrocarbons numeric(36,16),
    voc numeric(36,16),
    other_gaseous_and_liquid numeric(36,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

COMMENT ON TABLE gs_eco.gs_eco_analysis_zv_params IS 'Параметры анализа ЗВ: выверенная копия отчетных данных ГИС ТЭК для страниц zv-vse / zv-bez-kot';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_zv_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_zv_params.sheet_slug IS 'Страница анализа: zv-vse или zv-bez-kot';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_zv_params.station_numb IS 'Код группы оборудования (numb1120), связь с отчетными ЗВ';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_zv_params.year_number IS 'Год (связь с gs_sys.gs_sys_years по number и database_version_id)';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_zv_params.solid_substances IS 'Твердые вещества, т (TVERD_V ← Твердые вещества)';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_zv_params.sulfur_dioxide IS 'Диоксид серы, т (SO2_gaz ← диоксид серы)';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_zv_params.carbon_monoxide IS 'Оксид углерода [CO], т (CO_gaz ← оксид углерода)';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_zv_params.nitrogen_oxides IS 'Оксиды азота [в пересчете на NO2], т (NOx_gaz ← оксиды азота)';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_zv_params.hydrocarbons IS 'Углеводороды [без летучих органических соединений], т (UGLEVOD ← углеводороды)';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_zv_params.voc IS 'Летучие органические соединения [ЛОС], т (LOS ← ЛОС)';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_zv_params.other_gaseous_and_liquid IS 'В т.ч. прочие газообразные и жидкие, т (PROCH_ekol ← прочие)';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_zv_params.note IS 'Примечание';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_zv_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_zv_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_zv_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_zv_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_eco.gs_eco_analysis_zv_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

CREATE SEQUENCE gs_eco.gs_eco_analysis_zv_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_eco.gs_eco_analysis_zv_params_id_seq OWNED BY gs_eco.gs_eco_analysis_zv_params.id;

CREATE TABLE gs_eco.gs_eco_fuel_snapshots (
    id integer NOT NULL,
    database_version_id integer NOT NULL,
    year_number integer NOT NULL,
    payload json NOT NULL,
    created_by character varying(255),
    modified_by character varying(255),
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    scope character varying(20) DEFAULT 'operating'::character varying NOT NULL
);

CREATE SEQUENCE gs_eco.gs_eco_fuel_snapshots_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_eco.gs_eco_fuel_snapshots_id_seq OWNED BY gs_eco.gs_eco_fuel_snapshots.id;

CREATE TABLE gs_eco.gs_eco_fuel_submissions (
    id integer NOT NULL,
    database_version_id integer NOT NULL,
    year_number integer NOT NULL,
    payload json NOT NULL,
    created_by character varying(255),
    modified_by character varying(255),
    status character varying(20) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    reviewed_at timestamp with time zone,
    scope character varying(20) DEFAULT 'operating'::character varying NOT NULL
);

CREATE SEQUENCE gs_eco.gs_eco_fuel_submissions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_eco.gs_eco_fuel_submissions_id_seq OWNED BY gs_eco.gs_eco_fuel_submissions.id;

CREATE TABLE gs_eco.gs_eco_gis_tek_greenhouse_gas_params (
    id integer NOT NULL,
    station_numb integer NOT NULL,
    gis_tek_station_name text,
    station_type character varying(80),
    equipment_group_id integer,
    year_number integer NOT NULL,
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    gas_consumption_tce numeric(36,16),
    co2_from_gas_t numeric(36,16),
    oil_fuel_consumption_tce numeric(36,16),
    co2_from_oil_fuel_t numeric(36,16),
    solid_fuel_consumption_tce numeric(36,16),
    co2_from_solid_fuel_t numeric(36,16)
);

COMMENT ON TABLE gs_eco.gs_eco_gis_tek_greenhouse_gas_params IS 'Отчетные данные ГИС ТЭК: парниковые газы (ПГ)';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_greenhouse_gas_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_greenhouse_gas_params.station_numb IS 'Код группы оборудования: station_numb (numb1120) = EquipmentGroup.numb (без FK — numb не уникален)';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_greenhouse_gas_params.gis_tek_station_name IS 'Электростанция (ГИС ТЭК), наименование из файла';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_greenhouse_gas_params.station_type IS 'Тип станции (КЭС, ТЭЦ и т.п.)';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_greenhouse_gas_params.equipment_group_id IS 'Группа оборудования (Топливо), FK -> gs_fue.gs_fue_equipment_groups';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_greenhouse_gas_params.year_number IS 'Год: Year.number + database_version_id (composite FK)';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_greenhouse_gas_params.note IS 'Примечание';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_greenhouse_gas_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_greenhouse_gas_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_greenhouse_gas_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_greenhouse_gas_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_greenhouse_gas_params.database_version_id IS 'Версия базы данных, FK -> gs_sys.gs_database_versions';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_greenhouse_gas_params.gas_consumption_tce IS 'Расход газа, тут';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_greenhouse_gas_params.co2_from_gas_t IS 'Выбросы СО2 от сжигания газа, т';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_greenhouse_gas_params.oil_fuel_consumption_tce IS 'Расход мазута, тут';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_greenhouse_gas_params.co2_from_oil_fuel_t IS 'Выбросы СО2 от сжигания мазута, т';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_greenhouse_gas_params.solid_fuel_consumption_tce IS 'Расход твердого топлива, тут';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_greenhouse_gas_params.co2_from_solid_fuel_t IS 'Выбросы СО2 от сжигания твердого топлива, т';

CREATE SEQUENCE gs_eco.gs_eco_gis_tek_greenhouse_gas_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_eco.gs_eco_gis_tek_greenhouse_gas_params_id_seq OWNED BY gs_eco.gs_eco_gis_tek_greenhouse_gas_params.id;

CREATE TABLE gs_eco.gs_eco_gis_tek_pollutant_params (
    id integer NOT NULL,
    station_numb integer NOT NULL,
    gis_tek_station_name text,
    station_type character varying(80),
    equipment_group_id integer,
    year_number integer NOT NULL,
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    solid_substances numeric(36,16),
    gaseous_and_liquid numeric(36,16),
    sulfur_dioxide numeric(36,16),
    carbon_monoxide numeric(36,16),
    nitrogen_oxides numeric(36,16),
    hydrocarbons numeric(36,16),
    voc numeric(36,16),
    other_gaseous_and_liquid numeric(36,16)
);

COMMENT ON TABLE gs_eco.gs_eco_gis_tek_pollutant_params IS 'Отчетные данные ГИС ТЭК: загрязняющие вещества (ЗВ)';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_pollutant_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_pollutant_params.station_numb IS 'Код группы оборудования: station_numb (numb1120) = EquipmentGroup.numb (без FK — numb не уникален)';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_pollutant_params.gis_tek_station_name IS 'Электростанция (ГИС ТЭК), наименование из файла';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_pollutant_params.station_type IS 'Тип станции (КЭС, ТЭЦ и т.п.)';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_pollutant_params.equipment_group_id IS 'Группа оборудования (Топливо), FK -> gs_fue.gs_fue_equipment_groups';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_pollutant_params.year_number IS 'Год: Year.number + database_version_id (composite FK)';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_pollutant_params.note IS 'Примечание';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_pollutant_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_pollutant_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_pollutant_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_pollutant_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_pollutant_params.database_version_id IS 'Версия базы данных, FK -> gs_sys.gs_database_versions';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_pollutant_params.solid_substances IS 'Твердые вещества, т';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_pollutant_params.gaseous_and_liquid IS 'Газообразные и жидкие вещества, т';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_pollutant_params.sulfur_dioxide IS 'Диоксид серы, т';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_pollutant_params.carbon_monoxide IS 'Оксид углерода [CO], т';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_pollutant_params.nitrogen_oxides IS 'Оксиды азота [в пересчете на NO2], т';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_pollutant_params.hydrocarbons IS 'Углеводороды [без летучих органических соединений], т';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_pollutant_params.voc IS 'Летучие органические соединения [ЛОС], т';

COMMENT ON COLUMN gs_eco.gs_eco_gis_tek_pollutant_params.other_gaseous_and_liquid IS 'В т.ч. прочие газообразные и жидкие, т';

CREATE SEQUENCE gs_eco.gs_eco_gis_tek_pollutant_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_eco.gs_eco_gis_tek_pollutant_params_id_seq OWNED BY gs_eco.gs_eco_gis_tek_pollutant_params.id;

CREATE TABLE gs_eco.gs_eco_new_tes_norms (
    id integer NOT NULL,
    fuel_key character varying(80) NOT NULL,
    capacity_class character varying(16) NOT NULL,
    year_number integer NOT NULL,
    ash numeric(36,16),
    so2 numeric(36,16),
    nox numeric(36,16),
    co numeric(36,16),
    pg numeric(36,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

COMMENT ON TABLE gs_eco.gs_eco_new_tes_norms IS 'Нормативы удельных выбросов расчёта по новым ТЭС (до/более 100 МВт)';

CREATE SEQUENCE gs_eco.gs_eco_new_tes_norms_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_eco.gs_eco_new_tes_norms_id_seq OWNED BY gs_eco.gs_eco_new_tes_norms.id;

CREATE TABLE gs_eco.gs_eco_operating_tes_coefficients (
    id integer NOT NULL,
    territory_slug character varying(80) NOT NULL,
    year_number integer NOT NULL,
    kind character varying(40) NOT NULL,
    value numeric(36,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    affiliation character varying(20) DEFAULT 'all'::character varying NOT NULL
);

COMMENT ON TABLE gs_eco.gs_eco_operating_tes_coefficients IS 'КПД очистки и коэффициенты подавления (лист «Коэфф.»)';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_coefficients.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_coefficients.territory_slug IS 'Идентификатор территории (vsego, minen, severo-zapad, …)';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_coefficients.year_number IS 'Год: Year.number + database_version_id (composite FK)';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_coefficients.kind IS 'Вид: ash_eta (КПД золоулавливания), sulfur_eta (КПД сероочистки), nox_n / co_k / pg_k (коэф. подавления)';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_coefficients.value IS 'Значение КПД или коэффициента подавления, д.ед. (0–1)';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_coefficients.note IS 'Примечание';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_coefficients.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_coefficients.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_coefficients.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_coefficients.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_coefficients.database_version_id IS 'Версия базы данных, FK -> gs_sys.gs_database_versions';

CREATE SEQUENCE gs_eco.gs_eco_operating_tes_coefficients_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_eco.gs_eco_operating_tes_coefficients_id_seq OWNED BY gs_eco.gs_eco_operating_tes_coefficients.id;

CREATE TABLE gs_eco.gs_eco_operating_tes_formula_texts (
    id integer NOT NULL,
    formula_key character varying(128) NOT NULL,
    formula_text text NOT NULL,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE gs_eco.gs_eco_operating_tes_formula_texts IS 'Переопределения текстов формул (подсказки «i») расчёта по действующим ТЭС';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_formula_texts.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_formula_texts.formula_key IS 'Ключ формулы (иконка «i» на страницах расчёта)';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_formula_texts.formula_text IS 'Текст формулы (подсказка; на расчёт ячеек не влияет)';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_formula_texts.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_formula_texts.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_formula_texts.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_formula_texts.updated_at IS 'Дата и время последнего изменения записи';

CREATE SEQUENCE gs_eco.gs_eco_operating_tes_formula_texts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_eco.gs_eco_operating_tes_formula_texts_id_seq OWNED BY gs_eco.gs_eco_operating_tes_formula_texts.id;

CREATE TABLE gs_eco.gs_eco_operating_tes_fuel_chars (
    id integer NOT NULL,
    fuel_key character varying(80) NOT NULL,
    year_number integer NOT NULL,
    ash numeric(36,16),
    ash_share numeric(36,16),
    q_mech numeric(36,16),
    sulfur numeric(36,16),
    sulfur_share numeric(36,16),
    qh_kj numeric(36,16),
    qh_kcal numeric(36,16),
    bj numeric(36,16),
    k_co2 numeric(36,16),
    r_chem numeric(36,16),
    q_chem numeric(36,16),
    tut_per_t numeric(36,16),
    tj_per_kt numeric(36,16),
    t_co2_per_tj numeric(36,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    source_key character varying(40),
    territory_slug character varying(40) DEFAULT 'vsego'::character varying NOT NULL
);

COMMENT ON TABLE gs_eco.gs_eco_operating_tes_fuel_chars IS 'Характеристики топлива для расчёта выбросов действующих ТЭС (лист «Хар.топл.»)';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.fuel_key IS 'Ключ вида топлива (gas_natural, mazut, donetsk, …)';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.year_number IS 'Год: Year.number + database_version_id (composite FK)';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.ash IS 'Зольность Ар, %';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.ash_share IS 'Доля золы аун, д.ед.';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.q_mech IS 'Потери тепла от механической неполноты сгорания qч, %';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.sulfur IS 'Сернистость Sp, %';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.sulfur_share IS 'Доля оксидов серы x, д.ед.';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.qh_kj IS 'Низшая теплота сгорания QH, кДж/кг';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.qh_kcal IS 'Низшая теплота сгорания QH, ккал/кг';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.bj IS 'Удельный выброс оксидов азота bj, кг/тут';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.k_co2 IS 'Национальный коэффициент эмиссии CO2 (KCO2), т/тут';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.r_chem IS 'Коэффициент доли потери тепла от химической неполноты сгорания R, %';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.q_chem IS 'Потери тепла от химической неполноты сгорания q3, %';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.tut_per_t IS 'Коэффициент перевода в условное топливо, тут/т';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.tj_per_kt IS 'Энергосодержание, ТДж/тыс. т натур. топлива';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.t_co2_per_tj IS 'Коэффициент эмиссии CO2, т СО2/ТДж';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.note IS 'Примечание';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.database_version_id IS 'Версия базы данных, FK -> gs_sys.gs_database_versions';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_fuel_chars.source_key IS 'Источник характеристик топлива листа «Справочник»: thermal / method / industry / table21 / rosstat';

CREATE SEQUENCE gs_eco.gs_eco_operating_tes_fuel_chars_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_eco.gs_eco_operating_tes_fuel_chars_id_seq OWNED BY gs_eco.gs_eco_operating_tes_fuel_chars.id;

CREATE TABLE gs_eco.gs_eco_operating_tes_inputs (
    id integer NOT NULL,
    territory_slug character varying(80) NOT NULL,
    year_number integer NOT NULL,
    row_key character varying(80) NOT NULL,
    value numeric(36,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

COMMENT ON TABLE gs_eco.gs_eco_operating_tes_inputs IS 'Сохранённые значения ввода расчёта по действующим ТЭС (топливо, выработка, тепло)';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_inputs.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_inputs.territory_slug IS 'Идентификатор территории (vsego, minen, severo-zapad, …)';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_inputs.year_number IS 'Год: Year.number + database_version_id (composite FK)';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_inputs.row_key IS 'Ключ строки: вид топлива, ee_generation, heat_output, fuel_total';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_inputs.value IS 'Значение: топливо — тыс. тут; выработка ЭЭ — млрд.кВтч; отпуск тепла — тыс.Гкал';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_inputs.note IS 'Примечание';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_inputs.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_inputs.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_inputs.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_inputs.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_eco.gs_eco_operating_tes_inputs.database_version_id IS 'Версия базы данных, FK -> gs_sys.gs_database_versions';

CREATE SEQUENCE gs_eco.gs_eco_operating_tes_inputs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_eco.gs_eco_operating_tes_inputs_id_seq OWNED BY gs_eco.gs_eco_operating_tes_inputs.id;

CREATE TABLE gs_ei.gs_ei_federal_district_population_consumption_coefficients (
    id integer NOT NULL,
    id_federal_district integer NOT NULL,
    coefficient_a numeric(25,16),
    coefficient_x numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

COMMENT ON TABLE gs_ei.gs_ei_federal_district_population_consumption_coefficients IS 'Коэффициенты A и X блока «Население» на странице электроёмкости (ФО)';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_population_consumption_coefficients.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_population_consumption_coefficients.id_federal_district IS 'Федеральный округ (FK -> gs_sys.gs_sys_federal_districts)';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_population_consumption_coefficients.coefficient_a IS 'Коэффициент A';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_population_consumption_coefficients.coefficient_x IS 'Коэффициент X';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_population_consumption_coefficients.note IS 'Примечание';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_population_consumption_coefficients.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_population_consumption_coefficients.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_population_consumption_coefficients.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_population_consumption_coefficients.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_population_consumption_coefficients.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

CREATE SEQUENCE gs_ei.gs_ec_federal_district_population_consumption_coefficien_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ei.gs_ec_federal_district_population_consumption_coefficien_id_seq OWNED BY gs_ei.gs_ei_federal_district_population_consumption_coefficients.id;

CREATE TABLE gs_ei.gs_ei_federal_district_population_consumption_year_params (
    id integer NOT NULL,
    id_federal_district integer NOT NULL,
    row_kind character varying(32) NOT NULL,
    year_number integer,
    parameter_value numeric(25,10),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

COMMENT ON TABLE gs_ei.gs_ei_federal_district_population_consumption_year_params IS 'Показатели блока «Население» по годам для федерального округа';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_population_consumption_year_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_population_consumption_year_params.id_federal_district IS 'Федеральный округ (FK -> gs_sys.gs_sys_federal_districts)';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_population_consumption_year_params.row_kind IS 'Тип строки показателя (intensity, graph_point, calculated, delta)';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_population_consumption_year_params.year_number IS 'Номер года';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_population_consumption_year_params.parameter_value IS 'Значение показателя за год (кВт·ч/чел., зависит от row_kind)';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_population_consumption_year_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_population_consumption_year_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_population_consumption_year_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_population_consumption_year_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_population_consumption_year_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_population_consumption_year_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

CREATE SEQUENCE gs_ei.gs_ec_federal_district_population_consumption_year_param_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ei.gs_ec_federal_district_population_consumption_year_param_id_seq OWNED BY gs_ei.gs_ei_federal_district_population_consumption_year_params.id;

CREATE TABLE gs_ei.gs_ei_electrical_intensity_formula_texts (
    id integer NOT NULL,
    formula_key character varying(128) NOT NULL,
    formula_text text NOT NULL,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE gs_ei.gs_ei_electrical_intensity_formula_texts IS 'Переопределения текстов формул для страницы электроёмкости';

COMMENT ON COLUMN gs_ei.gs_ei_electrical_intensity_formula_texts.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ei.gs_ei_electrical_intensity_formula_texts.formula_key IS 'Ключ формулы';

COMMENT ON COLUMN gs_ei.gs_ei_electrical_intensity_formula_texts.formula_text IS 'Текст формулы';

COMMENT ON COLUMN gs_ei.gs_ei_electrical_intensity_formula_texts.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ei.gs_ei_electrical_intensity_formula_texts.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ei.gs_ei_electrical_intensity_formula_texts.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ei.gs_ei_electrical_intensity_formula_texts.updated_at IS 'Дата и время последнего изменения записи';

CREATE SEQUENCE gs_ei.gs_ec_long_term_electrical_intensity_formula_texts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ei.gs_ec_long_term_electrical_intensity_formula_texts_id_seq OWNED BY gs_ei.gs_ei_electrical_intensity_formula_texts.id;

CREATE TABLE gs_ei.gs_ei_russia_federation_electrical_intensity_coefficients (
    id integer NOT NULL,
    coefficient_a numeric(25,16),
    coefficient_x numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

COMMENT ON TABLE gs_ei.gs_ei_russia_federation_electrical_intensity_coefficients IS 'Коэффициенты A и X электроёмкости для РФ в целом';

COMMENT ON COLUMN gs_ei.gs_ei_russia_federation_electrical_intensity_coefficients.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ei.gs_ei_russia_federation_electrical_intensity_coefficients.coefficient_a IS 'Коэффициент A';

COMMENT ON COLUMN gs_ei.gs_ei_russia_federation_electrical_intensity_coefficients.coefficient_x IS 'Коэффициент X';

COMMENT ON COLUMN gs_ei.gs_ei_russia_federation_electrical_intensity_coefficients.note IS 'Примечание';

COMMENT ON COLUMN gs_ei.gs_ei_russia_federation_electrical_intensity_coefficients.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ei.gs_ei_russia_federation_electrical_intensity_coefficients.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ei.gs_ei_russia_federation_electrical_intensity_coefficients.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ei.gs_ei_russia_federation_electrical_intensity_coefficients.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ei.gs_ei_russia_federation_electrical_intensity_coefficients.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

CREATE SEQUENCE gs_ei.gs_ec_russia_federation_electrical_intensity_coefficient_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ei.gs_ec_russia_federation_electrical_intensity_coefficient_id_seq OWNED BY gs_ei.gs_ei_russia_federation_electrical_intensity_coefficients.id;

CREATE TABLE gs_ei.gs_ei_federal_district_electrical_intensity_coefficients (
    id integer NOT NULL,
    id_federal_district integer NOT NULL,
    coefficient_a numeric(25,16),
    coefficient_x numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    id_economic_activity_type integer NOT NULL
);

COMMENT ON TABLE gs_ei.gs_ei_federal_district_electrical_intensity_coefficients IS 'Коэффициенты A и X электроёмкости для федерального округа';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_electrical_intensity_coefficients.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_electrical_intensity_coefficients.id_federal_district IS 'Федеральный округ (FK -> gs_sys.gs_sys_federal_districts)';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_electrical_intensity_coefficients.coefficient_a IS 'Коэффициент A';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_electrical_intensity_coefficients.coefficient_x IS 'Коэффициент X';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_electrical_intensity_coefficients.note IS 'Примечание';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_electrical_intensity_coefficients.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_electrical_intensity_coefficients.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_electrical_intensity_coefficients.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_electrical_intensity_coefficients.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_electrical_intensity_coefficients.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_electrical_intensity_coefficients.id_economic_activity_type IS 'Вид экономической деятельности (FK -> gs_sys.gs_sys_economic_activity_types)';

CREATE SEQUENCE gs_ei.gs_ei_federal_district_electrical_intensity_coefficients_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ei.gs_ei_federal_district_electrical_intensity_coefficients_id_seq OWNED BY gs_ei.gs_ei_federal_district_electrical_intensity_coefficients.id;

CREATE TABLE gs_ei.gs_ei_federal_district_electrical_intensity_year_params (
    id integer NOT NULL,
    id_federal_district integer NOT NULL,
    row_kind character varying(32) NOT NULL,
    year_number integer,
    parameter_value numeric(25,10),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    id_economic_activity_type integer NOT NULL
);

COMMENT ON TABLE gs_ei.gs_ei_federal_district_electrical_intensity_year_params IS 'Электроёмкость по годам для федерального округа (долгосрочный прогноз)';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_electrical_intensity_year_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_electrical_intensity_year_params.id_federal_district IS 'Федеральный округ (FK -> gs_sys.gs_sys_federal_districts)';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_electrical_intensity_year_params.row_kind IS 'Тип строки показателя (intensity, graph_point, calculated, delta)';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_electrical_intensity_year_params.year_number IS 'Номер года';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_electrical_intensity_year_params.parameter_value IS 'Значение показателя за год (кВт·ч/тыс. руб., зависит от row_kind)';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_electrical_intensity_year_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_electrical_intensity_year_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_electrical_intensity_year_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_electrical_intensity_year_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_electrical_intensity_year_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_electrical_intensity_year_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_electrical_intensity_year_params.id_economic_activity_type IS 'Вид экономической деятельности (FK -> gs_sys.gs_sys_economic_activity_types)';

CREATE SEQUENCE gs_ei.gs_ei_federal_district_electrical_intensity_year_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ei.gs_ei_federal_district_electrical_intensity_year_params_id_seq OWNED BY gs_ei.gs_ei_federal_district_electrical_intensity_year_params.id;

CREATE TABLE gs_ei.gs_ei_federal_district_fd_total_consumption_coefficients (
    id integer NOT NULL,
    id_federal_district integer NOT NULL,
    row_kind character varying(32) NOT NULL,
    coefficient_k numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

COMMENT ON TABLE gs_ei.gs_ei_federal_district_fd_total_consumption_coefficients IS 'Коэффициенты k для строк «Потери в сетях» и «С.н. электростанций» блока «Всего» по федеральным округам';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_fd_total_consumption_coefficients.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_fd_total_consumption_coefficients.id_federal_district IS 'Федеральный округ';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_fd_total_consumption_coefficients.row_kind IS 'Тип строки блока «Всего»';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_fd_total_consumption_coefficients.coefficient_k IS 'Коэффициент k';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_fd_total_consumption_coefficients.note IS 'Примечание';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_fd_total_consumption_coefficients.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_fd_total_consumption_coefficients.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_fd_total_consumption_coefficients.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_fd_total_consumption_coefficients.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ei.gs_ei_federal_district_fd_total_consumption_coefficients.database_version_id IS 'Версия базы данных';

CREATE SEQUENCE gs_ei.gs_ei_federal_district_fd_total_consumption_coefficients_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ei.gs_ei_federal_district_fd_total_consumption_coefficients_id_seq OWNED BY gs_ei.gs_ei_federal_district_fd_total_consumption_coefficients.id;

CREATE TABLE gs_ei.gs_ei_russia_federation_electrical_intensity_year_params (
    id integer NOT NULL,
    row_kind character varying(32) NOT NULL,
    year_number integer,
    parameter_value numeric(25,10),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

COMMENT ON TABLE gs_ei.gs_ei_russia_federation_electrical_intensity_year_params IS 'Электроёмкость по годам для РФ в целом (долгосрочный прогноз)';

COMMENT ON COLUMN gs_ei.gs_ei_russia_federation_electrical_intensity_year_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ei.gs_ei_russia_federation_electrical_intensity_year_params.row_kind IS 'Тип строки показателя (intensity, graph_point, calculated, delta)';

COMMENT ON COLUMN gs_ei.gs_ei_russia_federation_electrical_intensity_year_params.year_number IS 'Номер года';

COMMENT ON COLUMN gs_ei.gs_ei_russia_federation_electrical_intensity_year_params.parameter_value IS 'Значение показателя за год (кВт·ч/тыс. руб., зависит от row_kind)';

COMMENT ON COLUMN gs_ei.gs_ei_russia_federation_electrical_intensity_year_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ei.gs_ei_russia_federation_electrical_intensity_year_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ei.gs_ei_russia_federation_electrical_intensity_year_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ei.gs_ei_russia_federation_electrical_intensity_year_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ei.gs_ei_russia_federation_electrical_intensity_year_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ei.gs_ei_russia_federation_electrical_intensity_year_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

CREATE SEQUENCE gs_ei.gs_ei_russia_federation_electrical_intensity_year_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ei.gs_ei_russia_federation_electrical_intensity_year_params_id_seq OWNED BY gs_ei.gs_ei_russia_federation_electrical_intensity_year_params.id;

CREATE TABLE gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params (
    id integer NOT NULL,
    id_federal_district integer NOT NULL,
    id_economic_activity_type integer NOT NULL,
    year_number integer,
    accumulated_fixed_capital_investment_mln_rub numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

COMMENT ON TABLE gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params IS 'Накопленные инвестиции в основной капитал по ВЭД для федерального округа (долгосрочный прогноз)';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params.id_federal_district IS 'Федеральный округ (FK -> gs_sys.gs_sys_federal_districts)';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params.id_economic_activity_type IS 'Вид экономической деятельности (FK -> gs_sys.gs_sys_economic_activity_types)';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params.year_number IS 'Номер года (связь с gs_sys.gs_sys_years по number и database_version_id)';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params.accumulated_fixed_capital_investment_mln_rub IS 'Накопленные инвестиции в основной капитал, млн руб.';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

CREATE SEQUENCE gs_ekp.gs_ec_federal_district_economic_activity_accum_fixed_cap_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ekp.gs_ec_federal_district_economic_activity_accum_fixed_cap_id_seq OWNED BY gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params.id;

CREATE TABLE gs_ekp.gs_ekp_federal_district_eat_consumption_params (
    id integer NOT NULL,
    id_federal_district integer NOT NULL,
    id_economic_activity_type integer NOT NULL,
    year_number integer,
    energy_consumption_mln_kvt_ch numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

COMMENT ON TABLE gs_ekp.gs_ekp_federal_district_eat_consumption_params IS 'Потребление ЭЭ по ВЭД для федерального округа (долгосрочный прогноз)';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_eat_consumption_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_eat_consumption_params.id_federal_district IS 'Федеральный округ (FK -> gs_sys.gs_sys_federal_districts)';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_eat_consumption_params.id_economic_activity_type IS 'Вид экономической деятельности (FK -> gs_sys.gs_sys_economic_activity_types)';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_eat_consumption_params.year_number IS 'Номер года (связь с gs_sys.gs_sys_years по number и database_version_id)';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_eat_consumption_params.energy_consumption_mln_kvt_ch IS 'Потребление электроэнергии, млн кВт·ч';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_eat_consumption_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_eat_consumption_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_eat_consumption_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_eat_consumption_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_eat_consumption_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_eat_consumption_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

CREATE SEQUENCE gs_ekp.gs_ec_federal_district_economic_activity_consumption_par_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ekp.gs_ec_federal_district_economic_activity_consumption_par_id_seq OWNED BY gs_ekp.gs_ekp_federal_district_eat_consumption_params.id;

CREATE TABLE gs_ekp.gs_ekp_federal_district_product_output_params (
    id integer NOT NULL,
    id_federal_district integer NOT NULL,
    id_economic_activity_type integer NOT NULL,
    year_number integer,
    accumulated_product_output_mln_rub numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    id_year_specific_product_output integer
);

COMMENT ON TABLE gs_ekp.gs_ekp_federal_district_product_output_params IS 'Накопленный выпуск продукции по ВЭД для федерального округа (долгосрочный прогноз)';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_product_output_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_product_output_params.id_federal_district IS 'Федеральный округ (FK -> gs_sys.gs_sys_federal_districts)';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_product_output_params.id_economic_activity_type IS 'Вид экономической деятельности (FK -> gs_sys.gs_sys_economic_activity_types)';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_product_output_params.year_number IS 'Номер года (связь с gs_sys.gs_sys_years по number и database_version_id)';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_product_output_params.accumulated_product_output_mln_rub IS 'Накопленный выпуск продукции, млн руб.';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_product_output_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_product_output_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_product_output_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_product_output_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_product_output_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_product_output_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_product_output_params.id_year_specific_product_output IS 'Год цен для накопленного выпуска продукции (FK -> gs_sys.gs_sys_years)';

CREATE SEQUENCE gs_ekp.gs_ec_federal_district_economic_activity_product_output__id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ekp.gs_ec_federal_district_economic_activity_product_output__id_seq OWNED BY gs_ekp.gs_ekp_federal_district_product_output_params.id;

CREATE TABLE gs_ekp.gs_ekp_russia_federation_accum_fixed_capital_params (
    id integer NOT NULL,
    id_economic_activity_type integer NOT NULL,
    year_number integer,
    accumulated_fixed_capital_investment_mln_rub numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

COMMENT ON TABLE gs_ekp.gs_ekp_russia_federation_accum_fixed_capital_params IS 'Накопленные инвестиции в основной капитал по ВЭД для РФ в целом (долгосрочный прогноз)';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_accum_fixed_capital_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_accum_fixed_capital_params.id_economic_activity_type IS 'Вид экономической деятельности (FK -> gs_sys.gs_sys_economic_activity_types)';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_accum_fixed_capital_params.year_number IS 'Номер года (связь с gs_sys.gs_sys_years по number и database_version_id)';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_accum_fixed_capital_params.accumulated_fixed_capital_investment_mln_rub IS 'Накопленные инвестиции в основной капитал, млн руб.';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_accum_fixed_capital_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_accum_fixed_capital_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_accum_fixed_capital_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_accum_fixed_capital_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_accum_fixed_capital_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_accum_fixed_capital_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

CREATE SEQUENCE gs_ekp.gs_ec_russia_federation_economic_activity_accum_fixed_ca_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ekp.gs_ec_russia_federation_economic_activity_accum_fixed_ca_id_seq OWNED BY gs_ekp.gs_ekp_russia_federation_accum_fixed_capital_params.id;

CREATE TABLE gs_ekp.gs_ekp_russia_federation_consumption_params (
    id integer NOT NULL,
    id_economic_activity_type integer NOT NULL,
    year_number integer,
    energy_consumption_mln_kvt_ch numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

COMMENT ON TABLE gs_ekp.gs_ekp_russia_federation_consumption_params IS 'Потребление ЭЭ по ВЭД для РФ в целом (долгосрочный прогноз)';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_consumption_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_consumption_params.id_economic_activity_type IS 'Вид экономической деятельности (FK -> gs_sys.gs_sys_economic_activity_types)';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_consumption_params.year_number IS 'Номер года (связь с gs_sys.gs_sys_years по number и database_version_id)';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_consumption_params.energy_consumption_mln_kvt_ch IS 'Потребление электроэнергии, млн кВт·ч';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_consumption_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_consumption_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_consumption_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_consumption_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_consumption_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_consumption_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

CREATE SEQUENCE gs_ekp.gs_ec_russia_federation_economic_activity_consumption_pa_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ekp.gs_ec_russia_federation_economic_activity_consumption_pa_id_seq OWNED BY gs_ekp.gs_ekp_russia_federation_consumption_params.id;

CREATE TABLE gs_ekp.gs_ekp_russia_federation_product_output_params (
    id integer NOT NULL,
    id_economic_activity_type integer NOT NULL,
    year_number integer,
    accumulated_product_output_mln_rub numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    id_year_specific_product_output integer
);

COMMENT ON TABLE gs_ekp.gs_ekp_russia_federation_product_output_params IS 'Накопленный выпуск продукции по ВЭД для РФ в целом (долгосрочный прогноз)';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_product_output_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_product_output_params.id_economic_activity_type IS 'Вид экономической деятельности (FK -> gs_sys.gs_sys_economic_activity_types)';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_product_output_params.year_number IS 'Номер года (связь с gs_sys.gs_sys_years по number и database_version_id)';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_product_output_params.accumulated_product_output_mln_rub IS 'Накопленный выпуск продукции, млн руб.';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_product_output_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_product_output_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_product_output_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_product_output_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_product_output_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_product_output_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_ekp.gs_ekp_russia_federation_product_output_params.id_year_specific_product_output IS 'Год цен для накопленного выпуска продукции (FK -> gs_sys.gs_sys_years)';

CREATE SEQUENCE gs_ekp.gs_ec_russia_federation_economic_activity_product_output_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ekp.gs_ec_russia_federation_economic_activity_product_output_id_seq OWNED BY gs_ekp.gs_ekp_russia_federation_product_output_params.id;

CREATE TABLE gs_ekp.gs_ekp_accum_fixed_capital_formula_texts (
    id integer NOT NULL,
    formula_key character varying(128) NOT NULL,
    formula_text text NOT NULL,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE gs_ekp.gs_ekp_accum_fixed_capital_formula_texts IS 'Переопределения текстов формул для накопленных инвестиций в основной капитал';

COMMENT ON COLUMN gs_ekp.gs_ekp_accum_fixed_capital_formula_texts.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_accum_fixed_capital_formula_texts.formula_key IS 'Ключ формулы';

COMMENT ON COLUMN gs_ekp.gs_ekp_accum_fixed_capital_formula_texts.formula_text IS 'Текст формулы';

COMMENT ON COLUMN gs_ekp.gs_ekp_accum_fixed_capital_formula_texts.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ekp.gs_ekp_accum_fixed_capital_formula_texts.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ekp.gs_ekp_accum_fixed_capital_formula_texts.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_accum_fixed_capital_formula_texts.updated_at IS 'Дата и время последнего изменения записи';

CREATE SEQUENCE gs_ekp.gs_ekp_accum_fixed_capital_formula_texts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ekp.gs_ekp_accum_fixed_capital_formula_texts_id_seq OWNED BY gs_ekp.gs_ekp_accum_fixed_capital_formula_texts.id;

CREATE TABLE gs_ekp.gs_ekp_federal_district_accum_monetary_income_params (
    id integer NOT NULL,
    id_federal_district integer NOT NULL,
    year_number integer,
    accum_monetary_income_mln_rub numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

COMMENT ON TABLE gs_ekp.gs_ekp_federal_district_accum_monetary_income_params IS 'Накопленные денежные доходы населения по федеральному округу и году';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_accum_monetary_income_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_accum_monetary_income_params.id_federal_district IS 'Федеральный округ (FK -> gs_sys.gs_sys_federal_districts)';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_accum_monetary_income_params.year_number IS 'Номер года (связь с gs_sys.gs_sys_years по number и database_version_id)';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_accum_monetary_income_params.accum_monetary_income_mln_rub IS 'Накопленные денежные доходы населения, млн руб.';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_accum_monetary_income_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_accum_monetary_income_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_accum_monetary_income_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_accum_monetary_income_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_accum_monetary_income_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_accum_monetary_income_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

CREATE SEQUENCE gs_ekp.gs_ekp_federal_district_accum_monetary_income_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ekp.gs_ekp_federal_district_accum_monetary_income_params_id_seq OWNED BY gs_ekp.gs_ekp_federal_district_accum_monetary_income_params.id;

CREATE TABLE gs_ekp.gs_ekp_federal_district_population_params (
    id integer NOT NULL,
    id_federal_district integer NOT NULL,
    year_number integer,
    population_thousand_persons numeric(25,16),
    note text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

COMMENT ON TABLE gs_ekp.gs_ekp_federal_district_population_params IS 'Численность населения по федеральному округу и году (долгосрочный прогноз)';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_population_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_population_params.id_federal_district IS 'Федеральный округ (FK -> gs_sys.gs_sys_federal_districts)';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_population_params.year_number IS 'Номер года (связь с gs_sys.gs_sys_years по number и database_version_id)';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_population_params.population_thousand_persons IS 'Численность населения, тыс. чел.';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_population_params.note IS 'Примечание';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_population_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_population_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_population_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_population_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_federal_district_population_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

CREATE SEQUENCE gs_ekp.gs_ekp_federal_district_population_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ekp.gs_ekp_federal_district_population_params_id_seq OWNED BY gs_ekp.gs_ekp_federal_district_population_params.id;

CREATE TABLE gs_ekp.gs_ekp_product_output_formula_texts (
    id integer NOT NULL,
    formula_key character varying(128) NOT NULL,
    formula_text text NOT NULL,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE gs_ekp.gs_ekp_product_output_formula_texts IS 'Переопределения текстов формул для выпуска продукции (долгосрочный прогноз)';

COMMENT ON COLUMN gs_ekp.gs_ekp_product_output_formula_texts.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_product_output_formula_texts.formula_key IS 'Ключ формулы';

COMMENT ON COLUMN gs_ekp.gs_ekp_product_output_formula_texts.formula_text IS 'Текст формулы';

COMMENT ON COLUMN gs_ekp.gs_ekp_product_output_formula_texts.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ekp.gs_ekp_product_output_formula_texts.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ekp.gs_ekp_product_output_formula_texts.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_product_output_formula_texts.updated_at IS 'Дата и время последнего изменения записи';

CREATE SEQUENCE gs_ekp.gs_ekp_product_output_formula_texts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ekp.gs_ekp_product_output_formula_texts_id_seq OWNED BY gs_ekp.gs_ekp_product_output_formula_texts.id;

CREATE TABLE gs_ekp.gs_ekp_ved_consumption_formula_texts (
    id integer NOT NULL,
    formula_key character varying(128) NOT NULL,
    formula_text text NOT NULL,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE gs_ekp.gs_ekp_ved_consumption_formula_texts IS 'Переопределения текстов формул для потребления ЭЭ по ВЭД (долгосрочный прогноз)';

COMMENT ON COLUMN gs_ekp.gs_ekp_ved_consumption_formula_texts.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_ved_consumption_formula_texts.formula_key IS 'Ключ формулы';

COMMENT ON COLUMN gs_ekp.gs_ekp_ved_consumption_formula_texts.formula_text IS 'Текст формулы';

COMMENT ON COLUMN gs_ekp.gs_ekp_ved_consumption_formula_texts.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ekp.gs_ekp_ved_consumption_formula_texts.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ekp.gs_ekp_ved_consumption_formula_texts.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ekp.gs_ekp_ved_consumption_formula_texts.updated_at IS 'Дата и время последнего изменения записи';

CREATE SEQUENCE gs_ekp.gs_ekp_ved_consumption_formula_texts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ekp.gs_ekp_ved_consumption_formula_texts_id_seq OWNED BY gs_ekp.gs_ekp_ved_consumption_formula_texts.id;

CREATE TABLE gs_fue.gs_fue_allocatable_heat (
    id integer NOT NULL,
    scope character varying(8) DEFAULT 'oes'::character varying NOT NULL,
    code integer NOT NULL,
    year_number integer NOT NULL,
    q_ras numeric(36,16),
    prirost numeric(36,16),
    hs numeric(36,16),
    ri numeric(36,16),
    database_version_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE gs_fue.gs_fue_allocatable_heat_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue.gs_fue_allocatable_heat_id_seq OWNED BY gs_fue.gs_fue_allocatable_heat.id;

CREATE TABLE gs_fue.gs_fue_distribution_coefficient_summaries (
    id integer NOT NULL,
    distribution_parameter_id integer NOT NULL,
    year_number integer NOT NULL,
    base_year integer,
    database_version_id integer,
    bnust numeric(20,6),
    be numeric(20,6),
    betp numeric(20,6),
    bq numeric(20,6),
    bqotr numeric(20,6),
    cnust numeric(20,6),
    cnustn numeric(20,6),
    cnustngt numeric(20,6),
    cnustnpg numeric(20,6),
    cnustnps numeric(20,6),
    cetp numeric(20,6),
    cq numeric(20,6),
    cqotr numeric(20,6),
    bptp numeric(20,6),
    cptp numeric(20,6),
    bh numeric(20,6),
    ch numeric(20,6),
    ph1 numeric(20,6),
    pe numeric(20,6),
    hd numeric(20,6),
    kn numeric(20,6),
    ph numeric(20,6),
    pq numeric(20,6),
    potr numeric(20,6),
    e_target numeric(20,6),
    k numeric(20,6),
    kplus numeric(20,6),
    kmin numeric(20,6),
    knps numeric(20,6),
    kngt numeric(20,6),
    knpg numeric(20,6),
    hnps numeric(20,6),
    hngt numeric(20,6),
    hnpg numeric(20,6),
    doptim numeric(20,6),
    lim numeric(20,6),
    note text
);

COMMENT ON TABLE gs_fue.gs_fue_distribution_coefficient_summaries IS 'Агрегированный результат этапа «Коэфф» по параметру распределения';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.distribution_parameter_id IS 'Параметр распределения';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.year_number IS 'Номер года';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.base_year IS 'Базовый год (номер)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.bnust IS 'Сумма установленной мощности (N_уст), базовый год, МВт';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.be IS 'Сумма выработки электроэнергии (E), базовый год';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.betp IS 'Сумма теплофикационной выработки (Этц), базовый год';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.bq IS 'Сумма отпуска тепла (Q), базовый год';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.bqotr IS 'Сумма тепла на отработку (Q_отр), базовый год';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.cnust IS 'Сумма установленной мощности (N_уст), расчётный год, МВт';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.cnustn IS 'Сумма мощности новых агрегатов (N_нов), расчётный год, МВт';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.cnustngt IS 'Мощность нового газотурбинного оборудования, расчётный год, МВт';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.cnustnpg IS 'Мощность нового парогазового оборудования, расчётный год, МВт';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.cnustnps IS 'Мощность нового паросилового оборудования, расчётный год, МВт';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.cetp IS 'Сумма теплофикационной выработки (Этц), расчётный год';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.cq IS 'Сумма отпуска тепла (Q), расчётный год';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.cqotr IS 'Сумма тепла на отработку (Q_отр), расчётный год';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.bptp IS 'Доля тепла в электроэнергии, %, базовый год';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.cptp IS 'Доля тепла в электроэнергии, %, расчётный год';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.bh IS 'Удельные часы (Н), базовый год';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.ch IS 'Удельные часы (Н), расчётный год';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.ph1 IS 'Вспомогательный показатель удельных часов (PH1)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.pe IS 'Отношение выработки E (расчётный/базовый год)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.hd IS 'Удельные часы на действующую часть парка (hd)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.kn IS 'Коэффициент загрузки нового оборудования (расчётный)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.ph IS 'Удельные часы на действующую часть парка (PH)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.pq IS 'Отношение отпуска тепла Q (расчётный/базовый год)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.potr IS 'Отношение тепла на отработку (расчётный/базовый год)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.e_target IS 'Целевая выработка электроэнергии (E_целевое)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.k IS 'Коэффициент загрузки';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.kplus IS 'Верхняя граница коэффициента загрузки (k+)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.kmin IS 'Нижняя граница коэффициента загрузки (k−)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.knps IS 'Коэффициент загрузки нового паросилового оборудования (расчётный)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.kngt IS 'Коэффициент загрузки нового газотурбинного оборудования (расчётный)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.knpg IS 'Коэффициент загрузки нового парогазового оборудования (расчётный)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.hnps IS 'ЧЧИУМ нового паросилового оборудования';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.hngt IS 'ЧЧИУМ нового газотурбинного оборудования';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.hnpg IS 'ЧЧИУМ нового парогазового оборудования';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.doptim IS 'Коэффициент допустимого отклонения';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.lim IS 'Наличие ограничений по выработке для РЭС';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_coefficient_summaries.note IS 'Примечание';

CREATE SEQUENCE gs_fue.gs_fue_distribution_coefficient_summaries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue.gs_fue_distribution_coefficient_summaries_id_seq OWNED BY gs_fue.gs_fue_distribution_coefficient_summaries.id;

CREATE TABLE gs_fue.gs_fue_distribution_parameters (
    id integer NOT NULL,
    filter_text text,
    e numeric(36,16),
    kplus numeric(36,16),
    kmin numeric(36,16),
    k numeric(36,16),
    bkl numeric(36,16),
    wname character varying(255),
    uname character varying(255),
    toplname character varying(255),
    dopname character varying(255),
    kn numeric(36,16),
    knps numeric(36,16),
    kngt numeric(36,16),
    knpg numeric(36,16),
    hnps numeric(36,16),
    hngt numeric(36,16),
    hnpg numeric(36,16),
    numb numeric(36,16),
    doptim numeric(36,16),
    lim integer,
    database_version_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    id_union_energy_system integer,
    id_year integer NOT NULL,
    id_base_year integer,
    ref_uuid character varying(36)
);

COMMENT ON TABLE gs_fue.gs_fue_distribution_parameters IS 'Параметры распределения (аналог таблицы «Параметры-распределения» из Access)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.filter_text IS 'Текст фильтра / можно потому удалить';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.e IS 'Выработка ТЭС';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.kplus IS 'Верхняя граница коэффициента загрузки (k+)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.kmin IS 'Нижняя граница коэффициента загрузки (k−)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.k IS 'Коэффициент загрузки';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.bkl IS 'Вспомогательный номер территоррии для распределения выработки по станциям ОЭС';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.wname IS 'Наименование таблицы с обобщенными показателями по станциям';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.uname IS 'Наименование таблицы с удельными технико-экономическими показателями работы групп оборудования';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.toplname IS 'Название таблицы со структурой топливного баланса групп оборудования';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.dopname IS 'Наименование таблицы с детализацией видов топлива';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.kn IS 'Коэффициент загрузки нового оборудования (расчётный)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.knps IS 'Коэффициент загрузки нового паросилового оборудования (расчётный)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.kngt IS 'Коэффициент загрузки нового газотурбинного оборудования (расчётный)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.knpg IS 'Коэффициент загрузки нового парогазового оборудования (расчётный)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.hnps IS 'ЧЧИУМ нового паросилового оборудования';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.hngt IS 'ЧЧИУМ нового газотурбинного оборудования';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.hnpg IS 'ЧЧИУМ нового парогазового оборудования';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.numb IS 'Порядковый номер';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.doptim IS 'Коэффициент допустимого отклонения';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.lim IS 'Наличие ограничений по выработке для РЭС';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.id_union_energy_system IS 'Объединенная энергосистема';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.id_year IS 'Расчитываемый год (id_year)';

COMMENT ON COLUMN gs_fue.gs_fue_distribution_parameters.id_base_year IS 'Базовый год';

CREATE SEQUENCE gs_fue.gs_fue_distribution_parameters_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue.gs_fue_distribution_parameters_id_seq OWNED BY gs_fue.gs_fue_distribution_parameters.id;

CREATE TABLE gs_fue.gs_fue_equipment_group_coefficient_results (
    id integer NOT NULL,
    equipment_group_id integer NOT NULL,
    distribution_parameter_id integer NOT NULL,
    year_number integer NOT NULL,
    database_version_id integer,
    k numeric(20,6),
    kplus numeric(20,6),
    kmin numeric(20,6),
    kn numeric(20,6),
    knps numeric(20,6),
    kngt numeric(20,6),
    knpg numeric(20,6),
    hnps numeric(20,6),
    hngt numeric(20,6),
    hnpg numeric(20,6),
    doptim numeric(20,6),
    lim numeric(20,6),
    coeff_base numeric(20,6),
    coeff_min numeric(20,6),
    coeff_max numeric(20,6),
    coeff_effective numeric(20,6),
    note text
);

COMMENT ON TABLE gs_fue.gs_fue_equipment_group_coefficient_results IS 'Снимок результатов этапа «Коэфф» для группы оборудования и параметра распределения';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_coefficient_results.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_coefficient_results.equipment_group_id IS 'Группа оборудования (FK -> gs_fue.gs_fue_equipment_groups)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_coefficient_results.distribution_parameter_id IS 'Параметр распределения (FK -> gs_fue.gs_fue_distribution_parameters)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_coefficient_results.year_number IS 'Номер года';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_coefficient_results.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_coefficient_results.k IS 'Входные коэффициенты параметра распределения (копия/снимок)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_coefficient_results.kplus IS 'Верхняя граница коэффициента загрузки (k+)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_coefficient_results.kmin IS 'Нижняя граница коэффициента загрузки (k−)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_coefficient_results.kn IS 'Коэффициент загрузки нового оборудования (расчётный)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_coefficient_results.knps IS 'Коэффициент загрузки нового паросилового оборудования (расчётный)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_coefficient_results.kngt IS 'Коэффициент загрузки нового газотурбинного оборудования (расчётный)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_coefficient_results.knpg IS 'Коэффициент загрузки нового парогазового оборудования (расчётный)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_coefficient_results.hnps IS 'ЧЧИУМ нового паросилового оборудования';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_coefficient_results.hngt IS 'ЧЧИУМ нового газотурбинного оборудования';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_coefficient_results.hnpg IS 'ЧЧИУМ нового парогазового оборудования';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_coefficient_results.doptim IS 'Коэффициент допустимого отклонения';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_coefficient_results.lim IS 'Наличие ограничений по выработке для РЭС';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_coefficient_results.coeff_base IS 'Базовый коэффициент загрузки (этап «Коэфф»)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_coefficient_results.coeff_min IS 'Нижняя граница коэффициента загрузки (этап «Коэфф»)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_coefficient_results.coeff_max IS 'Верхняя граница коэффициента загрузки (этап «Коэфф»)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_coefficient_results.coeff_effective IS 'Эффективный коэффициент загрузки (этап «Коэфф»)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_coefficient_results.note IS 'Примечание';

CREATE SEQUENCE gs_fue.gs_fue_equipment_group_coefficient_results_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue.gs_fue_equipment_group_coefficient_results_id_seq OWNED BY gs_fue.gs_fue_equipment_group_coefficient_results.id;

CREATE TABLE gs_fue.gs_fue_equipment_group_electricity_production_cost (
    id integer NOT NULL,
    equipment_group_id integer,
    name character varying(512),
    year_number integer,
    cost_code integer,
    zatraty_sum numeric(36,16),
    zatr_e numeric(36,16),
    zatr_p numeric(36,16),
    zatr_q numeric(36,16),
    numb1120 integer,
    database_version_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE gs_fue.gs_fue_equipment_group_electricity_production_cost_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue.gs_fue_equipment_group_electricity_production_cost_id_seq OWNED BY gs_fue.gs_fue_equipment_group_electricity_production_cost.id;

CREATE TABLE gs_fue.gs_fue_equipment_group_extra_fuel_param (
    id integer NOT NULL,
    equipment_group_id integer,
    name character varying(512),
    year_number integer,
    gaz_prir numeric(36,16),
    gazpp numeric(36,16),
    disel numeric(36,16),
    maztop numeric(36,16),
    gtt numeric(36,16),
    nft_proch numeric(36,16),
    domen_g numeric(36,16),
    koks_g numeric(36,16),
    prochgaz numeric(36,16),
    tvproch numeric(36,16),
    szh_gaz numeric(36,16),
    inoe numeric(36,16),
    nazar numeric(36,16),
    ibor numeric(36,16),
    berez numeric(36,16),
    per numeric(36,16),
    irbei numeric(36,16),
    kansk numeric(36,16),
    gusin numeric(36,16),
    tugn numeric(36,16),
    okino numeric(36,16),
    azey numeric(36,16),
    mug numeric(36,16),
    cher numeric(36,16),
    jer numeric(36,16),
    karab numeric(36,16),
    vork numeric(36,16),
    intin numeric(36,16),
    sver numeric(36,16),
    chel numeric(36,16),
    kizel numeric(36,16),
    har numeric(36,16),
    urt numeric(36,16),
    tataur numeric(36,16),
    tarbag numeric(36,16),
    zab_kam numeric(36,16),
    rai numeric(36,16),
    erk numeric(36,16),
    ogodj numeric(36,16),
    svo numeric(36,16),
    bikin numeric(36,16),
    razdol numeric(36,16),
    hankai numeric(36,16),
    neru numeric(36,16),
    zyryan numeric(36,16),
    pyak numeric(36,16),
    kuzngd numeric(36,16),
    kuznt numeric(36,16),
    kuznss numeric(36,16),
    kuznun numeric(36,16),
    bering numeric(36,16),
    anad numeric(36,16),
    ekib numeric(36,16),
    maikub numeric(36,16),
    karag numeric(36,16),
    karajyra numeric(36,16),
    teniz numeric(36,16),
    numb1120 integer,
    numb1 integer,
    database_version_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    sosv numeric(36,16),
    luch numeric(36,16),
    tal numeric(36,16)
);

COMMENT ON TABLE gs_fue.gs_fue_equipment_group_extra_fuel_param IS 'EquipmentGroupExtraFuelParam model — дополнительные топливные параметры групп оборудования';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.equipment_group_id IS 'Группа оборудования (FK -> gs_fue.gs_fue_equipment_groups)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.name IS 'Наименование';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.year_number IS 'Номер года';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.gaz_prir IS 'газ естественный природный';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.gazpp IS 'газ естественный попутный';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.disel IS 'топливо дизельное';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.maztop IS 'мазут топочный';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.gtt IS 'Газотурбинное топливо';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.nft_proch IS 'нефтетопливо прочее';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.domen_g IS 'газ искусственный доменный';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.koks_g IS 'газ искусственный коксовый';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.prochgaz IS 'газ НПЗ';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.tvproch IS 'прочие виды твердого топлива';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.szh_gaz IS 'газ сжиженный';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.inoe IS 'Иное топливо';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.nazar IS 'уголь назаровский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.ibor IS 'уголь бородинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.berez IS 'уголь березовский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.per IS 'уголь переясловский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.irbei IS 'уголь ирбейский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.kansk IS 'уголь канский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.gusin IS 'уголь гусиноозерский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.tugn IS 'уголь тугнуйский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.okino IS 'уголь разреза Окино-Ключевской';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.azey IS 'уголь азейский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.mug IS 'уголь мугунский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.cher IS 'уголь черемховский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.jer IS 'уголь жеронский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.karab IS 'уголь карабульский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.vork IS 'уголь воркутинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.intin IS 'уголь интинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.sver IS 'уголь свердловский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.chel IS 'уголь челябинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.kizel IS 'уголь кизеловский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.har IS 'уголь харанорский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.urt IS 'уголь уртуйский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.tataur IS 'уголь татауровский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.tarbag IS 'уголь тарбагатайский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.zab_kam IS 'уголь забайкальский каменный';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.rai IS 'уголь райчихинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.erk IS 'уголь ерковецкий';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.ogodj IS 'уголь огоджинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.svo IS 'уголь свободненский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.bikin IS 'уголь бикинский (лучегорский)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.razdol IS 'уголь раздольненский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.hankai IS 'уголь ханкайский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.neru IS 'уголь нерюнгринский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.zyryan IS 'уголь зырянский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.pyak IS 'уголь якутский прочий';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.kuzngd IS 'уголь кузнецкий марки Г, Д';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.kuznt IS 'уголь кузнецкий марки Т';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.kuznss IS 'уголь кузнецкий марки СС';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.kuznun IS 'уголь кузнецкий прочий';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.bering IS 'уголь беринговский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.anad IS 'уголь анадырский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.ekib IS 'уголь экибастузский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.maikub IS 'уголь майкубенский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.karag IS 'уголь карагандинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.karajyra IS 'уголь разреза Каражыра (Казахстан)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.teniz IS 'уголь тениз-коржункольский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.numb1120 IS 'Код электростанции';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.numb1 IS 'Номер';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.sosv IS 'Доп. поля по аналогии с Access (детализация углей)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.luch IS 'Лучегорское (уголь)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_extra_fuel_param.tal IS 'уголь таловский';

CREATE SEQUENCE gs_fue.gs_fue_equipment_group_extra_fuel_param_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue.gs_fue_equipment_group_extra_fuel_param_id_seq OWNED BY gs_fue.gs_fue_equipment_group_extra_fuel_param.id;

CREATE TABLE gs_fue.gs_fue_equipment_group_fuel_formula (
    id integer NOT NULL,
    equipment_group_id integer NOT NULL,
    name character varying(512),
    year_number integer NOT NULL,
    variant_number integer DEFAULT 0 NOT NULL,
    numb1120 integer,
    numb1 numeric(36,16),
    formtxt text,
    database_version_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE gs_fue.gs_fue_equipment_group_fuel_formula IS 'EquipmentGroupFuelFormula — формулы топлива для группы оборудования';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_formula.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_formula.equipment_group_id IS 'Группа оборудования (FK -> gs_fue.gs_fue_equipment_groups)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_formula.name IS 'Наименование';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_formula.year_number IS 'Номер года';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_formula.variant_number IS 'Аналог поля v из Access';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_formula.numb1120 IS 'Код электростанции';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_formula.numb1 IS 'Номер';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_formula.formtxt IS 'Текст формулы топлива';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_formula.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_formula.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_formula.updated_at IS 'Дата и время последнего изменения записи';

CREATE SEQUENCE gs_fue.gs_fue_equipment_group_fuel_formula_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue.gs_fue_equipment_group_fuel_formula_id_seq OWNED BY gs_fue.gs_fue_equipment_group_fuel_formula.id;

CREATE TABLE gs_fue.gs_fue_equipment_group_fuel_param (
    id integer NOT NULL,
    equipment_group_id integer NOT NULL,
    name character varying(512),
    year_number integer,
    nust numeric(36,16),
    nr numeric(36,16),
    e numeric(36,16),
    ewtp numeric(36,16),
    eotp numeric(36,16),
    eurt numeric(36,16),
    eust numeric(36,16),
    snk numeric(36,16),
    q numeric(36,16),
    qotr numeric(36,16),
    turt numeric(36,16),
    tust numeric(36,16),
    sn_t numeric(36,16),
    b numeric(36,16),
    gaz numeric(36,16),
    isk_gaz numeric(36,16),
    mazut numeric(36,16),
    torf numeric(36,16),
    slan numeric(36,16),
    proch numeric(36,16),
    ugol numeric(36,16),
    don numeric(36,16),
    podm numeric(36,16),
    pech numeric(36,16),
    arkt numeric(36,16),
    kuzn numeric(36,16),
    ural numeric(36,16),
    bashk numeric(36,16),
    kazah numeric(36,16),
    kan numeric(36,16),
    tung numeric(36,16),
    irkut numeric(36,16),
    hak numeric(36,16),
    tuv numeric(36,16),
    bur numeric(36,16),
    chit numeric(36,16),
    yakut numeric(36,16),
    amur numeric(36,16),
    urg numeric(36,16),
    ushum numeric(36,16),
    prim numeric(36,16),
    mag numeric(36,16),
    chukot numeric(36,16),
    kamch numeric(36,16),
    sah numeric(36,16),
    nt numeric(36,16),
    nt_sum numeric(36,16),
    numb1120 integer,
    numb1 integer,
    obor integer,
    ved integer,
    "вед" integer,
    obl character varying(80),
    dep character varying(80),
    oes character varying(80),
    ees integer,
    er character varying(80),
    gk character varying(80),
    be character varying(80),
    database_version_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    h numeric(36,16),
    hfix integer,
    sn_ee numeric(36,16),
    sn_te numeric(36,16)
);

COMMENT ON TABLE gs_fue.gs_fue_equipment_group_fuel_param IS 'EquipmentGroupFuelParam model — топливные параметры для группы оборудования';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.equipment_group_id IS 'Группа оборудования (FK -> gs_fue.gs_fue_equipment_groups)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.name IS 'Наименование группы оборудования';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.year_number IS 'Ссылка на год (number из gs_sys_years). Без FK: gs_sys_years.number не уникален (дубли по версиям).';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.nust IS 'Мощность: Руст';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.nr IS 'Ррасп';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.e IS 'Электроэнергия в тыс.кВтч: Выр';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.ewtp IS 'Этц';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.eotp IS 'Отпуск ЭЭ, тыс.кВтч';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.eurt IS 'Уд.расх';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.eust IS 'Расх топ ээ';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.snk IS 'СН, %';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.q IS 'Тепло в Гкал: Отпуск, Гкал';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.qotr IS 'Отраб';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.turt IS 'Уд.расх';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.tust IS 'Расх топ тэ';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.sn_t IS 'СН, кВтч/Гкал';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.b IS 'Расх топл.';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.gaz IS 'Расх по типам топлива';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.isk_gaz IS 'газ искусственный (прочие виды)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.mazut IS 'Мазут';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.torf IS 'торф';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.slan IS 'сланцы';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.proch IS 'Прочее';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.ugol IS 'Уголь';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.don IS 'уголь донецкий';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.podm IS 'уголь подмосковный';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.pech IS 'уголь печорский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.arkt IS 'уголь арктический';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.kuzn IS 'уголь кузнецкий';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.ural IS 'уголь уральский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.bashk IS 'уголь башкирский (южно-уральский)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.kazah IS 'угли Казахстана';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.kan IS 'уголь канско-ачинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.tung IS 'уголь тунгусский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.irkut IS 'уголь иркутский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.hak IS 'уголь хакасский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.tuv IS 'уголь тувинский (улуг-хемский)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.bur IS 'уголь бурятский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.chit IS 'уголь забайкальский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.yakut IS 'уголь якутский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.amur IS 'уголь амурский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.urg IS 'уголь ургальский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.ushum IS 'уголь ушумунский (средне-амурский)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.prim IS 'уголь приморский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.mag IS 'уголь магаданский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.chukot IS 'уголь чукотский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.kamch IS 'уголь камчатский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.sah IS 'уголь сахалинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.nt IS 'Тепл. мощн. отборов';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.nt_sum IS 'Сумма тепловых мощностей';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.numb1120 IS 'Код электростанции';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.numb1 IS 'Номер';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.obor IS 'FK -> EquipmentGroupExternalMapping.code';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.ved IS 'Ведомство (ved)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param."вед" IS 'Ведомство (вед)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.obl IS 'FK -> TerritoriesEnergyExternalMapping.external_id';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.dep IS 'FK -> DepartmentExternalMapping.external_id';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.oes IS 'FK -> UnionEnergySystemExternalMapping.external_id';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.ees IS 'Энергосистема (ees)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.er IS 'FK -> EconomicRegionExternalMapping.external_id';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.gk IS 'FK -> GenCompanyExternalMapping.external_id';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.be IS 'FK -> BusinessUnitExternalMapping.external_id';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.database_version_id IS 'Поле для связи с версией БД';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.sn_ee IS 'СН на производство электроэнергии, тыс. кВт·ч (числитель snk)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_fuel_param.sn_te IS 'СН на отпуск тепловой энергии, тыс. кВт·ч (числитель sn_t / SNT)';

CREATE SEQUENCE gs_fue.gs_fue_equipment_group_fuel_param_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue.gs_fue_equipment_group_fuel_param_id_seq OWNED BY gs_fue.gs_fue_equipment_group_fuel_param.id;

CREATE TABLE gs_fue.gs_fue_equipment_group_heat_and_tariffs (
    id integer NOT NULL,
    equipment_group_id integer,
    kod_goroda integer,
    name_goroda character varying(255),
    var_razv integer,
    name_eto text,
    numb1120 integer,
    ndv_st integer,
    year_number integer,
    q numeric(36,16),
    tarif numeric(36,16),
    database_version_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE gs_fue.gs_fue_equipment_group_heat_and_tariffs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue.gs_fue_equipment_group_heat_and_tariffs_id_seq OWNED BY gs_fue.gs_fue_equipment_group_heat_and_tariffs.id;

CREATE TABLE gs_fue.gs_fue_equipment_group_natural_fuel (
    id integer NOT NULL,
    equipment_group_id integer,
    name character varying(512),
    year_number integer,
    gaz numeric(36,16),
    gazpp numeric(36,16),
    gaz_prir numeric(36,16),
    isk_gaz numeric(36,16),
    domen_g numeric(36,16),
    koks_g numeric(36,16),
    prochgaz numeric(36,16),
    mazut numeric(36,16),
    disel numeric(36,16),
    maztop numeric(36,16),
    gtt numeric(36,16),
    nft_proch numeric(36,16),
    torf numeric(36,16),
    gtd numeric(36,16),
    slan numeric(36,16),
    proch numeric(36,16),
    tvproch numeric(36,16),
    szh_gaz numeric(36,16),
    inoe numeric(36,16),
    ugol numeric(36,16),
    don numeric(36,16),
    podm numeric(36,16),
    vork numeric(36,16),
    intin numeric(36,16),
    pech numeric(36,16),
    arkt numeric(36,16),
    kuzn numeric(36,16),
    kuzngd numeric(36,16),
    kuznt numeric(36,16),
    kuznss numeric(36,16),
    kuznun numeric(36,16),
    ural numeric(36,16),
    sver numeric(36,16),
    chel numeric(36,16),
    kizel numeric(36,16),
    bashk numeric(36,16),
    kazah numeric(36,16),
    ekib numeric(36,16),
    maikub numeric(36,16),
    karag numeric(36,16),
    karajyra numeric(36,16),
    teniz numeric(36,16),
    kan numeric(36,16),
    nazar numeric(36,16),
    ibor numeric(36,16),
    berez numeric(36,16),
    per numeric(36,16),
    irbei numeric(36,16),
    kansk numeric(36,16),
    irkut numeric(36,16),
    azey numeric(36,16),
    mug numeric(36,16),
    cher numeric(36,16),
    tung numeric(36,16),
    jer numeric(36,16),
    karab numeric(36,16),
    hak numeric(36,16),
    tuv numeric(36,16),
    bur numeric(36,16),
    gusin numeric(36,16),
    tugn numeric(36,16),
    okino numeric(36,16),
    chit numeric(36,16),
    har numeric(36,16),
    urt numeric(36,16),
    tataur numeric(36,16),
    tarbag numeric(36,16),
    zab_kam numeric(36,16),
    yakut numeric(36,16),
    neru numeric(36,16),
    zyryan numeric(36,16),
    pyak numeric(36,16),
    amur numeric(36,16),
    rai numeric(36,16),
    erk numeric(36,16),
    ogodj numeric(36,16),
    svo numeric(36,16),
    urg numeric(36,16),
    ushum numeric(36,16),
    prim numeric(36,16),
    bikin numeric(36,16),
    razdol numeric(36,16),
    hankai numeric(36,16),
    mag numeric(36,16),
    chukot numeric(36,16),
    bering numeric(36,16),
    anad numeric(36,16),
    kamch numeric(36,16),
    sah numeric(36,16),
    obl integer,
    dep integer,
    oes integer,
    er integer,
    numb1120 integer,
    numb1 integer,
    database_version_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE gs_fue.gs_fue_equipment_group_natural_fuel_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue.gs_fue_equipment_group_natural_fuel_id_seq OWNED BY gs_fue.gs_fue_equipment_group_natural_fuel.id;

CREATE TABLE gs_fue.gs_fue_equipment_group_sets (
    id integer NOT NULL,
    equipment_group_id integer NOT NULL,
    equipment_group_set_station_id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE gs_fue.gs_fue_equipment_group_sets IS 'EquipmentGroupSet model (link между итоговой группой и связкой станция+тип)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_sets.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_sets.equipment_group_id IS 'Группа оборудования (FK -> gs_fue.gs_fue_equipment_groups)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_sets.equipment_group_set_station_id IS 'Связка станция+тип группы (FK -> gs_fue.gs_fue_equipment_group_type_stations)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_sets.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_sets.updated_at IS 'Дата и время последнего изменения записи';

ALTER TABLE gs_fue.gs_fue_equipment_group_sets ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME gs_fue.gs_fue_equipment_group_sets_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

CREATE TABLE gs_fue.gs_fue_equipment_group_specific_fuel_consumption (
    id integer NOT NULL,
    equipment_group_id integer,
    name character varying(512),
    year_number integer,
    y numeric(36,16),
    btp numeric(36,16),
    sntp numeric(36,16),
    bk numeric(36,16),
    numb1120 integer,
    snk numeric(36,16),
    database_version_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    y_calc numeric(36,16),
    btp_calc numeric(36,16),
    sntp_calc numeric(36,16),
    bk_calc numeric(36,16),
    snk_calc numeric(36,16),
    k numeric(10,4),
    bbas numeric(36,16),
    snbas numeric(36,16),
    ksn numeric(36,16),
    kh numeric(36,16)
);

COMMENT ON TABLE gs_fue.gs_fue_equipment_group_specific_fuel_consumption IS 'EquipmentGroupSpecificFuelConsumption model — удельные показатели групп оборудования';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_consumption.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_consumption.equipment_group_id IS 'Группа оборудования (FK -> gs_fue.gs_fue_equipment_groups)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_consumption.name IS 'Наименование';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_consumption.year_number IS 'Номер года';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_consumption.y IS 'Удельная выработка ЭЭ на тепловом потреблении, кВтч/⁠Гкал';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_consumption.btp IS 'УРУТ на отпуск ЭЭ в теплофикационном режиме, г у.т./кВтч';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_consumption.sntp IS 'Эл.энергия на собственные нужды  в теплофик.режиме';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_consumption.bk IS 'УРУТ на отпуск ЭЭ в конденсационном режиме, г у.т./кВтч';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_consumption.numb1120 IS 'Код электростанции';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_consumption.snk IS 'Собственные нужды на выработку электроэнергии';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_consumption.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_consumption.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_consumption.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_consumption.y_calc IS 'Удельная выработка ЭЭ на тепловом потреблении, кВтч/⁠Гкал';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_consumption.btp_calc IS 'УРУТ на отпуск ЭЭ в теплофикационном режиме, г у.т./кВтч';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_consumption.sntp_calc IS 'Эл.энергия на собственные нужды  в теплофик.режиме';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_consumption.bk_calc IS 'УРУТ на отпуск ЭЭ в конденсационном режиме, г у.т./кВтч';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_consumption.snk_calc IS 'Собственные нужды на выработку электроэнергии';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_consumption.k IS 'Коэффициент экономии от теплофикации (привязан к году). Numeric для дробных (1.5, 0.7)';

CREATE SEQUENCE gs_fue.gs_fue_equipment_group_specific_fuel_consumption_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue.gs_fue_equipment_group_specific_fuel_consumption_id_seq OWNED BY gs_fue.gs_fue_equipment_group_specific_fuel_consumption.id;

CREATE TABLE gs_fue.gs_fue_equipment_group_specific_fuel_cost (
    id integer NOT NULL,
    equipment_group_id integer,
    name character varying(512),
    year_number integer,
    gaz numeric(36,16),
    gaz_prir numeric(36,16),
    gazpp numeric(36,16),
    mazut numeric(36,16),
    disel numeric(36,16),
    maztop numeric(36,16),
    gtt numeric(36,16),
    nft_proch numeric(36,16),
    torf numeric(36,16),
    isk_gaz numeric(36,16),
    domen_g numeric(36,16),
    koks_g numeric(36,16),
    prochgaz numeric(36,16),
    proch numeric(36,16),
    tvproch numeric(36,16),
    szh_gaz numeric(36,16),
    inoe numeric(36,16),
    ugol numeric(36,16),
    don numeric(36,16),
    podm numeric(36,16),
    pech numeric(36,16),
    vork numeric(36,16),
    intin numeric(36,16),
    kuzn numeric(36,16),
    kuzngd numeric(36,16),
    kuznt numeric(36,16),
    kuznss numeric(36,16),
    kuznun numeric(36,16),
    ural numeric(36,16),
    sver numeric(36,16),
    chel numeric(36,16),
    kizel numeric(36,16),
    bashk numeric(36,16),
    kazah numeric(36,16),
    ekib numeric(36,16),
    maikub numeric(36,16),
    karag numeric(36,16),
    karajyra numeric(36,16),
    teniz numeric(36,16),
    kan numeric(36,16),
    nazar numeric(36,16),
    ibor numeric(36,16),
    berez numeric(36,16),
    per numeric(36,16),
    irbei numeric(36,16),
    kansk numeric(36,16),
    irkut numeric(36,16),
    azey numeric(36,16),
    mug numeric(36,16),
    cher numeric(36,16),
    tung numeric(36,16),
    jer numeric(36,16),
    karab numeric(36,16),
    hak numeric(36,16),
    tuv numeric(36,16),
    bur numeric(36,16),
    gusin numeric(36,16),
    tugn numeric(36,16),
    okino numeric(36,16),
    chit numeric(36,16),
    har numeric(36,16),
    urt numeric(36,16),
    tataur numeric(36,16),
    tarbag numeric(36,16),
    zab_kam numeric(36,16),
    amur numeric(36,16),
    rai numeric(36,16),
    erk numeric(36,16),
    ogodj numeric(36,16),
    svo numeric(36,16),
    urg numeric(36,16),
    ushum numeric(36,16),
    prim numeric(36,16),
    bikin numeric(36,16),
    razdol numeric(36,16),
    hankai numeric(36,16),
    yakut numeric(36,16),
    neru numeric(36,16),
    zyryan numeric(36,16),
    pyak numeric(36,16),
    mag numeric(36,16),
    chukot numeric(36,16),
    anad numeric(36,16),
    bering numeric(36,16),
    kamch numeric(36,16),
    sah numeric(36,16),
    ved integer,
    obl character varying(80),
    dep character varying(80),
    oes character varying(80),
    er character varying(80),
    numb1120 integer,
    numb1 integer,
    database_version_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE gs_fue.gs_fue_equipment_group_specific_fuel_cost IS 'EquipmentGroupSpecificFuelCost model — стоимость для групп оборудования';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.equipment_group_id IS 'Группа оборудования (FK -> gs_fue.gs_fue_equipment_groups)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.name IS 'Наименование';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.year_number IS 'Номер года';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.gaz IS 'Топливные поля (Numeric для стоимостей)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.gaz_prir IS 'газ естественный природный';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.gazpp IS 'газ естественный попутный';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.mazut IS 'Мазут';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.disel IS 'топливо дизельное';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.maztop IS 'мазут топочный';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.gtt IS 'Газотурбинное топливо';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.nft_proch IS 'нефтетопливо прочее';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.torf IS 'торф';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.isk_gaz IS 'газ искусственный (прочие виды)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.domen_g IS 'газ искусственный доменный';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.koks_g IS 'газ искусственный коксовый';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.prochgaz IS 'газ НПЗ';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.proch IS 'Прочее';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.tvproch IS 'прочие виды твердого топлива';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.szh_gaz IS 'газ сжиженный';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.inoe IS 'Иное топливо';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.ugol IS 'Уголь';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.don IS 'уголь донецкий';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.podm IS 'уголь подмосковный';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.pech IS 'уголь печорский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.vork IS 'уголь воркутинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.intin IS 'уголь интинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.kuzn IS 'уголь кузнецкий';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.kuzngd IS 'уголь кузнецкий марки Г, Д';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.kuznt IS 'уголь кузнецкий марки Т';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.kuznss IS 'уголь кузнецкий марки СС';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.kuznun IS 'уголь кузнецкий прочий';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.ural IS 'уголь уральский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.sver IS 'уголь свердловский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.chel IS 'уголь челябинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.kizel IS 'уголь кизеловский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.bashk IS 'уголь башкирский (южно-уральский)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.kazah IS 'угли Казахстана';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.ekib IS 'уголь экибастузский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.maikub IS 'уголь майкубенский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.karag IS 'уголь карагандинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.karajyra IS 'уголь разреза Каражыра (Казахстан)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.teniz IS 'уголь тениз-коржункольский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.kan IS 'уголь канско-ачинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.nazar IS 'уголь назаровский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.ibor IS 'уголь бородинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.berez IS 'уголь березовский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.per IS 'уголь переясловский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.irbei IS 'уголь ирбейский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.kansk IS 'уголь канский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.irkut IS 'уголь иркутский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.azey IS 'уголь азейский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.mug IS 'уголь мугунский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.cher IS 'уголь черемховский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.tung IS 'уголь тунгусский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.jer IS 'уголь жеронский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.karab IS 'уголь карабульский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.hak IS 'уголь хакасский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.tuv IS 'уголь тувинский (улуг-хемский)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.bur IS 'уголь бурятский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.gusin IS 'уголь гусиноозерский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.tugn IS 'уголь тугнуйский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.okino IS 'уголь разреза Окино-Ключевской';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.chit IS 'уголь забайкальский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.har IS 'уголь харанорский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.urt IS 'уголь уртуйский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.tataur IS 'уголь татауровский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.tarbag IS 'уголь тарбагатайский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.zab_kam IS 'уголь забайкальский каменный';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.amur IS 'уголь амурский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.rai IS 'уголь райчихинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.erk IS 'уголь ерковецкий';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.ogodj IS 'уголь огоджинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.svo IS 'уголь свободненский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.urg IS 'уголь ургальский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.ushum IS 'уголь ушумунский (средне-амурский)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.prim IS 'уголь приморский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.bikin IS 'уголь бикинский (лучегорский)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.razdol IS 'уголь раздольненский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.hankai IS 'уголь ханкайский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.yakut IS 'уголь якутский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.neru IS 'уголь нерюнгринский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.zyryan IS 'уголь зырянский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.pyak IS 'уголь якутский прочий';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.mag IS 'уголь магаданский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.chukot IS 'уголь чукотский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.anad IS 'уголь анадырский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.bering IS 'уголь беринговский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.kamch IS 'уголь камчатский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.sah IS 'уголь сахалинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.ved IS 'Служебные поля';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.obl IS 'Код субъекта РФ (внешний идентификатор)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.dep IS 'Код департамента (внешний идентификатор)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.oes IS 'Код ОЭС (внешний идентификатор)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.er IS 'Код экономического района (внешний идентификатор)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.numb1120 IS 'Код электростанции';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.numb1 IS 'Номер';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_cost.updated_at IS 'Дата и время последнего изменения записи';

CREATE SEQUENCE gs_fue.gs_fue_equipment_group_specific_fuel_cost_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue.gs_fue_equipment_group_specific_fuel_cost_id_seq OWNED BY gs_fue.gs_fue_equipment_group_specific_fuel_cost.id;

CREATE TABLE gs_fue.gs_fue_equipment_group_specific_fuel_price (
    id integer NOT NULL,
    equipment_group_id integer,
    name character varying(512),
    year_number integer,
    obl character varying(80),
    gaz_c numeric(36,16),
    gazpp_c numeric(36,16),
    gaz_prir_c numeric(36,16),
    mazut_c numeric(36,16),
    disel_c numeric(36,16),
    maztop_c numeric(36,16),
    gtt_c numeric(36,16),
    nft_proch_c numeric(36,16),
    torf_c numeric(36,16),
    isk_gaz_c numeric(36,16),
    domen_g_c numeric(36,16),
    koks_g_c numeric(36,16),
    prochgaz_c numeric(36,16),
    proch_c numeric(36,16),
    tvproch_c numeric(36,16),
    szh_gaz_c numeric(36,16),
    inoe_c numeric(36,16),
    don_c numeric(36,16),
    podm_c numeric(36,16),
    pech_c numeric(36,16),
    vork_c numeric(36,16),
    intin_c numeric(36,16),
    kuzn_c numeric(36,16),
    kuzngd_c numeric(36,16),
    kuznt_c numeric(36,16),
    kuznss_c numeric(36,16),
    kuznun_c numeric(36,16),
    ural_c numeric(36,16),
    sver_c numeric(36,16),
    chel_c numeric(36,16),
    kizel_c numeric(36,16),
    bashk_c numeric(36,16),
    kazah_c numeric(36,16),
    ekib_c numeric(36,16),
    maikub_c numeric(36,16),
    karag_c numeric(36,16),
    karajyra_c numeric(36,16),
    teniz_c numeric(36,16),
    kan_c numeric(36,16),
    nazar_c numeric(36,16),
    ibor_c numeric(36,16),
    berez_c numeric(36,16),
    per_c numeric(36,16),
    irbei_c numeric(36,16),
    kansk_c numeric(36,16),
    irkut_c numeric(36,16),
    azey_c numeric(36,16),
    mug_c numeric(36,16),
    cher_c numeric(36,16),
    tung_c numeric(36,16),
    jer_c numeric(36,16),
    karab_c numeric(36,16),
    hak_c numeric(36,16),
    tuv_c numeric(36,16),
    bur_c numeric(36,16),
    gusin_c numeric(36,16),
    tugn_c numeric(36,16),
    okino_c numeric(36,16),
    chit_c numeric(36,16),
    har_c numeric(36,16),
    urt_c numeric(36,16),
    tataur_c numeric(36,16),
    tarbag_c numeric(36,16),
    zab_kam_c numeric(36,16),
    amur_c numeric(36,16),
    rai_c numeric(36,16),
    erk_c numeric(36,16),
    ogodj_c numeric(36,16),
    svo_c numeric(36,16),
    urg_c numeric(36,16),
    ushum_c numeric(36,16),
    prim_c numeric(36,16),
    bikin_c numeric(36,16),
    razdol_c numeric(36,16),
    hankai_c numeric(36,16),
    yakut_c numeric(36,16),
    neru_c numeric(36,16),
    zyryan_c numeric(36,16),
    pyak_c numeric(36,16),
    mag_c numeric(36,16),
    chukot_c numeric(36,16),
    anad_c numeric(36,16),
    bering_c numeric(36,16),
    kamch_c numeric(36,16),
    sah_c numeric(36,16),
    numb1120 integer,
    sost character varying(80),
    "group" character varying(80),
    database_version_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE gs_fue.gs_fue_equipment_group_specific_fuel_price IS 'EquipmentGroupSpecificFuelPrice model — цена для групп оборудования';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.equipment_group_id IS 'Группа оборудования (FK -> gs_fue.gs_fue_equipment_groups)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.name IS 'Наименование';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.year_number IS 'Номер года';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.obl IS 'Код субъекта РФ (внешний идентификатор)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.gaz_c IS 'Цена, газ (всего)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.gazpp_c IS 'Цена, газ естественный попутный';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.gaz_prir_c IS 'Цена, газ естественный природный';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.mazut_c IS 'Цена, Мазут';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.disel_c IS 'Цена, топливо дизельное';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.maztop_c IS 'Цена, мазут топочный';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.gtt_c IS 'Цена, Газотурбинное топливо';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.nft_proch_c IS 'Цена, нефтетопливо прочее';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.torf_c IS 'Цена, торф';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.isk_gaz_c IS 'Цена, газ искусственный (прочие виды)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.domen_g_c IS 'Цена, газ искусственный доменный';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.koks_g_c IS 'Цена, газ искусственный коксовый';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.prochgaz_c IS 'Цена, газ НПЗ';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.proch_c IS 'Цена, Прочее';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.tvproch_c IS 'Цена, прочие виды твердого топлива';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.szh_gaz_c IS 'Цена, газ сжиженный';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.inoe_c IS 'Цена, Иное топливо';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.don_c IS 'Цена, уголь донецкий';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.podm_c IS 'Цена, уголь подмосковный';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.pech_c IS 'Цена, уголь печорский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.vork_c IS 'Цена, уголь воркутинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.intin_c IS 'Цена, уголь интинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.kuzn_c IS 'Цена, уголь кузнецкий';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.kuzngd_c IS 'Цена, уголь кузнецкий марки Г, Д';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.kuznt_c IS 'Цена, уголь кузнецкий марки Т';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.kuznss_c IS 'Цена, уголь кузнецкий марки СС';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.kuznun_c IS 'Цена, уголь кузнецкий прочий';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.ural_c IS 'Цена, уголь уральский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.sver_c IS 'Цена, уголь свердловский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.chel_c IS 'Цена, уголь челябинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.kizel_c IS 'Цена, уголь кизеловский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.bashk_c IS 'Цена, уголь башкирский (южно-уральский)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.kazah_c IS 'Цена, угли Казахстана';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.ekib_c IS 'Цена, уголь экибастузский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.maikub_c IS 'Цена, уголь майкубенский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.karag_c IS 'Цена, уголь карагандинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.karajyra_c IS 'Цена, уголь разреза Каражыра (Казахстан)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.teniz_c IS 'Цена, уголь тениз-коржункольский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.kan_c IS 'Цена, уголь канско-ачинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.nazar_c IS 'Цена, уголь назаровский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.ibor_c IS 'Цена, уголь бородинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.berez_c IS 'Цена, уголь березовский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.per_c IS 'Цена, уголь переясловский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.irbei_c IS 'Цена, уголь ирбейский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.kansk_c IS 'Цена, уголь канский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.irkut_c IS 'Цена, уголь иркутский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.azey_c IS 'Цена, уголь азейский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.mug_c IS 'Цена, уголь мугунский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.cher_c IS 'Цена, уголь черемховский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.tung_c IS 'Цена, уголь тунгусский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.jer_c IS 'Цена, уголь жеронский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.karab_c IS 'Цена, уголь карабульский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.hak_c IS 'Цена, уголь хакасский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.tuv_c IS 'Цена, уголь тувинский (улуг-хемский)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.bur_c IS 'Цена, уголь бурятский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.gusin_c IS 'Цена, уголь гусиноозерский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.tugn_c IS 'Цена, уголь тугнуйский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.okino_c IS 'Цена, уголь разреза Окино-Ключевской';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.chit_c IS 'Цена, уголь забайкальский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.har_c IS 'Цена, уголь харанорский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.urt_c IS 'Цена, уголь уртуйский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.tataur_c IS 'Цена, уголь татауровский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.tarbag_c IS 'Цена, уголь тарбагатайский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.zab_kam_c IS 'Цена, уголь забайкальский каменный';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.amur_c IS 'Цена, уголь амурский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.rai_c IS 'Цена, уголь райчихинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.erk_c IS 'Цена, уголь ерковецкий';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.ogodj_c IS 'Цена, уголь огоджинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.svo_c IS 'Цена, уголь свободненский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.urg_c IS 'Цена, уголь ургальский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.ushum_c IS 'Цена, уголь ушумунский (средне-амурский)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.prim_c IS 'Цена, уголь приморский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.bikin_c IS 'Цена, уголь бикинский (лучегорский)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.razdol_c IS 'Цена, уголь раздольненский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.hankai_c IS 'Цена, уголь ханкайский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.yakut_c IS 'Цена, уголь якутский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.neru_c IS 'Цена, уголь нерюнгринский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.zyryan_c IS 'Цена, уголь зырянский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.pyak_c IS 'Цена, уголь якутский прочий';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.mag_c IS 'Цена, уголь магаданский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.chukot_c IS 'Цена, уголь чукотский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.anad_c IS 'Цена, уголь анадырский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.bering_c IS 'Цена, уголь беринговский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.kamch_c IS 'Цена, уголь камчатский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.sah_c IS 'Цена, уголь сахалинский';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.numb1120 IS 'Служебные поля';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.sost IS 'Состав/группа цен (sost из Access)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price."group" IS 'Группа цен (sost/group из Access)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_specific_fuel_price.updated_at IS 'Дата и время последнего изменения записи';

CREATE SEQUENCE gs_fue.gs_fue_equipment_group_specific_fuel_price_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue.gs_fue_equipment_group_specific_fuel_price_id_seq OWNED BY gs_fue.gs_fue_equipment_group_specific_fuel_price.id;

CREATE TABLE gs_fue.gs_fue_equipment_group_type_stations (
    id integer NOT NULL,
    station_id integer,
    equipment_group_type_id integer,
    database_version_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE gs_fue.gs_fue_equipment_group_type_stations IS 'EquipmentGroupSetStation model (привязка типа группы оборудования к электростанции)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_type_stations.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_type_stations.station_id IS 'Электростанция (FK -> gs_gen.gs_gen_stations)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_type_stations.equipment_group_type_id IS 'Тип группы оборудования (FK -> gs_sys.gs_sys_equipment_groups)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_type_stations.database_version_id IS 'Поле для связи с версией БД';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_type_stations.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_group_type_stations.updated_at IS 'Дата и время последнего изменения записи';

CREATE SEQUENCE gs_fue.gs_fue_equipment_group_type_stations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue.gs_fue_equipment_group_type_stations_id_seq OWNED BY gs_fue.gs_fue_equipment_group_type_stations.id;

CREATE TABLE gs_fue.gs_fue_equipment_groups (
    id integer NOT NULL,
    name character varying(255),
    name_ext character varying(255),
    niv integer,
    comp integer,
    main integer,
    d integer,
    r integer,
    forem integer,
    vedomstvo integer,
    obl integer,
    dep integer,
    id_department integer,
    oes integer,
    er integer,
    fo integer,
    numb integer,
    tm character varying(255),
    n1 character varying(255),
    n2 character varying(255),
    p1 character varying(255),
    p2 character varying(255),
    ordnumb character varying(255),
    addr character varying(255),
    note character varying(1000),
    codegor integer,
    be integer,
    gk integer,
    gkf integer,
    database_version_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    regional_district_id integer,
    regional_energy_system_id integer,
    external_code character varying(36) NOT NULL,
    energy_unit_id integer
);

COMMENT ON TABLE gs_fue.gs_fue_equipment_groups IS 'EquipmentGroup model (итоговая группа оборудования)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.name IS 'Пользовательский идентификатор/название группы';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.name_ext IS 'Название (БД Топливо)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.niv IS 'Признак группы оборудования';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.comp IS 'Признак электростанции, разбитой на группы оборудования';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.main IS 'Код электростанции, в которую входит группа оборудования';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.d IS 'Признак действующей электростанции';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.r IS 'Признак расширяемой электростанции';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.forem IS 'Признак ФОРЭМ';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.vedomstvo IS 'Ведомство';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.obl IS 'Код субъекта РФ (FK -> TerritoriesEnergyExternalMapping.external_id)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.dep IS 'Код департамента (FK -> DepartmentExternalMapping)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.id_department IS 'Департамент (FK -> gs_sys.gs_sys_departments)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.oes IS 'Код ОЭС (FK -> UnionEnergySystemExternalMapping.external_id)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.er IS 'Код экономического района (FK -> EconomicRegionExternalMapping.external_id)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.fo IS 'Код федерального округа (FK -> FederalDistrictExternalMapping.external_id)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.numb IS 'Код электростанции';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.tm IS 'Название типов турбин, которое соответствует коду (необязательное)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.n1 IS 'Мощность блока в группе оборудования_вариант 1';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.n2 IS 'Мощность блока в группе оборудования_вариант 2';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.p1 IS 'Давление пара перед турбиной_вариант 1';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.p2 IS 'Давление пара перед турбиной_вариант 2';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.ordnumb IS 'Порядковый номер электростанции';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.addr IS 'Адрес';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.note IS 'Примечание';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.codegor IS 'cast для совместимости, если в БД один из столбцов VARCHAR';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.be IS 'Тип генерирующей компании (FK -> BusinessUnitExternalMapping.external_id)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.gk IS 'Код генерирующей компании (FK -> GenCompanyExternalMapping.external_id)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.gkf IS 'Код филиала генерирующей компании (связь по external_id -> GenCompanyBranchExternalMapping, без FK в БД)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.database_version_id IS 'Поле для связи с версией БД';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.regional_district_id IS 'Субъект РФ (FK -> gs_sys.gs_sys_regional_districts)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.regional_energy_system_id IS 'Региональная энергосистема (FK -> gs_sys.gs_sys_regional_energy_systems)';

COMMENT ON COLUMN gs_fue.gs_fue_equipment_groups.external_code IS 'Внешний код (UUID)';

CREATE SEQUENCE gs_fue.gs_fue_equipment_groups_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue.gs_fue_equipment_groups_id_seq OWNED BY gs_fue.gs_fue_equipment_groups.id;

CREATE TABLE gs_fue.gs_fue_fixed_heat (
    id integer NOT NULL,
    numb1120 integer NOT NULL,
    database_version_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE gs_fue.gs_fue_fixed_heat_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue.gs_fue_fixed_heat_id_seq OWNED BY gs_fue.gs_fue_fixed_heat.id;

CREATE TABLE gs_fue.gs_fue_formula_texts (
    id integer NOT NULL,
    formula_key character varying(128) NOT NULL,
    formula_text text NOT NULL,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE gs_fue.gs_fue_formula_texts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue.gs_fue_formula_texts_id_seq OWNED BY gs_fue.gs_fue_formula_texts.id;

CREATE TABLE gs_fue.gs_fue_machine_fuel_param (
    id integer NOT NULL,
    machine_id integer NOT NULL,
    numb1120 integer,
    numb integer,
    stnumb integer,
    yearin integer,
    dem integer,
    nt numeric(12,6),
    grcode integer,
    note character varying(255),
    stname character varying(80),
    opesname character varying(80),
    database_version_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    equipment_group_id integer
);

COMMENT ON TABLE gs_fue.gs_fue_machine_fuel_param IS 'MachineFuelParam model — привязка топливных данных агрегата к Machine';

COMMENT ON COLUMN gs_fue.gs_fue_machine_fuel_param.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_fue.gs_fue_machine_fuel_param.machine_id IS 'Энергоблок (FK -> gs_gen.gs_gen_machines)';

COMMENT ON COLUMN gs_fue.gs_fue_machine_fuel_param.numb1120 IS 'Код электростанции';

COMMENT ON COLUMN gs_fue.gs_fue_machine_fuel_param.numb IS 'Порядковый номер';

COMMENT ON COLUMN gs_fue.gs_fue_machine_fuel_param.stnumb IS 'Номер агрегата';

COMMENT ON COLUMN gs_fue.gs_fue_machine_fuel_param.yearin IS 'Год ввода в эксплуатацию';

COMMENT ON COLUMN gs_fue.gs_fue_machine_fuel_param.dem IS 'Год демонтажа';

COMMENT ON COLUMN gs_fue.gs_fue_machine_fuel_param.nt IS 'Тепловая мощность отборов, Гкал/ч';

COMMENT ON COLUMN gs_fue.gs_fue_machine_fuel_param.grcode IS 'Код группы оборудования (без связи с моделью)';

COMMENT ON COLUMN gs_fue.gs_fue_machine_fuel_param.note IS 'Примечание';

COMMENT ON COLUMN gs_fue.gs_fue_machine_fuel_param.stname IS 'Название электростанции';

COMMENT ON COLUMN gs_fue.gs_fue_machine_fuel_param.opesname IS 'Тип (марка) оборудования';

COMMENT ON COLUMN gs_fue.gs_fue_machine_fuel_param.database_version_id IS 'Поле для связи с версией БД';

COMMENT ON COLUMN gs_fue.gs_fue_machine_fuel_param.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_fue.gs_fue_machine_fuel_param.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_fue.gs_fue_machine_fuel_param.equipment_group_id IS 'Группа оборудования (FK -> gs_fue.gs_fue_equipment_groups)';

CREATE SEQUENCE gs_fue.gs_fue_machine_topl_agr_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue.gs_fue_machine_topl_agr_id_seq OWNED BY gs_fue.gs_fue_machine_fuel_param.id;

CREATE TABLE gs_fue.gs_fue_restrictions (
    id integer NOT NULL,
    year numeric(36,16),
    oes numeric(36,16),
    name character varying(50),
    obl numeric(36,16),
    emin numeric(36,16),
    emax numeric(36,16),
    ecur numeric(36,16),
    h numeric(36,16),
    ecurdis numeric(36,16),
    hdis numeric(36,16),
    etp numeric(36,16),
    kobl numeric(36,16),
    kcur character varying(50),
    database_version_id integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE gs_fue.gs_fue_restrictions IS 'Ограничения (аналог таблицы «Ограничения» из Access, см';

COMMENT ON COLUMN gs_fue.gs_fue_restrictions.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_fue.gs_fue_restrictions.year IS 'Год (в Access — double)';

COMMENT ON COLUMN gs_fue.gs_fue_restrictions.oes IS 'Код ОЭС (oes)';

COMMENT ON COLUMN gs_fue.gs_fue_restrictions.name IS 'Наименование';

COMMENT ON COLUMN gs_fue.gs_fue_restrictions.obl IS 'Код субъекта РФ (obl)';

COMMENT ON COLUMN gs_fue.gs_fue_restrictions.emin IS 'Минимальная выработка (emin)';

COMMENT ON COLUMN gs_fue.gs_fue_restrictions.emax IS 'Максимальная выработка (emax)';

COMMENT ON COLUMN gs_fue.gs_fue_restrictions.ecur IS 'Текущая выработка (ecur)';

COMMENT ON COLUMN gs_fue.gs_fue_restrictions.h IS 'Поле H в Access';

COMMENT ON COLUMN gs_fue.gs_fue_restrictions.ecurdis IS 'Текущая выработка с учётом ограничения (ecurdis)';

COMMENT ON COLUMN gs_fue.gs_fue_restrictions.hdis IS 'H с учётом ограничения (hdis)';

COMMENT ON COLUMN gs_fue.gs_fue_restrictions.etp IS 'Выработка Этц (etp)';

COMMENT ON COLUMN gs_fue.gs_fue_restrictions.kobl IS 'Коэффициент по субъекту (kobl)';

COMMENT ON COLUMN gs_fue.gs_fue_restrictions.kcur IS 'Текущий коэффициент (kcur)';

COMMENT ON COLUMN gs_fue.gs_fue_restrictions.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_fue.gs_fue_restrictions.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_fue.gs_fue_restrictions.updated_at IS 'Дата и время последнего изменения записи';

CREATE SEQUENCE gs_fue.gs_fue_restrictions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue.gs_fue_restrictions_id_seq OWNED BY gs_fue.gs_fue_restrictions.id;

CREATE TABLE gs_fue_em.gs_fue_em_business_unit (
    id integer NOT NULL,
    external_id character varying(80) NOT NULL,
    external_name character varying(255),
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_fue_em.gs_fue_em_business_unit IS 'Внешние идентификаторы бизнес-единиц из топливного модуля';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_business_unit.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_business_unit.external_id IS 'Внешний идентификатор бизнес-единицы';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_business_unit.external_name IS 'Внешнее наименование бизнес-единицы';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_business_unit.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_business_unit.modified_by IS 'Пользователь, последним изменивший запись';

CREATE SEQUENCE gs_fue_em.gs_fue_em_business_unit_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue_em.gs_fue_em_business_unit_id_seq OWNED BY gs_fue_em.gs_fue_em_business_unit.id;

CREATE TABLE gs_fue_em.gs_fue_em_cities (
    id integer NOT NULL,
    code integer NOT NULL,
    name character varying(255),
    naselenie numeric(18,2),
    gilfond numeric(18,2),
    obesp_cts character varying(255),
    dprom_ao integer,
    dgkh_ao integer,
    obl integer,
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_fue_em.gs_fue_em_cities IS 'Справочник городов из БД «Топливо»';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_cities.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_cities.code IS 'Внешний код города из БД «Топливо»';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_cities.name IS 'Наименование города из БД «Топливо»';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_cities.naselenie IS 'Население города';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_cities.gilfond IS 'Жилищный фонд города';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_cities.obesp_cts IS 'Обеспеченность ЦТС (значение из БД Топливо)';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_cities.dprom_ao IS 'ПРОМ, АО (код/признак из БД Топливо)';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_cities.dgkh_ao IS 'ЖКХ, АО (код/признак из БД Топливо)';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_cities.obl IS 'Внешний код территории для связи с территориальным маппингом';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_cities.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_cities.modified_by IS 'Пользователь, последним изменивший запись';

CREATE SEQUENCE gs_fue_em.gs_fue_em_cities_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue_em.gs_fue_em_cities_id_seq OWNED BY gs_fue_em.gs_fue_em_cities.id;

CREATE TABLE gs_fue_em.gs_fue_em_department (
    external_id character varying(80) NOT NULL,
    external_name character varying(255),
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_fue_em.gs_fue_em_department IS 'Внешние идентификаторы департаментов из топливного модуля';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_department.external_id IS 'Внешний идентификатор департамента';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_department.external_name IS 'Внешнее наименование департамента';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_department.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_department.modified_by IS 'Пользователь, последним изменивший запись';

CREATE TABLE gs_fue_em.gs_fue_em_economic_region (
    id integer NOT NULL,
    external_id character varying(80),
    external_name character varying(255),
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_fue_em.gs_fue_em_economic_region IS 'Внешние идентификаторы экономических районов из топливного модуля';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_economic_region.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_economic_region.external_id IS 'Внешний идентификатор экономического района';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_economic_region.external_name IS 'Внешнее наименование экономического района';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_economic_region.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_economic_region.modified_by IS 'Пользователь, последним изменивший запись';

CREATE SEQUENCE gs_fue_em.gs_fue_em_economic_region_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue_em.gs_fue_em_economic_region_id_seq OWNED BY gs_fue_em.gs_fue_em_economic_region.id;

CREATE TABLE gs_fue_em.gs_fue_em_equipment_group (
    id integer NOT NULL,
    equipment_group_ref_uuid character varying(36),
    name_topl character varying(255),
    code integer,
    type integer,
    tm character varying(255),
    n1 integer,
    n2 integer,
    p1 integer,
    p2 integer,
    gruppa_oborud character varying(255),
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_fue_em.gs_fue_em_equipment_group IS 'Внешние идентификаторы и параметры типов групп оборудования из БД «Топливо»';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_equipment_group.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_equipment_group.equipment_group_ref_uuid IS 'UUID локального типа группы оборудования для сопоставления';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_equipment_group.name_topl IS 'Наименование группы оборудования из БД «Топливо»';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_equipment_group.code IS 'Внешний код группы оборудования из БД «Топливо»';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_equipment_group.type IS 'Внешний показатель `type` из БД «Топливо»';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_equipment_group.tm IS 'Название типов турбин из БД «Топливо»';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_equipment_group.n1 IS 'Мощность блока в группе оборудования, вариант 1';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_equipment_group.n2 IS 'Мощность блока в группе оборудования, вариант 2';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_equipment_group.p1 IS 'Давление пара перед турбиной, вариант 1';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_equipment_group.p2 IS 'Давление пара перед турбиной, вариант 2';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_equipment_group.gruppa_oborud IS 'Внешний показатель группы оборудования из БД «Топливо»';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_equipment_group.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_equipment_group.modified_by IS 'Пользователь, последним изменивший запись';

CREATE SEQUENCE gs_fue_em.gs_fue_em_equipment_group_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue_em.gs_fue_em_equipment_group_id_seq OWNED BY gs_fue_em.gs_fue_em_equipment_group.id;

CREATE TABLE gs_fue_em.gs_fue_em_federal_district (
    id integer NOT NULL,
    federal_district_ref_uuid character varying(36),
    external_id character varying(80),
    external_name character varying(255),
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_fue_em.gs_fue_em_federal_district IS 'Внешние идентификаторы федеральных округов из топливного модуля';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_federal_district.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_federal_district.federal_district_ref_uuid IS 'UUID федерального округа для сопоставления';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_federal_district.external_id IS 'Внешний идентификатор федерального округа';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_federal_district.external_name IS 'Внешнее наименование федерального округа';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_federal_district.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_federal_district.modified_by IS 'Пользователь, последним изменивший запись';

CREATE SEQUENCE gs_fue_em.gs_fue_em_federal_district_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue_em.gs_fue_em_federal_district_id_seq OWNED BY gs_fue_em.gs_fue_em_federal_district.id;

CREATE TABLE gs_fue_em.gs_fue_em_gen_company (
    id integer NOT NULL,
    gen_company_ref_uuid character varying(36),
    external_id character varying(80),
    external_name character varying(255),
    external_name1 character varying(255),
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_fue_em.gs_fue_em_gen_company IS 'Внешние идентификаторы генерирующих компаний из топливного модуля';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_gen_company.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_gen_company.gen_company_ref_uuid IS 'UUID генерирующей компании для сопоставления';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_gen_company.external_id IS 'Внешний идентификатор генерирующей компании';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_gen_company.external_name IS 'Внешнее наименование генерирующей компании';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_gen_company.external_name1 IS 'Дополнительное внешнее наименование генерирующей компании';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_gen_company.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_gen_company.modified_by IS 'Пользователь, последним изменивший запись';

CREATE TABLE gs_fue_em.gs_fue_em_gen_company_branch (
    id integer NOT NULL,
    gen_company_ref_uuid character varying(36),
    external_id character varying(80),
    external_name character varying(255),
    local_name character varying(255),
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_fue_em.gs_fue_em_gen_company_branch IS 'Внешние идентификаторы филиалов генерирующих компаний из топливного модуля';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_gen_company_branch.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_gen_company_branch.gen_company_ref_uuid IS 'UUID генерирующей компании для сопоставления филиала';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_gen_company_branch.external_id IS 'Внешний идентификатор филиала генерирующей компании';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_gen_company_branch.external_name IS 'Внешнее наименование филиала генерирующей компании';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_gen_company_branch.local_name IS 'Локальное наименование для сопоставления с `GenCompany.name`';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_gen_company_branch.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_gen_company_branch.modified_by IS 'Пользователь, последним изменивший запись';

CREATE SEQUENCE gs_fue_em.gs_fue_em_gen_company_branch_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue_em.gs_fue_em_gen_company_branch_id_seq OWNED BY gs_fue_em.gs_fue_em_gen_company_branch.id;

CREATE SEQUENCE gs_fue_em.gs_fue_em_gen_company_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue_em.gs_fue_em_gen_company_id_seq OWNED BY gs_fue_em.gs_fue_em_gen_company.id;

CREATE TABLE gs_fue_em.gs_fue_em_territories_energy (
    id integer NOT NULL,
    regional_district_ref_uuid character varying(36),
    regional_energy_system_ref_uuid character varying(36),
    energy_zone_ref_uuid character varying(36),
    name_ext character varying(255),
    ao character varying(255),
    obl integer,
    alph integer,
    dep integer,
    oes integer,
    er integer,
    terr_belyaev integer,
    teo90 integer,
    fo integer,
    abbr character varying(255),
    reu character varying(255),
    pter character varying(255),
    keyword character varying(255),
    created_by character varying(255),
    modified_by character varying(255),
    external_id character varying(80),
    external_name character varying(255)
);

COMMENT ON TABLE gs_fue_em.gs_fue_em_territories_energy IS 'Внешние территориальные идентификаторы для субъектов РФ, РЭС и энергозон из топливного модуля';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_territories_energy.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_territories_energy.regional_district_ref_uuid IS 'UUID субъекта РФ для сопоставления';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_territories_energy.regional_energy_system_ref_uuid IS 'UUID РЭС для сопоставления';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_territories_energy.energy_zone_ref_uuid IS 'UUID энергозоны для сопоставления';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_territories_energy.name_ext IS 'Внешнее наименование из БД «Топливо»';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_territories_energy.ao IS 'АО (значение из БД Топливо)';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_territories_energy.obl IS 'Внешний код субъекта РФ из БД «Топливо»';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_territories_energy.alph IS 'Alph (код из БД Топливо)';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_territories_energy.dep IS 'Внешний код департамента из БД «Топливо»';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_territories_energy.oes IS 'Внешний код ОЭС из БД «Топливо»';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_territories_energy.er IS 'Внешний код экономического района из БД «Топливо»';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_territories_energy.terr_belyaev IS 'terr_belyaev (код территории из БД Топливо)';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_territories_energy.teo90 IS 'teo90 (код/классификатор из БД Топливо)';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_territories_energy.fo IS 'Внешний код федерального округа из БД «Топливо»';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_territories_energy.abbr IS 'Внешняя аббревиатура территории из БД «Топливо»';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_territories_energy.reu IS 'РЭУ (значение из БД Топливо)';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_territories_energy.pter IS 'pter (значение из БД Топливо)';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_territories_energy.keyword IS 'Внешнее ключевое слово территории из БД «Топливо»';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_territories_energy.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_territories_energy.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_territories_energy.external_id IS 'Внешний территориальный код для связей';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_territories_energy.external_name IS 'Внешнее наименование территории для отображения';

CREATE SEQUENCE gs_fue_em.gs_fue_em_territories_energy_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue_em.gs_fue_em_territories_energy_id_seq OWNED BY gs_fue_em.gs_fue_em_territories_energy.id;

CREATE TABLE gs_fue_em.gs_fue_em_union_energy_system (
    id integer NOT NULL,
    union_energy_system_ref_uuid character varying(36),
    external_id character varying(80),
    external_name character varying(255),
    external_nameoes character varying(255),
    external_abbr character varying(255),
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_fue_em.gs_fue_em_union_energy_system IS 'Внешние идентификаторы объединенных энергосистем из топливного модуля';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_union_energy_system.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_union_energy_system.union_energy_system_ref_uuid IS 'UUID ОЭС для сопоставления';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_union_energy_system.external_id IS 'Внешний идентификатор ОЭС';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_union_energy_system.external_name IS 'Внешнее наименование ОЭС';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_union_energy_system.external_nameoes IS 'Внешнее наименование ОЭС из БД «Топливо»';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_union_energy_system.external_abbr IS 'Внешняя аббревиатура ОЭС';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_union_energy_system.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_fue_em.gs_fue_em_union_energy_system.modified_by IS 'Пользователь, последним изменивший запись';

CREATE SEQUENCE gs_fue_em.gs_fue_em_union_energy_system_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_fue_em.gs_fue_em_union_energy_system_id_seq OWNED BY gs_fue_em.gs_fue_em_union_energy_system.id;

CREATE TABLE gs_gen.gs_gen_boilers (
    id integer NOT NULL,
    name character varying(80) NOT NULL,
    id_station integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_gen.gs_gen_boilers IS 'котлы электростанций';

COMMENT ON COLUMN gs_gen.gs_gen_boilers.id IS 'идентификатор';

COMMENT ON COLUMN gs_gen.gs_gen_boilers.name IS 'наименование';

COMMENT ON COLUMN gs_gen.gs_gen_boilers.id_station IS 'идентификатор электростанции (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_boilers.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_gen.gs_gen_boilers.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_gen.gs_gen_boilers.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_gen.gs_gen_boilers.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_gen.gs_gen_boilers.modified_by IS 'пользователь, последним изменивший запись';

CREATE SEQUENCE gs_gen.boilers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.boilers_id_seq OWNED BY gs_gen.gs_gen_boilers.id;

CREATE TABLE gs_gen.gs_gen_documents_kommod (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    file_path character varying(500),
    file_name character varying(255),
    file_size integer,
    file_type character varying(100),
    uploaded_at timestamp with time zone,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_gen.gs_gen_documents_kommod IS 'нормативные документы';

COMMENT ON COLUMN gs_gen.gs_gen_documents_kommod.id IS 'идентификатор';

COMMENT ON COLUMN gs_gen.gs_gen_documents_kommod.name IS 'наименование';

COMMENT ON COLUMN gs_gen.gs_gen_documents_kommod.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_gen.gs_gen_documents_kommod.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_gen.gs_gen_documents_kommod.file_path IS 'путь к файлу в файловой системе';

COMMENT ON COLUMN gs_gen.gs_gen_documents_kommod.file_name IS 'оригинальное имя файла';

COMMENT ON COLUMN gs_gen.gs_gen_documents_kommod.file_size IS 'размер файла в байтах';

COMMENT ON COLUMN gs_gen.gs_gen_documents_kommod.file_type IS 'MIME тип файла';

COMMENT ON COLUMN gs_gen.gs_gen_documents_kommod.uploaded_at IS 'дата загрузки файла';

COMMENT ON COLUMN gs_gen.gs_gen_documents_kommod.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_gen.gs_gen_documents_kommod.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_gen.gs_gen_documents_kommod.modified_by IS 'пользователь, последним изменивший запись';

CREATE SEQUENCE gs_gen.documents_kommod_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.documents_kommod_id_seq OWNED BY gs_gen.gs_gen_documents_kommod.id;

CREATE TABLE gs_gen.gs_gen_gaes_tep_source_project_indicators (
    id integer NOT NULL,
    id_station_prospective_place_gaes integer NOT NULL,
    id_prospective_place_type_gaes integer,
    installed_capacity_mw_generator_mode character varying(100),
    stage_1_capacity_mw_generator_mode character varying(100),
    stage_2_capacity_mw_generator_mode character varying(100),
    installed_capacity_mw_pump_mode character varying(100),
    stage_1_capacity_mw_pump_mode character varying(100),
    stage_2_capacity_mw_pump_mode character varying(100),
    units_count integer,
    hydro_turbine_type character varying(500),
    ccium_turbine_mode character varying(100),
    ccium_pump_mode character varying(100),
    construction_period_years numeric(12,1),
    construction_increment_year_01_mw character varying(100),
    construction_increment_year_02_mw character varying(100),
    construction_increment_year_03_mw character varying(100),
    construction_increment_year_04_mw character varying(100),
    construction_increment_year_05_mw character varying(100),
    construction_increment_year_06_mw character varying(100),
    construction_increment_year_07_mw character varying(100),
    construction_increment_year_08_mw character varying(100),
    construction_increment_year_09_mw character varying(100),
    construction_increment_year_10_mw character varying(100),
    construction_increment_year_11_mw character varying(100),
    specific_semifixed_operating_costs_thous_rub_per_kw character varying(100),
    generation_average_multiyear_million_kwh character varying(100),
    generation_average_multiyear_million_kwh_stage_1 character varying(100),
    generation_average_multiyear_million_kwh_stage_2 character varying(100),
    generation_medium_water_50pct_million_kwh character varying(100),
    generation_low_water_95pct_million_kwh character varying(100),
    annual_charging_electricity_consumption_million_kwh_stage_1 character varying(100),
    annual_charging_electricity_consumption_million_kwh_stage_2 character varying(100),
    specific_capital_investment_thous_rub_per_kw character varying(100),
    capital_investment_gaes_construction_current_prices_billion_rub character varying(100),
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    construction_increment_year_12_mw character varying(100),
    capital_cost_wo_pir_total_million_rub numeric(24,4),
    id_year_capital_cost_wo_pir_total integer,
    capital_cost_wo_pir_ges_with_reservoir_million_rub numeric(24,4),
    id_year_capital_cost_wo_pir_ges_with_reservoir integer,
    capital_cost_wo_pir_svm_million_rub numeric(24,4),
    id_year_capital_cost_wo_pir_svm integer,
    startup_complex_capacity_mw_generator_mode character varying(100),
    startup_complex_capacity_mw_pump_mode character varying(100),
    unit_capacity_mw_generator_mode character varying(100),
    unit_capacity_mw_pump_mode character varying(100),
    annual_charging_electricity_consumption_million_kwh character varying(100),
    id_year_specific_semifixed_operating_costs integer,
    id_year_specific_capital_investment integer
);

COMMENT ON TABLE gs_gen.gs_gen_gaes_tep_source_project_indicators IS 'перечень исходных технико-экономических показателей новых ГАЭС по проектным (предпроектным) данным';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.id IS 'идентификатор';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.id_station_prospective_place_gaes IS 'идентификатор станции перспективной площадки ГАЭС (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.id_prospective_place_type_gaes IS 'идентификатор типа перспективной площадки ГАЭС (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.installed_capacity_mw_generator_mode IS 'установленная мощность в генераторном режиме (всего → в т.ч. ПК → 1–2 очередь)';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.stage_1_capacity_mw_generator_mode IS 'установленная мощность в генераторном режиме (1 очередь)';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.stage_2_capacity_mw_generator_mode IS 'установленная мощность в генераторном режиме (2 очередь)';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.installed_capacity_mw_pump_mode IS 'установленная мощность в насосном режиме (всего → в т.ч. ПК → 1–2 очередь)';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.stage_1_capacity_mw_pump_mode IS 'установленная мощность в насосном режиме (1 очередь)';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.stage_2_capacity_mw_pump_mode IS 'установленная мощность в насосном режиме (2 очередь)';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.units_count IS 'количество агрегатов';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.hydro_turbine_type IS 'тип гидротурбины';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.ccium_turbine_mode IS 'число часов использования установленной мощности в сутки (генераторный режим), час/сутки';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.ccium_pump_mode IS 'число часов использования установленной мощности в сутки (насосный режим), час/сутки';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.construction_period_years IS 'срок строительства АЭС, ГАЭС лет';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.construction_increment_year_01_mw IS 'очередность строительства (прирост вводимой мощности), год 1, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.construction_increment_year_02_mw IS 'очередность строительства (прирост вводимой мощности), год 2, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.construction_increment_year_03_mw IS 'очередность строительства (прирост вводимой мощности), год 3, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.construction_increment_year_04_mw IS 'очередность строительства (прирост вводимой мощности), год 4, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.construction_increment_year_05_mw IS 'очередность строительства (прирост вводимой мощности), год 5, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.construction_increment_year_06_mw IS 'очередность строительства (прирост вводимой мощности), год 6, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.construction_increment_year_07_mw IS 'очередность строительства (прирост вводимой мощности), год 7, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.construction_increment_year_08_mw IS 'очередность строительства (прирост вводимой мощности), год 8, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.construction_increment_year_09_mw IS 'очередность строительства (прирост вводимой мощности), год 9, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.construction_increment_year_10_mw IS 'очередность строительства (прирост вводимой мощности), год 10, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.construction_increment_year_11_mw IS 'очередность строительства (прирост вводимой мощности), год 11, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.specific_semifixed_operating_costs_thous_rub_per_kw IS 'удельные условно-постоянные эксплуатационные затраты (без амортизационных отчислений), млн руб./МВт';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.generation_average_multiyear_million_kwh IS 'годовая выработка электроэнергии (млн кВт·ч)';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.generation_average_multiyear_million_kwh_stage_1 IS 'годовая выработка электроэнергии – 1 очередь, млн кВт·ч';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.generation_average_multiyear_million_kwh_stage_2 IS 'годовая выработка электроэнергии – 2 очередь, млн кВт·ч';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.generation_medium_water_50pct_million_kwh IS 'выработка электроэнергии при средневодных условиях (50% обеспеченности по каскаду), млн кВт·ч';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.generation_low_water_95pct_million_kwh IS 'выработка электроэнергии при маловодных условиях (95% обеспеченности по каскаду), млн кВт·ч';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.annual_charging_electricity_consumption_million_kwh_stage_1 IS 'годовое потребление электрической энергии ГАЭС на заряд, млн кВт·ч, очередь 1';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.annual_charging_electricity_consumption_million_kwh_stage_2 IS 'годовое потребление электрической энергии ГАЭС на заряд, млн кВт·ч, очередь 2';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.specific_capital_investment_thous_rub_per_kw IS 'удельные капиталовложения в строительство (с бассейнами), млн руб./МВт';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.capital_investment_gaes_construction_current_prices_billion_rub IS 'капиталовложения в строительство ГАЭС в ценах текущего года без НДС, млрд руб.';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.note IS 'примечание';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.construction_increment_year_12_mw IS 'очередность строительства (прирост вводимой мощности), год 12, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.capital_cost_wo_pir_total_million_rub IS 'стоимость (капзатраты без ПИР), млн руб';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.id_year_capital_cost_wo_pir_total IS 'идентификатор года данных (стоимость (капзатраты без ПИР) (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.capital_cost_wo_pir_ges_with_reservoir_million_rub IS 'стоимость (капзатраты без ПИР), в том числе ГЭС (с водохранилищем), млн руб';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.id_year_capital_cost_wo_pir_ges_with_reservoir IS 'идентификатор года данных (стоимость (капзатраты без ПИР), в том числе ГЭС (с водохранилищем) (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.capital_cost_wo_pir_svm_million_rub IS 'стоимость (капзатраты без ПИР), в том числе СВМ, млн руб';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.id_year_capital_cost_wo_pir_svm IS 'идентификатор года данных (стоимость (капзатраты без ПИР), в том числе СВМ (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.startup_complex_capacity_mw_generator_mode IS 'установленная мощность в генераторном режиме (ПК → 1–2 очередь)';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.startup_complex_capacity_mw_pump_mode IS 'установленная мощность в насосном режиме (ПК → 1–2 очередь)';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.unit_capacity_mw_generator_mode IS 'единичная мощность агрегата (генераторный режим)';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.unit_capacity_mw_pump_mode IS 'единичная мощность агрегата (насосный режим)';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.annual_charging_electricity_consumption_million_kwh IS 'годовое потребление электрической энергии ГАЭС на заряд, млн кВт·ч';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.id_year_specific_semifixed_operating_costs IS 'идентификатор года данных (удельные условно-постоянные эксплуатационные затраты (без амортизации) (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_gaes_tep_source_project_indicators.id_year_specific_capital_investment IS 'год данных (удельные капитальные вложения)';

CREATE SEQUENCE gs_gen.gaes_tep_source_project_indicators_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.gaes_tep_source_project_indicators_id_seq OWNED BY gs_gen.gs_gen_gaes_tep_source_project_indicators.id;

CREATE TABLE gs_gen.gs_gen_tep_price_conversion_coefficients (
    id integer NOT NULL,
    id_year integer NOT NULL,
    coefficient numeric(24,10),
    database_version_id integer NOT NULL,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE gs_gen.gs_gen_tep_price_conversion_coefficients IS 'коэффициенты для перевода цен исходных данных ТЭП в цены текущего года (характеристика актуальных площадок размещения новых электростанций: АЭС, ГЭС, ГАЭС, ТЭС и др.)';

COMMENT ON COLUMN gs_gen.gs_gen_tep_price_conversion_coefficients.id IS 'идентификатор';

COMMENT ON COLUMN gs_gen.gs_gen_tep_price_conversion_coefficients.id_year IS 'идентификатор года';

COMMENT ON COLUMN gs_gen.gs_gen_tep_price_conversion_coefficients.coefficient IS 'коэффициент';

COMMENT ON COLUMN gs_gen.gs_gen_tep_price_conversion_coefficients.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_gen.gs_gen_tep_price_conversion_coefficients.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_gen.gs_gen_tep_price_conversion_coefficients.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_gen.gs_gen_tep_price_conversion_coefficients.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_gen.gs_gen_tep_price_conversion_coefficients.updated_at IS 'дата и время последнего обновления записи';

CREATE SEQUENCE gs_gen.ges_tep_price_conversion_coefficients_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.ges_tep_price_conversion_coefficients_id_seq OWNED BY gs_gen.gs_gen_tep_price_conversion_coefficients.id;

CREATE TABLE gs_gen.gs_gen_ges_tep_source_project_indicators (
    id integer NOT NULL,
    id_station_prospective_place_ges integer NOT NULL,
    id_prospective_place_type_ges integer,
    installed_capacity_mw character varying(100),
    stage_1_capacity_mw character varying(100),
    stage_2_capacity_mw character varying(100),
    startup_complex_capacity_mw character varying(100),
    units_count integer,
    unit_capacity_mw character varying(100),
    hydro_turbine_type character varying(500),
    construction_period_years numeric(12,1),
    construction_increment_year_01_mw character varying(100),
    construction_increment_year_02_mw character varying(100),
    construction_increment_year_03_mw character varying(100),
    construction_increment_year_04_mw character varying(100),
    construction_increment_year_05_mw character varying(100),
    construction_increment_year_06_mw character varying(100),
    construction_increment_year_07_mw character varying(100),
    construction_increment_year_08_mw character varying(100),
    construction_increment_year_09_mw character varying(100),
    construction_increment_year_10_mw character varying(100),
    construction_increment_year_11_mw character varying(100),
    specific_semifixed_operating_costs_thous_rub_per_kw character varying(100),
    generation_medium_water_50pct_million_kwh character varying(100),
    generation_medium_water_management_year character varying(255),
    generation_low_water_95pct_million_kwh character varying(100),
    generation_low_water_management_year character varying(255),
    specific_capital_investment_thous_rub_per_kw character varying(100),
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    generation_average_multiyear_million_kwh character varying(100),
    construction_increment_year_12_mw character varying(100),
    capital_cost_wo_pir_total_million_rub numeric(24,4),
    id_year_capital_cost_wo_pir_total integer,
    capital_cost_wo_pir_ges_with_reservoir_million_rub numeric(24,4),
    id_year_capital_cost_wo_pir_ges_with_reservoir integer,
    capital_cost_wo_pir_svm_million_rub numeric(24,4),
    id_year_capital_cost_wo_pir_svm integer,
    id_year_specific_semifixed_operating_costs integer,
    id_year_specific_capital_investment integer
);

COMMENT ON TABLE gs_gen.gs_gen_ges_tep_source_project_indicators IS 'перечень исходных технико-экономических показателей новых ГЭС по проектным (предпроектным) данным';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.id IS 'идентификатор';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.id_station_prospective_place_ges IS 'идентификатор станции перспективной площадки ГЭС (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.id_prospective_place_type_ges IS 'идентификатор типа перспективной площадки ГЭС (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.installed_capacity_mw IS 'установленная генерирующая мощность, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.stage_1_capacity_mw IS 'установленная генерирующая мощность, 1 очередь, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.stage_2_capacity_mw IS 'установленная генерирующая мощность, 2 очередь, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.startup_complex_capacity_mw IS 'установленная генерирующая мощность, пусковой комплекс, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.units_count IS 'количество агрегатов';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.unit_capacity_mw IS 'мощность одного агрегата / энергоблока, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.hydro_turbine_type IS 'тип гидротурбины';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.construction_period_years IS 'срок строительства АЭС, ГАЭС лет';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.construction_increment_year_01_mw IS 'очередность строительства (прирост вводимой мощности), год 1, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.construction_increment_year_02_mw IS 'очередность строительства (прирост вводимой мощности), год 2, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.construction_increment_year_03_mw IS 'очередность строительства (прирост вводимой мощности), год 3, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.construction_increment_year_04_mw IS 'очередность строительства (прирост вводимой мощности), год 4, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.construction_increment_year_05_mw IS 'очередность строительства (прирост вводимой мощности), год 5, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.construction_increment_year_06_mw IS 'очередность строительства (прирост вводимой мощности), год 6, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.construction_increment_year_07_mw IS 'очередность строительства (прирост вводимой мощности), год 7, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.construction_increment_year_08_mw IS 'очередность строительства (прирост вводимой мощности), год 8, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.construction_increment_year_09_mw IS 'очередность строительства (прирост вводимой мощности), год 9, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.construction_increment_year_10_mw IS 'очередность строительства (прирост вводимой мощности), год 10, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.construction_increment_year_11_mw IS 'очередность строительства (прирост вводимой мощности), год 11, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.specific_semifixed_operating_costs_thous_rub_per_kw IS 'удельные условно-постоянные эксплуатационные затраты (без амортизационных отчислений), млн руб./МВт';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.generation_medium_water_50pct_million_kwh IS 'выработка электроэнергии при средневодных условиях (50% обеспеченности по каскаду), млн кВт·ч';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.generation_medium_water_management_year IS 'год управления уровнем воды при среднем уровне воды';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.generation_low_water_95pct_million_kwh IS 'выработка электроэнергии при маловодных условиях (95% обеспеченности по каскаду), млн кВт·ч';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.generation_low_water_management_year IS 'год управления уровнем воды при низком уровне воды';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.specific_capital_investment_thous_rub_per_kw IS 'удельные капиталовложения (без НДС), за вычетом затрат на водохранилище, млн руб./МВт';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.note IS 'примечание';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.generation_average_multiyear_million_kwh IS 'среднемноголетняя выработка электроэнергии, млн кВт·ч';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.construction_increment_year_12_mw IS 'очередность строительства (прирост вводимой мощности), год 12, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.capital_cost_wo_pir_total_million_rub IS 'стоимость (капзатраты без ПИР), млн руб';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.id_year_capital_cost_wo_pir_total IS 'идентификатор года данных (стоимость (капзатраты без ПИР) (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.capital_cost_wo_pir_ges_with_reservoir_million_rub IS 'стоимость (капзатраты без ПИР), в том числе ГЭС (с водохранилищем), млн руб';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.id_year_capital_cost_wo_pir_ges_with_reservoir IS 'идентификатор года данных (стоимость (капзатраты без ПИР), в том числе ГЭС (с водохранилищем) (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.capital_cost_wo_pir_svm_million_rub IS 'стоимость (капзатраты без ПИР), в том числе СВМ, млн руб';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.id_year_capital_cost_wo_pir_svm IS 'идентификатор года данных (стоимость (капзатраты без ПИР), в том числе СВМ (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.id_year_specific_semifixed_operating_costs IS 'идентификатор года данных (удельные условно-постоянные эксплуатационные затраты (без амортизации) (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_ges_tep_source_project_indicators.id_year_specific_capital_investment IS 'год данных (удельные капитальные вложения)';

CREATE SEQUENCE gs_gen.ges_tep_source_project_indicators_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.ges_tep_source_project_indicators_id_seq OWNED BY gs_gen.gs_gen_ges_tep_source_project_indicators.id;

CREATE TABLE gs_gen.gs_gen_machine_fuels (
    id integer NOT NULL,
    year_number integer,
    id_machine integer,
    id_fuel integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_gen.gs_gen_machine_fuels IS 'топливо агрегатов';

COMMENT ON COLUMN gs_gen.gs_gen_machine_fuels.id IS 'идентификатор';

COMMENT ON COLUMN gs_gen.gs_gen_machine_fuels.year_number IS 'номер года (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_machine_fuels.id_machine IS 'идентификатор агрегата (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_machine_fuels.id_fuel IS 'идентификатор топлива (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_machine_fuels.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_gen.gs_gen_machine_fuels.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_gen.gs_gen_machine_fuels.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_gen.gs_gen_machine_fuels.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_gen.gs_gen_machine_fuels.modified_by IS 'пользователь, последним изменивший запись';

CREATE TABLE gs_gen.gs_gen_machine_names (
    id integer NOT NULL,
    year_number integer,
    id_machine integer,
    name character varying(1024),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_gen.gs_gen_machine_names IS 'названия агрегатов по годам';

COMMENT ON COLUMN gs_gen.gs_gen_machine_names.id IS 'идентификатор';

COMMENT ON COLUMN gs_gen.gs_gen_machine_names.year_number IS 'номер года (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_machine_names.id_machine IS 'идентификатор агрегата (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_machine_names.name IS 'наименование';

COMMENT ON COLUMN gs_gen.gs_gen_machine_names.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_gen.gs_gen_machine_names.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_gen.gs_gen_machine_names.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_gen.gs_gen_machine_names.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_gen.gs_gen_machine_names.modified_by IS 'пользователь, последним изменивший запись';

CREATE TABLE gs_gen.gs_gen_machine_powers (
    id integer NOT NULL,
    year_number integer,
    id_machine integer,
    p_ust numeric(25,16),
    p_ogr numeric(25,16),
    p_rasp numeric(25,16),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_gen.gs_gen_machine_powers IS 'мощности агрегатов';

COMMENT ON COLUMN gs_gen.gs_gen_machine_powers.id IS 'идентификатор';

COMMENT ON COLUMN gs_gen.gs_gen_machine_powers.year_number IS 'номер года (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_machine_powers.id_machine IS 'идентификатор агрегата (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_machine_powers.p_ust IS 'мощности (до 16 знаков после запятой для согласования с импортом excel)';

COMMENT ON COLUMN gs_gen.gs_gen_machine_powers.p_ogr IS 'мощности (до 16 знаков после запятой для согласования с импортом excel)';

COMMENT ON COLUMN gs_gen.gs_gen_machine_powers.p_rasp IS 'мощности (до 16 знаков после запятой для согласования с импортом excel)';

COMMENT ON COLUMN gs_gen.gs_gen_machine_powers.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_gen.gs_gen_machine_powers.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_gen.gs_gen_machine_powers.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_gen.gs_gen_machine_powers.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_gen.gs_gen_machine_powers.modified_by IS 'пользователь, последним изменивший запись';

CREATE TABLE gs_gen.gs_gen_machine_prospective_place_aes (
    id integer NOT NULL,
    id_station_prospective_place_aes integer,
    station_block_number character varying(100),
    unit_type character varying(255),
    unit_capacity_mw character varying(100),
    max_annual_operating_hours character varying(100),
    specific_fuel_cost_rub_per_kwh character varying(100),
    specific_fixed_operating_costs_thous_rub_per_kw character varying(100),
    relative_auxiliary_power_consumption_pct character varying(100),
    specific_capital_investment_thous_rub_per_kw character varying(100),
    specific_decommissioning_cost_thous_rub_per_kw character varying(100),
    emergency_state_probability character varying(100),
    ozp character varying(100),
    vlp character varying(100),
    note text,
    possible_implementation_period character varying(50),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    id_prospective_place_type integer,
    service_life_years integer,
    construction_period_years integer,
    id_year_specific_fuel_cost integer,
    id_year_specific_fixed_operating_costs integer,
    id_year_specific_capital_investment integer,
    id_year_specific_decommissioning integer
);

COMMENT ON TABLE gs_gen.gs_gen_machine_prospective_place_aes IS 'энергоблок перспективной площадки размещения АЭС';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.id IS 'идентификатор';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.id_station_prospective_place_aes IS 'идентификатор перспективной площадки АЭС (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.station_block_number IS 'станционный номер блока (текст)';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.unit_type IS 'тип энергоблока';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.unit_capacity_mw IS 'мощность одного агрегата / энергоблока, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.max_annual_operating_hours IS 'предельное годовое число часов использования мощности энергоблока, час';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.specific_fuel_cost_rub_per_kwh IS 'удельная топливная составляющая эксплуатационных затрат в ценах текущего года, руб./кВт';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.specific_fixed_operating_costs_thous_rub_per_kw IS 'удельные условно постоянные эксплуатационные затраты (без амортизационных отчислений), тыс. руб./кВтч';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.relative_auxiliary_power_consumption_pct IS 'относительная величина расхода электрической энергии на собственные нужды АЭС, %';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.specific_capital_investment_thous_rub_per_kw IS 'удельные капиталовложения в строительство АЭС в ценах текущего года (без НДС), тыс. руб./кВт';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.specific_decommissioning_cost_thous_rub_per_kw IS 'удельные затраты на вывод из эксплуатации, тыс. руб./кВт';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.emergency_state_probability IS 'вероятность аварийного состояния, о.е';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.ozp IS 'ОЗП, о.е';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.vlp IS 'ВЛП, о.е';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.note IS 'примечание';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.possible_implementation_period IS 'возможный срок реализации (год: 2042 или дата: 31.12.2042)';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.id_prospective_place_type IS 'идентификатор типа перспективной площадки АЭС (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.service_life_years IS 'срок эксплуатации АЭС, лет';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.construction_period_years IS 'срок строительства АЭС, ГАЭС лет';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.id_year_specific_fuel_cost IS 'идентификатор года данных (топливная составляющая) (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.id_year_specific_fixed_operating_costs IS 'идентификатор года данных (условно постоянные затраты) (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.id_year_specific_capital_investment IS 'год данных (удельные капитальные вложения)';

COMMENT ON COLUMN gs_gen.gs_gen_machine_prospective_place_aes.id_year_specific_decommissioning IS 'идентификатор года данных (вывод из эксплуатации) (FK)';

CREATE TABLE gs_gen.gs_gen_machine_tes_types (
    id integer NOT NULL,
    year_number integer,
    id_machine integer,
    id_tes_type integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_gen.gs_gen_machine_tes_types IS 'типы агрегатов ТЭС';

COMMENT ON COLUMN gs_gen.gs_gen_machine_tes_types.id IS 'идентификатор';

COMMENT ON COLUMN gs_gen.gs_gen_machine_tes_types.year_number IS 'номер года (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_machine_tes_types.id_machine IS 'идентификатор агрегата (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_machine_tes_types.id_tes_type IS 'идентификатор типа ТЭС (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_machine_tes_types.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_gen.gs_gen_machine_tes_types.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_gen.gs_gen_machine_tes_types.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_gen.gs_gen_machine_tes_types.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_gen.gs_gen_machine_tes_types.modified_by IS 'пользователь, последним изменивший запись';

CREATE TABLE gs_gen.gs_gen_machines (
    id integer NOT NULL,
    id_ti integer,
    id_equipment_group integer,
    id_condition_type integer,
    id_gen_company integer,
    id_station integer,
    id_energy_area integer,
    machine_number character varying(80) NOT NULL,
    machine_name character varying(1024) NOT NULL,
    machine_group character varying(255),
    fuel_so character varying(255),
    id_machine_type integer,
    id_tes_machine_type integer,
    date_exploitation integer,
    date_commission_fact character varying(10),
    date_joining_expected character varying(10),
    date_joining_fact character varying(10),
    date_detatchment_fact character varying(10),
    date_decompressing_expected integer,
    date_decompressing_fact character varying(10),
    date_modernization_power_change_expected integer,
    date_relabing_fact character varying(255),
    date_update_fact character varying(255),
    note character varying(512),
    year_modern character varying(10),
    year_demontaz character varying(10),
    resurs_coal character varying(10),
    resurs_gas character varying(10),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    id_technology integer,
    id_technology_type integer,
    id_technology_availability integer,
    change_document text,
    version integer DEFAULT 1 NOT NULL,
    database_version_id integer,
    date_exploitation_expected integer,
    external_code character varying(36) NOT NULL,
    date_commission_year integer,
    created_by character varying(255),
    modified_by character varying(255),
    date_modernization_no_power_change_expected integer,
    relabing_outcome character varying(64),
    is_archived boolean DEFAULT false NOT NULL,
    is_commissioning_q4 boolean DEFAULT false NOT NULL,
    date_exploitation_date_expected character varying(10)
);

COMMENT ON TABLE gs_gen.gs_gen_machines IS 'агрегаты';

COMMENT ON COLUMN gs_gen.gs_gen_machines.id IS 'идентификатор';

COMMENT ON COLUMN gs_gen.gs_gen_machines.id_ti IS 'идентификатор техинспекции';

COMMENT ON COLUMN gs_gen.gs_gen_machines.id_equipment_group IS 'идентификатор группы оборудования (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_machines.id_condition_type IS 'идентификатор типа состояния (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_machines.id_gen_company IS 'идентификатор генерирующей компании (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_machines.id_station IS 'идентификатор электростанции (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_machines.id_energy_area IS 'идентификатор энергорайона (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_machines.machine_number IS 'основные атрибуты';

COMMENT ON COLUMN gs_gen.gs_gen_machines.machine_name IS 'основные атрибуты';

COMMENT ON COLUMN gs_gen.gs_gen_machines.machine_group IS 'групповая принадлежность агрегата';

COMMENT ON COLUMN gs_gen.gs_gen_machines.fuel_so IS 'Топливо по СО ЕЭС';

COMMENT ON COLUMN gs_gen.gs_gen_machines.id_machine_type IS 'идентификатор типа агрегата (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_machines.id_tes_machine_type IS 'идентификатор типа агрегата ТЭС (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_machines.date_exploitation IS 'фактический год ввода в эксплуатацию';

COMMENT ON COLUMN gs_gen.gs_gen_machines.date_commission_fact IS 'фактическая дата ввода в работу';

COMMENT ON COLUMN gs_gen.gs_gen_machines.date_joining_expected IS 'ожидаемая дата присоединения';

COMMENT ON COLUMN gs_gen.gs_gen_machines.date_joining_fact IS 'фактическая дата присоединения';

COMMENT ON COLUMN gs_gen.gs_gen_machines.date_detatchment_fact IS 'фактическая дата отсоединения';

COMMENT ON COLUMN gs_gen.gs_gen_machines.date_decompressing_expected IS 'ожидаемый год вывода из эксплуатации';

COMMENT ON COLUMN gs_gen.gs_gen_machines.date_decompressing_fact IS 'фактическая дата вывода из эксплуатации';

COMMENT ON COLUMN gs_gen.gs_gen_machines.date_modernization_power_change_expected IS 'Ожидаемый год модернизации с изменением мощности';

COMMENT ON COLUMN gs_gen.gs_gen_machines.date_relabing_fact IS 'фактическая дата перемаркировки (может содержать несколько дат)';

COMMENT ON COLUMN gs_gen.gs_gen_machines.date_update_fact IS 'Фактическая дата уточнения';

COMMENT ON COLUMN gs_gen.gs_gen_machines.note IS 'примечание';

COMMENT ON COLUMN gs_gen.gs_gen_machines.year_modern IS 'год модернизации';

COMMENT ON COLUMN gs_gen.gs_gen_machines.year_demontaz IS 'год демонтажа';

COMMENT ON COLUMN gs_gen.gs_gen_machines.resurs_coal IS 'Ресурс угля для агрегата';

COMMENT ON COLUMN gs_gen.gs_gen_machines.resurs_gas IS 'Ресурс газа для агрегата';

COMMENT ON COLUMN gs_gen.gs_gen_machines.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_gen.gs_gen_machines.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_gen.gs_gen_machines.id_technology IS 'Идентификатор технологии';

COMMENT ON COLUMN gs_gen.gs_gen_machines.id_technology_type IS 'Тип технологии агрегата';

COMMENT ON COLUMN gs_gen.gs_gen_machines.id_technology_availability IS 'Доступность технологии агрегата';

COMMENT ON COLUMN gs_gen.gs_gen_machines.change_document IS 'Документ-основание для изменения параметров агрегата';

COMMENT ON COLUMN gs_gen.gs_gen_machines.version IS 'версия записи';

COMMENT ON COLUMN gs_gen.gs_gen_machines.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_gen.gs_gen_machines.date_exploitation_expected IS 'ожидаемый год ввода в эксплуатацию';

COMMENT ON COLUMN gs_gen.gs_gen_machines.external_code IS 'внешний код';

COMMENT ON COLUMN gs_gen.gs_gen_machines.date_commission_year IS 'Фактический год ввода в работу';

COMMENT ON COLUMN gs_gen.gs_gen_machines.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_gen.gs_gen_machines.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_gen.gs_gen_machines.date_modernization_no_power_change_expected IS 'ожидаемый год модернизации без изменения мощности';

COMMENT ON COLUMN gs_gen.gs_gen_machines.relabing_outcome IS 'Тип перемаркировки агрегата';

CREATE TABLE gs_gen.gs_gen_pgu_machine_names (
    id integer NOT NULL,
    year_number integer,
    id_pgu_machine integer,
    name character varying(1024),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_gen.gs_gen_pgu_machine_names IS 'названия компонентов ПГУ по годам';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machine_names.id IS 'идентификатор';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machine_names.year_number IS 'номер года (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machine_names.id_pgu_machine IS 'идентификатор ПГУ-агрегата (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machine_names.name IS 'наименование';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machine_names.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machine_names.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machine_names.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machine_names.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machine_names.modified_by IS 'пользователь, последним изменивший запись';

CREATE TABLE gs_gen.gs_gen_pgu_machine_powers (
    id integer NOT NULL,
    year_number integer,
    id_pgu_machine integer,
    p_ust numeric(25,16),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_gen.gs_gen_pgu_machine_powers IS 'мощности ПГУ-компонентов';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machine_powers.id IS 'идентификатор';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machine_powers.year_number IS 'номер года (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machine_powers.id_pgu_machine IS 'идентификатор ПГУ-агрегата (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machine_powers.p_ust IS 'мощности (до 16 знаков после запятой для согласования с импортом excel)';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machine_powers.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machine_powers.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machine_powers.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machine_powers.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machine_powers.modified_by IS 'пользователь, последним изменивший запись';

CREATE TABLE gs_gen.gs_gen_pgu_machines (
    id integer NOT NULL,
    id_ti integer,
    id_condition_type integer,
    id_parent_machine integer NOT NULL,
    machine_number character varying(80),
    machine_name character varying(1024) NOT NULL,
    id_tes_machine_type integer,
    id_pgu_tes_machine_type integer,
    date_exploitation integer,
    date_commission_fact character varying(10),
    date_joining_expected character varying(10),
    date_joining_fact character varying(10),
    date_detatchment_fact character varying(10),
    date_decompressing_expected integer,
    date_decompressing_fact character varying(10),
    date_modernization_power_change_expected integer,
    date_relabing_fact character varying(255),
    date_update_fact character varying(255),
    note character varying(512),
    year_modern character varying(10),
    year_demontaz character varying(10),
    resurs_gas character varying(10),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    version integer DEFAULT 1 NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    date_commission_year integer,
    date_exploitation_expected integer,
    change_document text,
    date_modernization_no_power_change_expected integer,
    date_exploitation_date_expected character varying(10)
);

COMMENT ON TABLE gs_gen.gs_gen_pgu_machines IS 'компоненты ПГУ';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.id IS 'идентификатор';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.id_ti IS 'идентификатор техинспекции';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.id_condition_type IS 'идентификатор типа состояния (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.id_parent_machine IS 'идентификатор родительского агрегата (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.machine_number IS 'основные атрибуты';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.machine_name IS 'основные атрибуты';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.id_tes_machine_type IS 'идентификатор типа агрегата ТЭС (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.id_pgu_tes_machine_type IS 'идентификатор типа агрегата ПГУ ТЭС (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.date_exploitation IS 'фактический год ввода в эксплуатацию';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.date_commission_fact IS 'фактическая дата ввода в работу';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.date_joining_expected IS 'ожидаемая дата присоединения';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.date_joining_fact IS 'фактическая дата присоединения';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.date_detatchment_fact IS 'фактическая дата отсоединения';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.date_decompressing_expected IS 'ожидаемый год вывода из эксплуатации';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.date_decompressing_fact IS 'фактическая дата вывода из эксплуатации';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.date_modernization_power_change_expected IS 'ожидаемый год модернизации с изменением мощности';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.date_relabing_fact IS 'фактическая дата перемаркировки (может содержать несколько дат)';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.date_update_fact IS 'фактическая дата уточнения (может содержать несколько дат)';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.note IS 'примечание';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.year_modern IS 'год модернизации';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.year_demontaz IS 'год демонтажа';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.resurs_gas IS 'ресурс по газу';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.version IS 'версия записи';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.date_commission_year IS 'фактический год ввода в работу';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.date_exploitation_expected IS 'ожидаемый год ввода в эксплуатацию';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.change_document IS 'документ-основание для изменения параметров агрегата';

COMMENT ON COLUMN gs_gen.gs_gen_pgu_machines.date_modernization_no_power_change_expected IS 'ожидаемый год модернизации без изменения мощности';

CREATE TABLE gs_gen.gs_gen_prospective_place_hydro_energy_forecasts (
    id integer NOT NULL,
    place_kind character varying(8) NOT NULL,
    place_id integer NOT NULL,
    scenario character varying(16) NOT NULL,
    month_number integer NOT NULL,
    electricity_generation numeric(25,16),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    CONSTRAINT ck_pp_hydro_forecast_month CHECK (((month_number >= 1) AND (month_number <= 12))),
    CONSTRAINT ck_pp_hydro_forecast_place_kind CHECK (((place_kind)::text = ANY ((ARRAY['ges'::character varying, 'gaes'::character varying, 'station'::character varying])::text[]))),
    CONSTRAINT ck_pp_hydro_forecast_scenario CHECK (((scenario)::text = ANY ((ARRAY['low_95'::character varying, 'medium_50'::character varying])::text[])))
);

CREATE SEQUENCE gs_gen.gs_gen_prospective_place_hydro_energy_forecasts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.gs_gen_prospective_place_hydro_energy_forecasts_id_seq OWNED BY gs_gen.gs_gen_prospective_place_hydro_energy_forecasts.id;

CREATE TABLE gs_gen.gs_gen_prospective_place_types (
    id integer NOT NULL,
    name text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_gen.gs_gen_prospective_place_types IS 'типы перспективных площадок';

COMMENT ON COLUMN gs_gen.gs_gen_prospective_place_types.id IS 'идентификатор';

COMMENT ON COLUMN gs_gen.gs_gen_prospective_place_types.name IS 'наименование';

COMMENT ON COLUMN gs_gen.gs_gen_prospective_place_types.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_gen.gs_gen_prospective_place_types.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_gen.gs_gen_prospective_place_types.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_gen.gs_gen_prospective_place_types.modified_by IS 'пользователь, последним изменивший запись';

CREATE TABLE gs_gen.gs_gen_prospective_place_types_gaes (
    id integer NOT NULL,
    name text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_gen.gs_gen_prospective_place_types_gaes IS 'типы перспективных площадок ГАЭС (справочник refdata)';

COMMENT ON COLUMN gs_gen.gs_gen_prospective_place_types_gaes.id IS 'идентификатор';

COMMENT ON COLUMN gs_gen.gs_gen_prospective_place_types_gaes.name IS 'наименование';

COMMENT ON COLUMN gs_gen.gs_gen_prospective_place_types_gaes.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_gen.gs_gen_prospective_place_types_gaes.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_gen.gs_gen_prospective_place_types_gaes.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_gen.gs_gen_prospective_place_types_gaes.modified_by IS 'пользователь, последним изменивший запись';

CREATE TABLE gs_gen.gs_gen_prospective_place_types_ges (
    id integer NOT NULL,
    name text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_gen.gs_gen_prospective_place_types_ges IS 'типы перспективных площадок ГЭС (справочник refdata)';

COMMENT ON COLUMN gs_gen.gs_gen_prospective_place_types_ges.id IS 'идентификатор';

COMMENT ON COLUMN gs_gen.gs_gen_prospective_place_types_ges.name IS 'наименование';

COMMENT ON COLUMN gs_gen.gs_gen_prospective_place_types_ges.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_gen.gs_gen_prospective_place_types_ges.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_gen.gs_gen_prospective_place_types_ges.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_gen.gs_gen_prospective_place_types_ges.modified_by IS 'пользователь, последним изменивший запись';

CREATE TABLE gs_gen.gs_gen_station_gaes_charge_consumptions (
    id integer NOT NULL,
    year_number integer,
    id_station integer,
    charge_consumption numeric(25,16),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_gen.gs_gen_station_gaes_charge_consumptions IS 'потребление электрической энергии ГАЭС на заряд по годам (млн кВт·ч)';

COMMENT ON COLUMN gs_gen.gs_gen_station_gaes_charge_consumptions.id IS 'идентификатор';

COMMENT ON COLUMN gs_gen.gs_gen_station_gaes_charge_consumptions.year_number IS 'номер года (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_station_gaes_charge_consumptions.id_station IS 'идентификатор электростанции (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_station_gaes_charge_consumptions.charge_consumption IS 'потребление на заряд, млн кВт·ч';

COMMENT ON COLUMN gs_gen.gs_gen_station_gaes_charge_consumptions.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_gen.gs_gen_station_gaes_charge_consumptions.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_gen.gs_gen_station_gaes_charge_consumptions.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_gen.gs_gen_station_gaes_charge_consumptions.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_gen.gs_gen_station_gaes_charge_consumptions.modified_by IS 'пользователь, последним изменивший запись';

CREATE SEQUENCE gs_gen.gs_gen_station_gaes_charge_consumptions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.gs_gen_station_gaes_charge_consumptions_id_seq OWNED BY gs_gen.gs_gen_station_gaes_charge_consumptions.id;

CREATE TABLE gs_gen.gs_gen_station_groups (
    id integer NOT NULL,
    name character varying(80) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_gen.gs_gen_station_groups IS 'группы станций';

COMMENT ON COLUMN gs_gen.gs_gen_station_groups.id IS 'идентификатор';

COMMENT ON COLUMN gs_gen.gs_gen_station_groups.name IS 'наименование';

COMMENT ON COLUMN gs_gen.gs_gen_station_groups.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_gen.gs_gen_station_groups.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_gen.gs_gen_station_groups.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_gen.gs_gen_station_groups.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_gen.gs_gen_station_groups.modified_by IS 'пользователь, последним изменивший запись';

CREATE TABLE gs_gen.gs_gen_station_owner_energy_generations (
    id integer NOT NULL,
    year_number integer,
    id_station integer,
    electricity_generation numeric(25,16),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255)
);

CREATE SEQUENCE gs_gen.gs_gen_station_owner_energy_generations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.gs_gen_station_owner_energy_generations_id_seq OWNED BY gs_gen.gs_gen_station_owner_energy_generations.id;

CREATE TABLE gs_gen.gs_gen_station_prospective_place_aes (
    id integer NOT NULL,
    site_name character varying(255),
    geo_location character varying(500),
    planned_capacity_mw integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    id_regional_district integer,
    id_regional_energy_system integer,
    planned_unit_capacity_mw integer,
    selection_factor character varying(255),
    external_code character varying(36)
);

COMMENT ON TABLE gs_gen.gs_gen_station_prospective_place_aes IS 'перспективная площадка размещения АЭС';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_aes.id IS 'идентификатор';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_aes.site_name IS 'наименование площадки размещения АЭС, ГЭС';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_aes.geo_location IS 'географическое расположение площадки (кадастровый номер земельного участка или координаты)';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_aes.planned_capacity_mw IS 'планируемая установленная генерирующая мощность АЭС, ГЭС, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_aes.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_aes.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_aes.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_aes.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_aes.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_aes.id_regional_district IS 'идентификатор субъекта РФ (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_aes.id_regional_energy_system IS 'идентификатор региональной энергосистемы (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_aes.planned_unit_capacity_mw IS 'планируемая единичная мощность энергоблока, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_aes.selection_factor IS 'фактор отбора';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_aes.external_code IS 'внешний код';

CREATE TABLE gs_gen.gs_gen_station_prospective_place_gaes (
    id integer NOT NULL,
    site_name character varying(255),
    id_regional_district integer,
    id_regional_energy_system integer,
    geo_location character varying(500),
    planned_capacity_mw character varying(500),
    project_initiator character varying(500),
    water_body character varying(500),
    general_scheme_commissioning_period character varying(255),
    construction_period_years numeric(12,1),
    id_prospective_place_type_gaes integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    display_order integer,
    external_code character varying(36)
);

COMMENT ON TABLE gs_gen.gs_gen_station_prospective_place_gaes IS 'перспективная площадка размещения ГАЭС';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_gaes.id IS 'идентификатор';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_gaes.site_name IS 'наименование площадки размещения АЭС, ГЭС';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_gaes.id_regional_district IS 'идентификатор субъекта РФ (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_gaes.id_regional_energy_system IS 'идентификатор региональной энергосистемы (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_gaes.geo_location IS 'географическое расположение площадки (кадастровый номер земельного участка или координаты)';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_gaes.planned_capacity_mw IS 'планируемая установленная генерирующая мощность АЭС, ГЭС, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_gaes.project_initiator IS 'инициатор проекта';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_gaes.water_body IS 'водохранилище / водный объект';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_gaes.general_scheme_commissioning_period IS 'генеральная схема до 2042 года (период ввода в эксплуатацию), распоряжение ПРФ от 30.12.2024 № 4153-р';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_gaes.construction_period_years IS 'срок строительства АЭС, ГАЭС лет';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_gaes.id_prospective_place_type_gaes IS 'идентификатор типа перспективной площадки ГАЭС (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_gaes.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_gaes.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_gaes.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_gaes.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_gaes.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_gaes.display_order IS 'порядок отображения';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_gaes.external_code IS 'внешний код';

CREATE TABLE gs_gen.gs_gen_station_prospective_place_ges (
    id integer NOT NULL,
    site_name character varying(255),
    id_regional_district integer,
    id_regional_energy_system integer,
    geo_location character varying(500),
    planned_capacity_mw integer,
    project_initiator character varying(500),
    water_body character varying(500),
    general_scheme_commissioning_period character varying(255),
    construction_period_years numeric(12,1),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    id_prospective_place_type_ges integer,
    regulation_type character varying(500),
    display_order integer,
    external_code character varying(36)
);

COMMENT ON TABLE gs_gen.gs_gen_station_prospective_place_ges IS 'перспективная площадка размещения ГЭС';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_ges.id IS 'идентификатор';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_ges.site_name IS 'наименование площадки размещения АЭС, ГЭС';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_ges.id_regional_district IS 'идентификатор субъекта РФ (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_ges.id_regional_energy_system IS 'идентификатор региональной энергосистемы (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_ges.geo_location IS 'географическое расположение площадки (кадастровый номер земельного участка или координаты)';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_ges.planned_capacity_mw IS 'планируемая установленная генерирующая мощность АЭС, ГЭС, МВт';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_ges.project_initiator IS 'инициатор проекта';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_ges.water_body IS 'водохранилище / водный объект';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_ges.general_scheme_commissioning_period IS 'генеральная схема до 2042 года (период ввода в эксплуатацию), распоряжение ПРФ от 30.12.2024 № 4153-р';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_ges.construction_period_years IS 'срок строительства АЭС, ГАЭС лет';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_ges.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_ges.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_ges.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_ges.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_ges.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_ges.id_prospective_place_type_ges IS 'идентификатор типа перспективной площадки ГЭС (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_ges.regulation_type IS 'вид регулирования';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_ges.display_order IS 'порядок отображения';

COMMENT ON COLUMN gs_gen.gs_gen_station_prospective_place_ges.external_code IS 'внешний код';

CREATE TABLE gs_gen.gs_gen_station_snee_efficiencies (
    id integer NOT NULL,
    id_station integer NOT NULL,
    database_version_id integer,
    efficiency_percent numeric(25,16),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by character varying(255),
    modified_by character varying(255)
);

CREATE SEQUENCE gs_gen.gs_gen_station_snee_efficiencies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.gs_gen_station_snee_efficiencies_id_seq OWNED BY gs_gen.gs_gen_station_snee_efficiencies.id;

CREATE TABLE gs_gen.gs_gen_station_snee_energy_consumptions (
    id integer NOT NULL,
    year_number integer,
    id_station integer,
    electricity_consumption numeric(25,16),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255)
);

CREATE SEQUENCE gs_gen.gs_gen_station_snee_energy_consumptions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.gs_gen_station_snee_energy_consumptions_id_seq OWNED BY gs_gen.gs_gen_station_snee_energy_consumptions.id;

CREATE TABLE gs_gen.gs_gen_stations (
    id integer NOT NULL,
    id_condition_type integer,
    name character varying(255) NOT NULL,
    name_so character varying(80),
    name_combined character varying(80),
    name_archive character varying(80),
    id_regional_district integer,
    id_energy_unit integer,
    kto character varying(80),
    location character varying(255),
    note character varying(1000),
    id_station_group integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    version integer DEFAULT 1 NOT NULL,
    id_station_type integer,
    database_version_id integer,
    id_regional_energy_system integer,
    external_code character varying(36) NOT NULL,
    created_by character varying(255),
    modified_by character varying(255),
    station_sign character varying(20),
    is_generation_only boolean DEFAULT false NOT NULL,
    created_as_generation_only boolean DEFAULT false NOT NULL
);

COMMENT ON TABLE gs_gen.gs_gen_stations IS 'электростанции';

COMMENT ON COLUMN gs_gen.gs_gen_stations.id IS 'идентификатор';

COMMENT ON COLUMN gs_gen.gs_gen_stations.id_condition_type IS 'идентификатор типа состояния (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_stations.name IS 'наименование';

COMMENT ON COLUMN gs_gen.gs_gen_stations.name_so IS 'наименование по данным СО';

COMMENT ON COLUMN gs_gen.gs_gen_stations.name_combined IS 'сводное наименование электростанции';

COMMENT ON COLUMN gs_gen.gs_gen_stations.name_archive IS 'историческое / архивное наименование электростанции';

COMMENT ON COLUMN gs_gen.gs_gen_stations.id_regional_district IS 'идентификатор субъекта РФ (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_stations.id_energy_unit IS 'идентификатор энергоузла (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_stations.kto IS 'прочее';

COMMENT ON COLUMN gs_gen.gs_gen_stations.location IS 'локация';

COMMENT ON COLUMN gs_gen.gs_gen_stations.note IS 'примечание';

COMMENT ON COLUMN gs_gen.gs_gen_stations.id_station_group IS 'идентификатор группы электростанций (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_stations.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_gen.gs_gen_stations.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_gen.gs_gen_stations.version IS 'версия записи';

COMMENT ON COLUMN gs_gen.gs_gen_stations.id_station_type IS 'идентификатор типа электростанции (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_stations.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_gen.gs_gen_stations.id_regional_energy_system IS 'идентификатор региональной энергосистемы (FK)';

COMMENT ON COLUMN gs_gen.gs_gen_stations.external_code IS 'внешний код';

COMMENT ON COLUMN gs_gen.gs_gen_stations.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_gen.gs_gen_stations.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_gen.gs_gen_stations.station_sign IS 'Признак электростанции: ЭСПП или не указано';

CREATE SEQUENCE gs_gen.gs_prospective_place_types_gaes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.gs_prospective_place_types_gaes_id_seq OWNED BY gs_gen.gs_gen_prospective_place_types_gaes.id;

CREATE SEQUENCE gs_gen.gs_prospective_place_types_ges_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.gs_prospective_place_types_ges_id_seq OWNED BY gs_gen.gs_gen_prospective_place_types_ges.id;

CREATE SEQUENCE gs_gen.gs_prospective_place_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.gs_prospective_place_types_id_seq OWNED BY gs_gen.gs_gen_prospective_place_types.id;

CREATE SEQUENCE gs_gen.machine_fuels_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.machine_fuels_id_seq OWNED BY gs_gen.gs_gen_machine_fuels.id;

CREATE SEQUENCE gs_gen.machine_names_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.machine_names_id_seq OWNED BY gs_gen.gs_gen_machine_names.id;

CREATE SEQUENCE gs_gen.machine_powers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.machine_powers_id_seq OWNED BY gs_gen.gs_gen_machine_powers.id;

CREATE SEQUENCE gs_gen.machine_prospective_place_aes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.machine_prospective_place_aes_id_seq OWNED BY gs_gen.gs_gen_machine_prospective_place_aes.id;

CREATE SEQUENCE gs_gen.machine_tes_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.machine_tes_types_id_seq OWNED BY gs_gen.gs_gen_machine_tes_types.id;

CREATE SEQUENCE gs_gen.machines_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.machines_id_seq OWNED BY gs_gen.gs_gen_machines.id;

CREATE SEQUENCE gs_gen.pgu_machine_names_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.pgu_machine_names_id_seq OWNED BY gs_gen.gs_gen_pgu_machine_names.id;

CREATE SEQUENCE gs_gen.pgu_machine_powers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.pgu_machine_powers_id_seq OWNED BY gs_gen.gs_gen_pgu_machine_powers.id;

CREATE SEQUENCE gs_gen.pgu_machines_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.pgu_machines_id_seq OWNED BY gs_gen.gs_gen_pgu_machines.id;

CREATE SEQUENCE gs_gen.station_groups_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.station_groups_id_seq OWNED BY gs_gen.gs_gen_station_groups.id;

CREATE SEQUENCE gs_gen.station_prospective_place_aes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.station_prospective_place_aes_id_seq OWNED BY gs_gen.gs_gen_station_prospective_place_aes.id;

CREATE SEQUENCE gs_gen.station_prospective_place_gaes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.station_prospective_place_gaes_id_seq OWNED BY gs_gen.gs_gen_station_prospective_place_gaes.id;

CREATE SEQUENCE gs_gen.station_prospective_place_ges_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.station_prospective_place_ges_id_seq OWNED BY gs_gen.gs_gen_station_prospective_place_ges.id;

CREATE SEQUENCE gs_gen.stations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_gen.stations_id_seq OWNED BY gs_gen.gs_gen_stations.id;

CREATE TABLE gs_logs.logs (
    id integer NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL,
    username character varying(100) NOT NULL,
    action character varying(500) NOT NULL,
    details text,
    entity_type character varying(50),
    entity_id integer,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    module character varying(100) DEFAULT 'Система'::character varying NOT NULL
);

COMMENT ON TABLE gs_logs.logs IS 'Журнал аудита действий пользователей';

COMMENT ON COLUMN gs_logs.logs.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_logs.logs."timestamp" IS 'Время события аудита';

COMMENT ON COLUMN gs_logs.logs.username IS 'Идентификатор пользователя на момент события';

COMMENT ON COLUMN gs_logs.logs.action IS 'Краткое действие в журнале';

COMMENT ON COLUMN gs_logs.logs.details IS 'Детали действия в журнале';

COMMENT ON COLUMN gs_logs.logs.entity_type IS 'Тип сущности, к которой относится событие';

COMMENT ON COLUMN gs_logs.logs.entity_id IS 'Идентификатор сущности, к которой относится событие';

COMMENT ON COLUMN gs_logs.logs.database_version_id IS 'Версия базы данных на момент создания записи журнала';

COMMENT ON COLUMN gs_logs.logs.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_logs.logs.modified_by IS 'Пользователь, последним изменивший запись';

CREATE SEQUENCE gs_logs.logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_logs.logs_id_seq OWNED BY gs_logs.logs.id;

CREATE TABLE gs_pd.gs_pd_centralized_zone_demand_params (
    id integer NOT NULL,
    is_historical_maximum boolean DEFAULT false NOT NULL,
    year_number integer,
    max_power_consumption_mw numeric(25,3),
    peak_datetime timestamp with time zone,
    avg_daily_air_temp_c numeric(10,2),
    combined_on_oes numeric(25,3),
    combined_on_ees numeric(25,3),
    combined_on_es numeric(25,3),
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    note text,
    perimeter_variant_code character varying(64),
    CONSTRAINT ck_gs_centralized_zone_demand_params_year_vs_hist CHECK ((((is_historical_maximum = true) AND (year_number IS NULL)) OR ((is_historical_maximum = false) AND (year_number IS NOT NULL))))
);

COMMENT ON TABLE gs_pd.gs_pd_centralized_zone_demand_params IS 'Параметры нагрузки для Централизованной зоны (без FK на справочник)';

COMMENT ON COLUMN gs_pd.gs_pd_centralized_zone_demand_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_pd.gs_pd_centralized_zone_demand_params.is_historical_maximum IS 'Признак исторического максимума (true — без года)';

COMMENT ON COLUMN gs_pd.gs_pd_centralized_zone_demand_params.year_number IS 'Год';

COMMENT ON COLUMN gs_pd.gs_pd_centralized_zone_demand_params.max_power_consumption_mw IS 'Максимальное потребление мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_centralized_zone_demand_params.peak_datetime IS 'Дата и время максимального потребления мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_centralized_zone_demand_params.avg_daily_air_temp_c IS 'Средняя дневная температура воздуха, °C';

COMMENT ON COLUMN gs_pd.gs_pd_centralized_zone_demand_params.combined_on_oes IS 'совмещенный максимум на ОЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_centralized_zone_demand_params.combined_on_ees IS 'совмещенный максимум на ЕЭС России, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_centralized_zone_demand_params.combined_on_es IS 'совмещенный максимум на РЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_centralized_zone_demand_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_pd.gs_pd_centralized_zone_demand_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_pd.gs_pd_centralized_zone_demand_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_pd.gs_pd_centralized_zone_demand_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_pd.gs_pd_centralized_zone_demand_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_pd.gs_pd_centralized_zone_demand_params.note IS 'Примечание';

COMMENT ON COLUMN gs_pd.gs_pd_centralized_zone_demand_params.perimeter_variant_code IS 'Код варианта периметра (NULL — без варианта)';

CREATE SEQUENCE gs_pd.gs_centralized_zone_demand_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_pd.gs_centralized_zone_demand_params_id_seq OWNED BY gs_pd.gs_pd_centralized_zone_demand_params.id;

CREATE TABLE gs_pd.gs_pd_ees_demand_params (
    id integer NOT NULL,
    is_historical_maximum boolean DEFAULT false NOT NULL,
    year_number integer,
    max_power_consumption_mw numeric(25,3),
    peak_datetime timestamp with time zone,
    avg_daily_air_temp_c numeric(10,2),
    combined_on_oes numeric(25,3),
    combined_on_ees numeric(25,3),
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    combined_on_es numeric(25,3),
    note text,
    perimeter_variant_code character varying(64),
    CONSTRAINT ck_gs_ees_demand_params_year_vs_hist CHECK ((((is_historical_maximum = true) AND (year_number IS NULL)) OR ((is_historical_maximum = false) AND (year_number IS NOT NULL))))
);

COMMENT ON TABLE gs_pd.gs_pd_ees_demand_params IS 'Параметры нагрузки для ЭЭС (отдельный сценарий, без привязки к справочнику типов энергосистем)';

COMMENT ON COLUMN gs_pd.gs_pd_ees_demand_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_pd.gs_pd_ees_demand_params.is_historical_maximum IS 'Признак исторического максимума (true — без года)';

COMMENT ON COLUMN gs_pd.gs_pd_ees_demand_params.year_number IS 'Год';

COMMENT ON COLUMN gs_pd.gs_pd_ees_demand_params.max_power_consumption_mw IS 'Максимальное потребление мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_ees_demand_params.peak_datetime IS 'Дата и время максимального потребления мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_ees_demand_params.avg_daily_air_temp_c IS 'Средняя дневная температура воздуха, °C';

COMMENT ON COLUMN gs_pd.gs_pd_ees_demand_params.combined_on_oes IS 'совмещенный максимум на ОЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_ees_demand_params.combined_on_ees IS 'совмещенный максимум на ЕЭС России, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_ees_demand_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_pd.gs_pd_ees_demand_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_pd.gs_pd_ees_demand_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_pd.gs_pd_ees_demand_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_pd.gs_pd_ees_demand_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_pd.gs_pd_ees_demand_params.combined_on_es IS 'совмещенный максимум на РЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_ees_demand_params.note IS 'Примечание';

COMMENT ON COLUMN gs_pd.gs_pd_ees_demand_params.perimeter_variant_code IS 'Код варианта периметра; NULL означает строку без варианта';

CREATE SEQUENCE gs_pd.gs_ees_demand_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_pd.gs_ees_demand_params_id_seq OWNED BY gs_pd.gs_pd_ees_demand_params.id;

CREATE TABLE gs_pd.gs_pd_ees_russia_demand_params (
    id integer NOT NULL,
    is_historical_maximum boolean DEFAULT false NOT NULL,
    year_number integer,
    max_power_consumption_mw numeric(25,3),
    peak_datetime timestamp with time zone,
    avg_daily_air_temp_c numeric(10,2),
    combined_on_oes numeric(25,3),
    combined_on_ees numeric(25,3),
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    combined_on_es numeric(25,3),
    note text,
    perimeter_variant_code character varying(64),
    CONSTRAINT ck_gs_ees_russia_demand_params_year_vs_hist CHECK ((((is_historical_maximum = true) AND (year_number IS NULL)) OR ((is_historical_maximum = false) AND (year_number IS NOT NULL))))
);

COMMENT ON TABLE gs_pd.gs_pd_ees_russia_demand_params IS 'Параметры нагрузки для ЕЭС России без НТ';

COMMENT ON COLUMN gs_pd.gs_pd_ees_russia_demand_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_pd.gs_pd_ees_russia_demand_params.is_historical_maximum IS 'Признак исторического максимума (true — без года)';

COMMENT ON COLUMN gs_pd.gs_pd_ees_russia_demand_params.year_number IS 'Год';

COMMENT ON COLUMN gs_pd.gs_pd_ees_russia_demand_params.max_power_consumption_mw IS 'Максимальное потребление мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_ees_russia_demand_params.peak_datetime IS 'Дата и время максимального потребления мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_ees_russia_demand_params.avg_daily_air_temp_c IS 'Средняя дневная температура воздуха, °C';

COMMENT ON COLUMN gs_pd.gs_pd_ees_russia_demand_params.combined_on_oes IS 'совмещенный максимум на ОЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_ees_russia_demand_params.combined_on_ees IS 'совмещенный максимум на ЕЭС России, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_ees_russia_demand_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_pd.gs_pd_ees_russia_demand_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_pd.gs_pd_ees_russia_demand_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_pd.gs_pd_ees_russia_demand_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_pd.gs_pd_ees_russia_demand_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_pd.gs_pd_ees_russia_demand_params.combined_on_es IS 'совмещенный максимум на РЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_ees_russia_demand_params.note IS 'Примечание';

COMMENT ON COLUMN gs_pd.gs_pd_ees_russia_demand_params.perimeter_variant_code IS 'Код варианта периметра (NULL — без варианта)';

CREATE SEQUENCE gs_pd.gs_ees_russia_demand_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_pd.gs_ees_russia_demand_params_id_seq OWNED BY gs_pd.gs_pd_ees_russia_demand_params.id;

CREATE TABLE gs_pd.gs_pd_energy_area_demand_params (
    id integer NOT NULL,
    id_energy_area integer NOT NULL,
    is_historical_maximum boolean DEFAULT false NOT NULL,
    year_number integer,
    max_power_consumption_mw numeric(25,3),
    peak_datetime timestamp with time zone,
    avg_daily_air_temp_c numeric(10,2),
    combined_on_oes numeric(25,3),
    combined_on_ees numeric(25,3),
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    combined_on_es numeric(25,3),
    note text,
    CONSTRAINT ck_gs_energy_area_demand_params_year_vs_hist CHECK ((((is_historical_maximum = true) AND (year_number IS NULL)) OR ((is_historical_maximum = false) AND (year_number IS NOT NULL))))
);

COMMENT ON TABLE gs_pd.gs_pd_energy_area_demand_params IS 'Параметры нагрузки (demand) для энергоузла (EnergyArea)';

COMMENT ON COLUMN gs_pd.gs_pd_energy_area_demand_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_pd.gs_pd_energy_area_demand_params.id_energy_area IS 'Энергорайон (FK -> gs_sys.gs_sys_energy_areas)';

COMMENT ON COLUMN gs_pd.gs_pd_energy_area_demand_params.is_historical_maximum IS 'Признак исторического максимума (true — без года)';

COMMENT ON COLUMN gs_pd.gs_pd_energy_area_demand_params.year_number IS 'Год';

COMMENT ON COLUMN gs_pd.gs_pd_energy_area_demand_params.max_power_consumption_mw IS 'Максимальное потребление мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_energy_area_demand_params.peak_datetime IS 'Дата и время максимального потребления мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_energy_area_demand_params.avg_daily_air_temp_c IS 'Средняя дневная температура воздуха, °C';

COMMENT ON COLUMN gs_pd.gs_pd_energy_area_demand_params.combined_on_oes IS 'Совмещенный максимум на ОЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_energy_area_demand_params.combined_on_ees IS 'Совмещенный максимум на ЕЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_energy_area_demand_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_pd.gs_pd_energy_area_demand_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_pd.gs_pd_energy_area_demand_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_pd.gs_pd_energy_area_demand_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_pd.gs_pd_energy_area_demand_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_pd.gs_pd_energy_area_demand_params.combined_on_es IS 'Совмещенный максимум на РЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_energy_area_demand_params.note IS 'Примечание';

CREATE SEQUENCE gs_pd.gs_energy_area_demand_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_pd.gs_energy_area_demand_params_id_seq OWNED BY gs_pd.gs_pd_energy_area_demand_params.id;

CREATE TABLE gs_pd.gs_pd_energy_system_type_demand_params (
    id integer NOT NULL,
    id_energy_system_type integer NOT NULL,
    is_historical_maximum boolean DEFAULT false NOT NULL,
    year_number integer,
    max_power_consumption_mw numeric(25,3),
    peak_datetime timestamp with time zone,
    avg_daily_air_temp_c numeric(10,2),
    combined_on_oes numeric(25,3),
    combined_on_ees numeric(25,3),
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    combined_on_es numeric(25,3),
    note text,
    perimeter_variant_code character varying(64),
    CONSTRAINT ck_gs_energy_system_type_demand_params_year_vs_hist CHECK ((((is_historical_maximum = true) AND (year_number IS NULL)) OR ((is_historical_maximum = false) AND (year_number IS NOT NULL))))
);

COMMENT ON TABLE gs_pd.gs_pd_energy_system_type_demand_params IS 'Параметры нагрузки (demand) для типа энергосистемы (EnergySystemType)';

COMMENT ON COLUMN gs_pd.gs_pd_energy_system_type_demand_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_pd.gs_pd_energy_system_type_demand_params.id_energy_system_type IS 'Тип энергосистемы (FK -> gs_sys.gs_sys_energy_system_types)';

COMMENT ON COLUMN gs_pd.gs_pd_energy_system_type_demand_params.is_historical_maximum IS 'Признак исторического максимума (true — без года)';

COMMENT ON COLUMN gs_pd.gs_pd_energy_system_type_demand_params.year_number IS 'Год';

COMMENT ON COLUMN gs_pd.gs_pd_energy_system_type_demand_params.max_power_consumption_mw IS 'Максимальное потребление мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_energy_system_type_demand_params.peak_datetime IS 'Дата и время максимального потребления мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_energy_system_type_demand_params.avg_daily_air_temp_c IS 'Средняя дневная температура воздуха, °C';

COMMENT ON COLUMN gs_pd.gs_pd_energy_system_type_demand_params.combined_on_oes IS 'совмещенный максимум на ОЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_energy_system_type_demand_params.combined_on_ees IS 'Совмещенный максимум на ЕЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_energy_system_type_demand_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_pd.gs_pd_energy_system_type_demand_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_pd.gs_pd_energy_system_type_demand_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_pd.gs_pd_energy_system_type_demand_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_pd.gs_pd_energy_system_type_demand_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_pd.gs_pd_energy_system_type_demand_params.combined_on_es IS 'совмещенный максимум на РЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_energy_system_type_demand_params.note IS 'Примечание';

COMMENT ON COLUMN gs_pd.gs_pd_energy_system_type_demand_params.perimeter_variant_code IS 'Код варианта периметра; NULL означает строку без варианта';

CREATE SEQUENCE gs_pd.gs_energy_system_type_demand_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_pd.gs_energy_system_type_demand_params_id_seq OWNED BY gs_pd.gs_pd_energy_system_type_demand_params.id;

CREATE TABLE gs_pd.gs_pd_energy_unit_demand_params (
    id integer NOT NULL,
    id_energy_unit integer NOT NULL,
    is_historical_maximum boolean DEFAULT false NOT NULL,
    year_number integer,
    max_power_consumption_mw numeric(25,3),
    peak_datetime timestamp with time zone,
    avg_daily_air_temp_c numeric(10,2),
    combined_on_oes numeric(25,3),
    combined_on_ees numeric(25,3),
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    combined_on_es numeric(25,3),
    note text,
    perimeter_variant_code character varying(64),
    CONSTRAINT ck_gs_energy_unit_demand_params_year_vs_hist CHECK ((((is_historical_maximum = true) AND (year_number IS NULL)) OR ((is_historical_maximum = false) AND (year_number IS NOT NULL))))
);

COMMENT ON TABLE gs_pd.gs_pd_energy_unit_demand_params IS 'Параметры нагрузки (demand) для энергоузла (EnergyUnit)';

COMMENT ON COLUMN gs_pd.gs_pd_energy_unit_demand_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_pd.gs_pd_energy_unit_demand_params.id_energy_unit IS 'Энергоузел (FK -> gs_sys.gs_sys_energy_units)';

COMMENT ON COLUMN gs_pd.gs_pd_energy_unit_demand_params.is_historical_maximum IS 'Признак исторического максимума (true — без года)';

COMMENT ON COLUMN gs_pd.gs_pd_energy_unit_demand_params.year_number IS 'Год';

COMMENT ON COLUMN gs_pd.gs_pd_energy_unit_demand_params.max_power_consumption_mw IS 'Максимальное потребление мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_energy_unit_demand_params.peak_datetime IS 'Дата и время максимального потребления мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_energy_unit_demand_params.avg_daily_air_temp_c IS 'Средняя дневная температура воздуха, °C';

COMMENT ON COLUMN gs_pd.gs_pd_energy_unit_demand_params.combined_on_oes IS 'Совмещенный максимум на ОЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_energy_unit_demand_params.combined_on_ees IS 'Совмещенный максимум на ЕЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_energy_unit_demand_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_pd.gs_pd_energy_unit_demand_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_pd.gs_pd_energy_unit_demand_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_pd.gs_pd_energy_unit_demand_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_pd.gs_pd_energy_unit_demand_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_pd.gs_pd_energy_unit_demand_params.combined_on_es IS 'Совмещенный максимум на РЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_energy_unit_demand_params.note IS 'Примечание';

CREATE SEQUENCE gs_pd.gs_energy_unit_demand_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_pd.gs_energy_unit_demand_params_id_seq OWNED BY gs_pd.gs_pd_energy_unit_demand_params.id;

CREATE TABLE gs_pd.gs_pd_energy_zone_demand_params (
    id integer NOT NULL,
    id_energy_zone integer NOT NULL,
    is_historical_maximum boolean DEFAULT false NOT NULL,
    year_number integer,
    max_power_consumption_mw numeric(25,3),
    peak_datetime timestamp with time zone,
    avg_daily_air_temp_c numeric(10,2),
    combined_on_oes numeric(25,3),
    combined_on_ees numeric(25,3),
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    combined_on_es numeric(25,3),
    note text,
    perimeter_variant_code character varying(64),
    CONSTRAINT ck_gs_energy_zone_demand_params_year_vs_hist CHECK ((((is_historical_maximum = true) AND (year_number IS NULL)) OR ((is_historical_maximum = false) AND (year_number IS NOT NULL))))
);

COMMENT ON TABLE gs_pd.gs_pd_energy_zone_demand_params IS 'Параметры нагрузки (demand) для энергозоны (EnergyZone)';

COMMENT ON COLUMN gs_pd.gs_pd_energy_zone_demand_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_pd.gs_pd_energy_zone_demand_params.id_energy_zone IS 'Энергозона (FK -> gs_sys.gs_sys_energy_zones)';

COMMENT ON COLUMN gs_pd.gs_pd_energy_zone_demand_params.is_historical_maximum IS 'Признак исторического максимума (true — без года)';

COMMENT ON COLUMN gs_pd.gs_pd_energy_zone_demand_params.year_number IS 'Год';

COMMENT ON COLUMN gs_pd.gs_pd_energy_zone_demand_params.max_power_consumption_mw IS 'Максимальное потребление мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_energy_zone_demand_params.peak_datetime IS 'Дата и время максимального потребления мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_energy_zone_demand_params.avg_daily_air_temp_c IS 'Средняя дневная температура воздуха, °C';

COMMENT ON COLUMN gs_pd.gs_pd_energy_zone_demand_params.combined_on_oes IS 'совмещенный максимум на ОЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_energy_zone_demand_params.combined_on_ees IS 'Совмещенный максимум на ЕЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_energy_zone_demand_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_pd.gs_pd_energy_zone_demand_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_pd.gs_pd_energy_zone_demand_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_pd.gs_pd_energy_zone_demand_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_pd.gs_pd_energy_zone_demand_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_pd.gs_pd_energy_zone_demand_params.combined_on_es IS 'совмещенный максимум на РЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_energy_zone_demand_params.note IS 'Примечание';

CREATE SEQUENCE gs_pd.gs_energy_zone_demand_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_pd.gs_energy_zone_demand_params_id_seq OWNED BY gs_pd.gs_pd_energy_zone_demand_params.id;

CREATE TABLE gs_pd.gs_pd_federal_district_demand_params (
    id integer NOT NULL,
    id_federal_district integer NOT NULL,
    is_historical_maximum boolean DEFAULT false NOT NULL,
    year_number integer,
    max_power_consumption_mw numeric(25,3),
    peak_datetime timestamp with time zone,
    avg_daily_air_temp_c numeric(10,2),
    combined_on_oes numeric(25,3),
    combined_on_ees numeric(25,3),
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    combined_on_es numeric(25,3),
    combined_on_cz numeric(25,3),
    note text,
    perimeter_variant_code character varying(64),
    CONSTRAINT ck_gs_federal_district_demand_params_year_vs_hist CHECK ((((is_historical_maximum = true) AND (year_number IS NULL)) OR ((is_historical_maximum = false) AND (year_number IS NOT NULL))))
);

COMMENT ON TABLE gs_pd.gs_pd_federal_district_demand_params IS 'Параметры нагрузки (demand) для федерального округа (FederalDistrict)';

COMMENT ON COLUMN gs_pd.gs_pd_federal_district_demand_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_pd.gs_pd_federal_district_demand_params.id_federal_district IS 'Федеральный округ (FK -> gs_sys.gs_sys_federal_districts)';

COMMENT ON COLUMN gs_pd.gs_pd_federal_district_demand_params.is_historical_maximum IS 'Признак исторического максимума (true — без года)';

COMMENT ON COLUMN gs_pd.gs_pd_federal_district_demand_params.year_number IS 'Год';

COMMENT ON COLUMN gs_pd.gs_pd_federal_district_demand_params.max_power_consumption_mw IS 'Максимальное потребление мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_federal_district_demand_params.peak_datetime IS 'Дата и время максимального потребления мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_federal_district_demand_params.avg_daily_air_temp_c IS 'Средняя дневная температура воздуха, °C';

COMMENT ON COLUMN gs_pd.gs_pd_federal_district_demand_params.combined_on_oes IS 'совмещенный максимум на ОЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_federal_district_demand_params.combined_on_ees IS 'совмещенный максимум на ЕЭС России, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_federal_district_demand_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_pd.gs_pd_federal_district_demand_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_pd.gs_pd_federal_district_demand_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_pd.gs_pd_federal_district_demand_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_pd.gs_pd_federal_district_demand_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_pd.gs_pd_federal_district_demand_params.combined_on_es IS 'совмещенный максимум на РЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_federal_district_demand_params.combined_on_cz IS 'Совмещенный максимум на ЦЗ России, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_federal_district_demand_params.note IS 'Примечание';

COMMENT ON COLUMN gs_pd.gs_pd_federal_district_demand_params.perimeter_variant_code IS 'Код варианта периметра; NULL означает строку без варианта';

CREATE SEQUENCE gs_pd.gs_federal_district_demand_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_pd.gs_federal_district_demand_params_id_seq OWNED BY gs_pd.gs_pd_federal_district_demand_params.id;

CREATE TABLE gs_pd.gs_pd_ozp_max_power_params (
    id integer NOT NULL,
    ozp_end_year integer NOT NULL,
    max_power_mw numeric(25,3),
    growth_pct numeric(12,6),
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    peak_datetime character varying(64)
);

COMMENT ON COLUMN gs_pd.gs_pd_ozp_max_power_params.peak_datetime IS 'Дата и время прохождения максимума потребления мощности, дд.мм чч:мм';

CREATE SEQUENCE gs_pd.gs_pd_ozp_max_power_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_pd.gs_pd_ozp_max_power_params_id_seq OWNED BY gs_pd.gs_pd_ozp_max_power_params.id;

CREATE TABLE gs_pd.gs_pd_regional_district_demand_params (
    id integer NOT NULL,
    id_regional_district integer NOT NULL,
    is_historical_maximum boolean DEFAULT false NOT NULL,
    year_number integer,
    max_power_consumption_mw numeric(25,3),
    peak_datetime timestamp with time zone,
    avg_daily_air_temp_c numeric(10,2),
    combined_on_oes numeric(25,3),
    combined_on_ees numeric(25,3),
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    combined_on_es numeric(25,3),
    combined_on_fo numeric(25,3),
    combined_on_cz numeric(25,3),
    note text,
    perimeter_variant_code character varying(64),
    CONSTRAINT ck_gs_regional_district_demand_params_year_vs_hist CHECK ((((is_historical_maximum = true) AND (year_number IS NULL)) OR ((is_historical_maximum = false) AND (year_number IS NOT NULL))))
);

COMMENT ON TABLE gs_pd.gs_pd_regional_district_demand_params IS 'Параметры нагрузки (demand) для субъекта РФ (RegionalDistrict)';

COMMENT ON COLUMN gs_pd.gs_pd_regional_district_demand_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_pd.gs_pd_regional_district_demand_params.id_regional_district IS 'Субъект РФ (FK -> gs_sys.gs_sys_regional_districts)';

COMMENT ON COLUMN gs_pd.gs_pd_regional_district_demand_params.is_historical_maximum IS 'Признак исторического максимума (true — без года)';

COMMENT ON COLUMN gs_pd.gs_pd_regional_district_demand_params.year_number IS 'Год';

COMMENT ON COLUMN gs_pd.gs_pd_regional_district_demand_params.max_power_consumption_mw IS 'Максимальное потребление мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_regional_district_demand_params.peak_datetime IS 'Дата и время максимального потребления мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_regional_district_demand_params.avg_daily_air_temp_c IS 'Средняя дневная температура воздуха, °C';

COMMENT ON COLUMN gs_pd.gs_pd_regional_district_demand_params.combined_on_oes IS 'Совмещенный максимум на ОЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_regional_district_demand_params.combined_on_ees IS 'Совмещенный максимум на ЕЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_regional_district_demand_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_pd.gs_pd_regional_district_demand_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_pd.gs_pd_regional_district_demand_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_pd.gs_pd_regional_district_demand_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_pd.gs_pd_regional_district_demand_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_pd.gs_pd_regional_district_demand_params.combined_on_es IS 'Совмещенный максимум на РЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_regional_district_demand_params.combined_on_fo IS 'Совмещенный максимум на ФО, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_regional_district_demand_params.combined_on_cz IS 'Совмещенный максимум на централизованную зону, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_regional_district_demand_params.note IS 'Примечание';

COMMENT ON COLUMN gs_pd.gs_pd_regional_district_demand_params.perimeter_variant_code IS 'Код варианта периметра; NULL означает строку без варианта';

CREATE TABLE gs_pd.gs_pd_regional_energy_system_demand_params (
    id integer NOT NULL,
    id_regional_energy_system integer NOT NULL,
    is_historical_maximum boolean DEFAULT false NOT NULL,
    year_number integer,
    max_power_consumption_mw numeric(25,3),
    peak_datetime timestamp with time zone,
    avg_daily_air_temp_c numeric(10,2),
    combined_on_oes numeric(25,3),
    combined_on_ees numeric(25,3),
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    combined_on_es numeric(25,3),
    combined_on_ez numeric(25,3),
    coeff_k_combined_on_oes numeric(25,6),
    coeff_k_combined_on_ees numeric(25,6),
    note text,
    combined_on_fo numeric(25,3),
    combined_on_cz numeric(25,3),
    perimeter_variant_code character varying(64),
    CONSTRAINT ck_gs_res_demand_params_year_vs_hist CHECK ((((is_historical_maximum = true) AND (year_number IS NULL)) OR ((is_historical_maximum = false) AND (year_number IS NOT NULL))))
);

COMMENT ON TABLE gs_pd.gs_pd_regional_energy_system_demand_params IS 'Параметры нагрузки (demand) для региональной энергосистемы';

COMMENT ON COLUMN gs_pd.gs_pd_regional_energy_system_demand_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_pd.gs_pd_regional_energy_system_demand_params.id_regional_energy_system IS 'Региональная энергосистема (FK -> gs_sys.gs_sys_regional_energy_systems)';

COMMENT ON COLUMN gs_pd.gs_pd_regional_energy_system_demand_params.is_historical_maximum IS 'Признак исторического максимума (true — без года)';

COMMENT ON COLUMN gs_pd.gs_pd_regional_energy_system_demand_params.year_number IS 'Год';

COMMENT ON COLUMN gs_pd.gs_pd_regional_energy_system_demand_params.max_power_consumption_mw IS 'Максимальное потребление мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_regional_energy_system_demand_params.peak_datetime IS 'Дата и время максимального потребления мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_regional_energy_system_demand_params.avg_daily_air_temp_c IS 'Средняя дневная температура воздуха, °C';

COMMENT ON COLUMN gs_pd.gs_pd_regional_energy_system_demand_params.combined_on_oes IS 'Совмещенный максимум на ОЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_regional_energy_system_demand_params.combined_on_ees IS 'Совмещенный максимум на ЕЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_regional_energy_system_demand_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_pd.gs_pd_regional_energy_system_demand_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_pd.gs_pd_regional_energy_system_demand_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_pd.gs_pd_regional_energy_system_demand_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_pd.gs_pd_regional_energy_system_demand_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_pd.gs_pd_regional_energy_system_demand_params.combined_on_es IS 'совмещенный максимум на РЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_regional_energy_system_demand_params.combined_on_ez IS 'Совмещенный максимум на энергозону, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_regional_energy_system_demand_params.coeff_k_combined_on_oes IS 'Коэффициент k для показателя «Совмещённый на ОЭС, МВт»';

COMMENT ON COLUMN gs_pd.gs_pd_regional_energy_system_demand_params.coeff_k_combined_on_ees IS 'Коэффициент k для показателя «Совмещённый на ЕЭС, МВт»';

COMMENT ON COLUMN gs_pd.gs_pd_regional_energy_system_demand_params.note IS 'Примечание';

COMMENT ON COLUMN gs_pd.gs_pd_regional_energy_system_demand_params.combined_on_fo IS 'Совмещенный максимум на ФО, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_regional_energy_system_demand_params.combined_on_cz IS 'Совмещенный максимум на ЦЗ России, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_regional_energy_system_demand_params.perimeter_variant_code IS 'Код варианта периметра (NULL — без варианта)';

CREATE TABLE gs_pd.gs_pd_russia_federation_demand_params (
    id integer NOT NULL,
    is_historical_maximum boolean DEFAULT false NOT NULL,
    year_number integer,
    max_power_consumption_mw numeric(25,3),
    peak_datetime timestamp with time zone,
    avg_daily_air_temp_c numeric(10,2),
    combined_on_oes numeric(25,3),
    combined_on_ees numeric(25,3),
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    combined_on_es numeric(25,3),
    note text,
    perimeter_variant_code character varying(64),
    CONSTRAINT ck_gs_russia_federation_demand_params_year_vs_hist CHECK ((((is_historical_maximum = true) AND (year_number IS NULL)) OR ((is_historical_maximum = false) AND (year_number IS NOT NULL))))
);

COMMENT ON TABLE gs_pd.gs_pd_russia_federation_demand_params IS 'Параметры нагрузки (demand) для Российской Федерации в целом';

COMMENT ON COLUMN gs_pd.gs_pd_russia_federation_demand_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_pd.gs_pd_russia_federation_demand_params.is_historical_maximum IS 'Признак исторического максимума (true — без года)';

COMMENT ON COLUMN gs_pd.gs_pd_russia_federation_demand_params.year_number IS 'Год';

COMMENT ON COLUMN gs_pd.gs_pd_russia_federation_demand_params.max_power_consumption_mw IS 'Максимальное потребление мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_russia_federation_demand_params.peak_datetime IS 'Дата и время максимального потребления мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_russia_federation_demand_params.avg_daily_air_temp_c IS 'Средняя дневная температура воздуха, °C';

COMMENT ON COLUMN gs_pd.gs_pd_russia_federation_demand_params.combined_on_oes IS 'совмещенный максимум на ОЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_russia_federation_demand_params.combined_on_ees IS 'совмещенный максимум на ЕЭС России, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_russia_federation_demand_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_pd.gs_pd_russia_federation_demand_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_pd.gs_pd_russia_federation_demand_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_pd.gs_pd_russia_federation_demand_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_pd.gs_pd_russia_federation_demand_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_pd.gs_pd_russia_federation_demand_params.combined_on_es IS 'совмещенный максимум на РЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_russia_federation_demand_params.note IS 'Примечание';

COMMENT ON COLUMN gs_pd.gs_pd_russia_federation_demand_params.perimeter_variant_code IS 'Код варианта периметра (NULL — без варианта)';

CREATE TABLE gs_pd.gs_pd_summary_formula_texts (
    id integer NOT NULL,
    formula_key character varying(128) NOT NULL,
    formula_text text NOT NULL,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE gs_pd.gs_pd_summary_formula_texts IS 'Переопределения текстов формул (подсказки «i») для сводок модуля «Нагрузки»';

COMMENT ON COLUMN gs_pd.gs_pd_summary_formula_texts.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_pd.gs_pd_summary_formula_texts.formula_key IS 'Ключ формулы';

COMMENT ON COLUMN gs_pd.gs_pd_summary_formula_texts.formula_text IS 'Текст формулы';

COMMENT ON COLUMN gs_pd.gs_pd_summary_formula_texts.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_pd.gs_pd_summary_formula_texts.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_pd.gs_pd_summary_formula_texts.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_pd.gs_pd_summary_formula_texts.updated_at IS 'Дата и время последнего изменения записи';

CREATE SEQUENCE gs_pd.gs_pd_summary_formula_texts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_pd.gs_pd_summary_formula_texts_id_seq OWNED BY gs_pd.gs_pd_summary_formula_texts.id;

CREATE TABLE gs_pd.gs_pd_synchronous_area_demand_params (
    id integer NOT NULL,
    id_synchronous_area integer NOT NULL,
    is_historical_maximum boolean DEFAULT false NOT NULL,
    year_number integer,
    max_power_consumption_mw numeric(25,3),
    peak_datetime timestamp with time zone,
    avg_daily_air_temp_c numeric(10,2),
    combined_on_oes numeric(25,3),
    combined_on_ees numeric(25,3),
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    combined_on_es numeric(25,3),
    note text,
    perimeter_variant_code character varying(64),
    CONSTRAINT ck_gs_synchronous_area_demand_params_year_vs_hist CHECK ((((is_historical_maximum = true) AND (year_number IS NULL)) OR ((is_historical_maximum = false) AND (year_number IS NOT NULL))))
);

COMMENT ON TABLE gs_pd.gs_pd_synchronous_area_demand_params IS 'Параметры нагрузки (demand) для синхронной зоны (SynchronousArea)';

COMMENT ON COLUMN gs_pd.gs_pd_synchronous_area_demand_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_pd.gs_pd_synchronous_area_demand_params.id_synchronous_area IS 'Синхронная зона (FK -> gs_sys.gs_sys_synchronous_areas)';

COMMENT ON COLUMN gs_pd.gs_pd_synchronous_area_demand_params.is_historical_maximum IS 'Признак исторического максимума (true — без года)';

COMMENT ON COLUMN gs_pd.gs_pd_synchronous_area_demand_params.year_number IS 'Год';

COMMENT ON COLUMN gs_pd.gs_pd_synchronous_area_demand_params.max_power_consumption_mw IS 'Максимальное потребление мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_synchronous_area_demand_params.peak_datetime IS 'Дата и время максимального потребления мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_synchronous_area_demand_params.avg_daily_air_temp_c IS 'Средняя дневная температура воздуха, °C';

COMMENT ON COLUMN gs_pd.gs_pd_synchronous_area_demand_params.combined_on_oes IS 'совмещенный максимум на ОЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_synchronous_area_demand_params.combined_on_ees IS 'Совмещенный максимум на ЕЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_synchronous_area_demand_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_pd.gs_pd_synchronous_area_demand_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_pd.gs_pd_synchronous_area_demand_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_pd.gs_pd_synchronous_area_demand_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_pd.gs_pd_synchronous_area_demand_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_pd.gs_pd_synchronous_area_demand_params.combined_on_es IS 'совмещенный максимум на РЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_synchronous_area_demand_params.note IS 'Примечание';

COMMENT ON COLUMN gs_pd.gs_pd_synchronous_area_demand_params.perimeter_variant_code IS 'Код варианта периметра; NULL означает строку без варианта';

CREATE TABLE gs_pd.gs_pd_union_energy_system_demand_params (
    id integer NOT NULL,
    id_union_energy_system integer NOT NULL,
    is_historical_maximum boolean DEFAULT false NOT NULL,
    year_number integer,
    max_power_consumption_mw numeric(25,3),
    peak_datetime timestamp with time zone,
    avg_daily_air_temp_c numeric(10,2),
    combined_on_oes numeric(25,3),
    combined_on_ees numeric(25,3),
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    combined_on_es numeric(25,3),
    calculated_max_power_mw numeric(25,3),
    calculated_combined_on_ees_mw numeric(25,3),
    coeff_k_calculated_max_power_mw numeric(25,6),
    coeff_k_combined_on_ees numeric(25,6),
    coeff_k_calculated_combined_on_ees_mw numeric(25,6),
    note text,
    perimeter_variant_code character varying(64),
    CONSTRAINT ck_gs_union_energy_system_demand_params_year_vs_hist CHECK ((((is_historical_maximum = true) AND (year_number IS NULL)) OR ((is_historical_maximum = false) AND (year_number IS NOT NULL))))
);

COMMENT ON TABLE gs_pd.gs_pd_union_energy_system_demand_params IS 'Параметры нагрузки (demand) для объединённой энергосистемы (UnionEnergySystem)';

COMMENT ON COLUMN gs_pd.gs_pd_union_energy_system_demand_params.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_pd.gs_pd_union_energy_system_demand_params.id_union_energy_system IS 'Объединённая энергосистема (FK -> gs_sys.gs_sys_union_energy_systems)';

COMMENT ON COLUMN gs_pd.gs_pd_union_energy_system_demand_params.is_historical_maximum IS 'Признак исторического максимума (true — без года)';

COMMENT ON COLUMN gs_pd.gs_pd_union_energy_system_demand_params.year_number IS 'Год';

COMMENT ON COLUMN gs_pd.gs_pd_union_energy_system_demand_params.max_power_consumption_mw IS 'Максимальное потребление мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_union_energy_system_demand_params.peak_datetime IS 'Дата и время максимального потребления мощности, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_union_energy_system_demand_params.avg_daily_air_temp_c IS 'Средняя дневная температура воздуха, °C';

COMMENT ON COLUMN gs_pd.gs_pd_union_energy_system_demand_params.combined_on_oes IS 'совмещенный максимум на ОЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_union_energy_system_demand_params.combined_on_ees IS 'Совмещенный максимум на ЕЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_union_energy_system_demand_params.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_pd.gs_pd_union_energy_system_demand_params.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_pd.gs_pd_union_energy_system_demand_params.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_pd.gs_pd_union_energy_system_demand_params.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_pd.gs_pd_union_energy_system_demand_params.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_pd.gs_pd_union_energy_system_demand_params.combined_on_es IS 'совмещенный максимум на РЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_union_energy_system_demand_params.calculated_max_power_mw IS 'Расчетный максимум ОЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_union_energy_system_demand_params.calculated_combined_on_ees_mw IS 'Расчетный совмещенный на ЕЭС, МВт';

COMMENT ON COLUMN gs_pd.gs_pd_union_energy_system_demand_params.coeff_k_calculated_max_power_mw IS 'Коэффициент k для показателя «Расчетный максимум ОЭС, МВт»';

COMMENT ON COLUMN gs_pd.gs_pd_union_energy_system_demand_params.coeff_k_combined_on_ees IS 'Коэффициент k для показателя «Совмещённый на ЕЭС, МВт»';

COMMENT ON COLUMN gs_pd.gs_pd_union_energy_system_demand_params.coeff_k_calculated_combined_on_ees_mw IS 'Коэффициент k для показателя «Расчетный совмещенный на ЕЭС, МВт»';

COMMENT ON COLUMN gs_pd.gs_pd_union_energy_system_demand_params.note IS 'Примечание';

COMMENT ON COLUMN gs_pd.gs_pd_union_energy_system_demand_params.perimeter_variant_code IS 'Код варианта периметра (NULL — без варианта)';

CREATE SEQUENCE gs_pd.gs_regional_district_demand_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_pd.gs_regional_district_demand_params_id_seq OWNED BY gs_pd.gs_pd_regional_district_demand_params.id;

CREATE SEQUENCE gs_pd.gs_regional_energy_system_demand_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_pd.gs_regional_energy_system_demand_params_id_seq OWNED BY gs_pd.gs_pd_regional_energy_system_demand_params.id;

CREATE SEQUENCE gs_pd.gs_russia_federation_demand_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_pd.gs_russia_federation_demand_params_id_seq OWNED BY gs_pd.gs_pd_russia_federation_demand_params.id;

CREATE SEQUENCE gs_pd.gs_synchronous_area_demand_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_pd.gs_synchronous_area_demand_params_id_seq OWNED BY gs_pd.gs_pd_synchronous_area_demand_params.id;

CREATE SEQUENCE gs_pd.gs_union_energy_system_demand_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_pd.gs_union_energy_system_demand_params_id_seq OWNED BY gs_pd.gs_pd_union_energy_system_demand_params.id;

CREATE TABLE gs_rs.gs_rs_calculation_workbooks (
    id integer NOT NULL,
    database_version_id integer NOT NULL,
    kind character varying(30) NOT NULL,
    source_filename text NOT NULL,
    source_sha256 character varying(64) NOT NULL,
    data json NOT NULL,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_rs_calculation_workbook_kind CHECK (((kind)::text = ANY ((ARRAY['equipment_runtime'::character varying, 'marginal_price'::character varying])::text[])))
);

CREATE SEQUENCE gs_rs.gs_rs_calculation_workbooks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_rs.gs_rs_calculation_workbooks_id_seq OWNED BY gs_rs.gs_rs_calculation_workbooks.id;

CREATE TABLE gs_rs.gs_rs_equipment_technical_characteristics (
    id integer NOT NULL,
    database_version_id integer NOT NULL,
    equipment_type character varying(20) NOT NULL,
    equipment_code character varying(100) NOT NULL,
    report_year integer NOT NULL,
    equipment_kind text,
    subject_name text,
    station_name text,
    station_number text,
    equipment_subclass text,
    equipment_brand text,
    standard_service_life text,
    extension_decision text,
    assigned_service_life text,
    replaced_element text,
    remarking_reason text,
    decommissioning_reason text,
    recommissioning text,
    commissioning_year integer,
    expected_service_life_year integer,
    last_overhaul_year integer,
    element_replacement_year integer,
    remarking_year integer,
    decommissioning_year integer,
    installed_electric_power numeric(24,8),
    nominal_active_power numeric(24,8),
    technical_min_power numeric(24,8),
    technical_max_power numeric(24,8),
    total_heat_power numeric(24,8),
    district_heat_power numeric(24,8),
    electricity_generation numeric(24,8),
    heat_output numeric(24,8),
    operating_hours_total numeric(24,8),
    operating_hours_year numeric(24,8),
    standard_start_count numeric(24,8),
    start_count_total numeric(24,8),
    start_count_year numeric(24,8),
    standard_overhaul_hours numeric(24,8),
    hours_since_overhaul numeric(24,8),
    extension_count numeric(24,8),
    extra_values json NOT NULL,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    machine_id integer,
    match_status character varying(20) DEFAULT 'not_checked'::character varying NOT NULL,
    match_details json DEFAULT '{}'::json NOT NULL,
    pgu_machine_id integer,
    design_head numeric(24,8),
    steam_capacity numeric(24,8),
    heat_power numeric(24,8),
    fuel_project text,
    fuel_main text,
    fuel_reserve text,
    efficiency_gross numeric(24,8),
    water_consumption numeric(24,8),
    operation_mode text,
    CONSTRAINT ck_rs_equipment_type CHECK (((equipment_type)::text = ANY ((ARRAY['steam'::character varying, 'gas'::character varying, 'hydro'::character varying, 'boiler_energy'::character varying, 'boiler_water'::character varying])::text[]))),
    CONSTRAINT ck_rs_turbine_match_status CHECK (((match_status)::text = ANY ((ARRAY['not_checked'::character varying, 'matched'::character varying, 'partial'::character varying, 'ambiguous'::character varying, 'unmatched'::character varying])::text[])))
);

CREATE TABLE gs_rs.gs_rs_technical_inspection_codes (
    id integer NOT NULL,
    database_version_id integer NOT NULL,
    equipment_code character varying(100) NOT NULL,
    machine_id integer NOT NULL,
    pgu_machine_id integer,
    created_by character varying(255),
    modified_by character varying(255)
);

CREATE SEQUENCE gs_rs.gs_rs_technical_inspection_codes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_rs.gs_rs_technical_inspection_codes_id_seq OWNED BY gs_rs.gs_rs_technical_inspection_codes.id;

CREATE TABLE gs_rs.gs_rs_territory_discount_rates (
    database_version_id integer NOT NULL,
    year_values json NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by character varying(255),
    modified_by character varying(255)
);

CREATE TABLE gs_rs.gs_rs_territory_inputs (
    id integer NOT NULL,
    database_version_id integer NOT NULL,
    energy_zone_id integer NOT NULL,
    years json NOT NULL,
    rows json NOT NULL,
    source_filename character varying(255) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by character varying(255),
    modified_by character varying(255),
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE gs_rs.gs_rs_territory_inputs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_rs.gs_rs_territory_inputs_id_seq OWNED BY gs_rs.gs_rs_territory_inputs.id;

CREATE TABLE gs_rs.gs_rs_territory_technologies (
    id integer NOT NULL,
    database_version_id integer NOT NULL,
    name text NOT NULL,
    source_row integer NOT NULL,
    source_filename text NOT NULL,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    energy_zone_id integer NOT NULL,
    technology_number integer NOT NULL,
    unit_power double precision,
    minimum_power double precision,
    capacity_factor_1 double precision,
    capacity_factor_2 double precision,
    capacity_factor_3 double precision,
    capacity_factor_4 double precision,
    standard_deviation double precision,
    capital_cost double precision,
    modernization_cost double precision,
    fuel_cost_winter double precision,
    fuel_cost_summer double precision,
    fixed_cost double precision,
    transmission_cost double precision,
    outage_probability_winter double precision,
    outage_probability_summer double precision,
    co2_per_fuel double precision,
    co2_per_energy double precision,
    quantity_min double precision,
    quantity_mod double precision,
    quantity_max double precision
);

CREATE SEQUENCE gs_rs.gs_rs_territory_technologies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_rs.gs_rs_territory_technologies_id_seq OWNED BY gs_rs.gs_rs_territory_technologies.id;

CREATE TABLE gs_rs.gs_rs_territory_transfer_sections (
    id integer NOT NULL,
    database_version_id integer NOT NULL,
    name text NOT NULL,
    source_row integer NOT NULL,
    source_filename text NOT NULL,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    zone_membership json NOT NULL,
    zone_paths json NOT NULL,
    forward_limit double precision NOT NULL,
    reverse_limit double precision NOT NULL
);

CREATE SEQUENCE gs_rs.gs_rs_territory_transfer_sections_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_rs.gs_rs_territory_transfer_sections_id_seq OWNED BY gs_rs.gs_rs_territory_transfer_sections.id;

CREATE SEQUENCE gs_rs.gs_rs_turbine_technical_characteristics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_rs.gs_rs_turbine_technical_characteristics_id_seq OWNED BY gs_rs.gs_rs_equipment_technical_characteristics.id;

CREATE TABLE gs_sys.gs_sys_condition_types (
    id integer NOT NULL,
    name character varying(80) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    ref_uuid character varying(36) NOT NULL
);

COMMENT ON TABLE gs_sys.gs_sys_condition_types IS 'справочник типов состояния оборудования/станции';

COMMENT ON COLUMN gs_sys.gs_sys_condition_types.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_condition_types.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_condition_types.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_condition_types.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_condition_types.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_condition_types.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_condition_types.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_condition_types.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_condition_types.ref_uuid IS 'стабильный UUID справочной сущности';

CREATE SEQUENCE gs_sys.condition_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.condition_types_id_seq OWNED BY gs_sys.gs_sys_condition_types.id;

CREATE TABLE gs_sys.gs_sys_database_versions (
    id integer NOT NULL,
    version_number character varying(30) NOT NULL,
    description text,
    is_active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    snapshot_path character varying(500),
    snapshot_size bigint,
    parent_version_id integer,
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_sys.gs_sys_database_versions IS 'версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_database_versions.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_database_versions.version_number IS 'номер версии';

COMMENT ON COLUMN gs_sys.gs_sys_database_versions.description IS 'описание';

COMMENT ON COLUMN gs_sys.gs_sys_database_versions.is_active IS 'признак активности записи';

COMMENT ON COLUMN gs_sys.gs_sys_database_versions.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_database_versions.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_database_versions.snapshot_path IS 'путь к файлу снимка базы данных при хранении снимка в виде файла (опционально)';

COMMENT ON COLUMN gs_sys.gs_sys_database_versions.snapshot_size IS 'размер файла снимка базы данных при хранении снимка в виде файла (опционально)';

COMMENT ON COLUMN gs_sys.gs_sys_database_versions.parent_version_id IS 'родительская версия (на основе какой версии создана)';

COMMENT ON COLUMN gs_sys.gs_sys_database_versions.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_database_versions.modified_by IS 'пользователь, последним изменивший запись';

CREATE SEQUENCE gs_sys.database_versions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.database_versions_id_seq OWNED BY gs_sys.gs_sys_database_versions.id;

CREATE TABLE gs_sys.gs_sys_energy_areas (
    id integer NOT NULL,
    name character varying(256) NOT NULL,
    id_regional_district integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    ref_uuid character varying(36) NOT NULL
);

COMMENT ON TABLE gs_sys.gs_sys_energy_areas IS 'энергоузлы';

COMMENT ON COLUMN gs_sys.gs_sys_energy_areas.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_energy_areas.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_energy_areas.id_regional_district IS 'идентификатор субъекта РФ (FK)';

COMMENT ON COLUMN gs_sys.gs_sys_energy_areas.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_energy_areas.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_energy_areas.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_energy_areas.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_energy_areas.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_energy_areas.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_energy_areas.ref_uuid IS 'стабильный UUID справочной сущности';

CREATE SEQUENCE gs_sys.energy_areas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.energy_areas_id_seq OWNED BY gs_sys.gs_sys_energy_areas.id;

CREATE TABLE gs_sys.gs_sys_energy_system_types (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    ref_uuid character varying(36) NOT NULL
);

COMMENT ON TABLE gs_sys.gs_sys_energy_system_types IS 'типы энергосистем';

COMMENT ON COLUMN gs_sys.gs_sys_energy_system_types.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_energy_system_types.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_energy_system_types.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_energy_system_types.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_energy_system_types.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_energy_system_types.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_energy_system_types.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_energy_system_types.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_energy_system_types.ref_uuid IS 'стабильный UUID справочной сущности';

CREATE SEQUENCE gs_sys.energy_system_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.energy_system_types_id_seq OWNED BY gs_sys.gs_sys_energy_system_types.id;

CREATE TABLE gs_sys.gs_sys_energy_units (
    id integer NOT NULL,
    name character varying(256) NOT NULL,
    id_regional_district integer NOT NULL,
    id_regional_energy_system integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    ref_uuid character varying(36) NOT NULL,
    name_rp character varying(255) NOT NULL,
    name_dp character varying(255) NOT NULL,
    name_dat character varying(255) DEFAULT ''::character varying NOT NULL
);

COMMENT ON TABLE gs_sys.gs_sys_energy_units IS 'энергорайоны';

COMMENT ON COLUMN gs_sys.gs_sys_energy_units.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_energy_units.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_energy_units.id_regional_district IS 'идентификатор субъекта РФ (FK)';

COMMENT ON COLUMN gs_sys.gs_sys_energy_units.id_regional_energy_system IS 'идентификатор региональной энергосистемы (FK)';

COMMENT ON COLUMN gs_sys.gs_sys_energy_units.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_energy_units.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_energy_units.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_energy_units.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_energy_units.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_energy_units.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_energy_units.ref_uuid IS 'стабильный UUID справочной сущности';

COMMENT ON COLUMN gs_sys.gs_sys_energy_units.name_rp IS 'полное наименование в родительном падеже';

COMMENT ON COLUMN gs_sys.gs_sys_energy_units.name_dp IS 'полное наименование в дательном падеже';

CREATE SEQUENCE gs_sys.energy_units_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.energy_units_id_seq OWNED BY gs_sys.gs_sys_energy_units.id;

CREATE TABLE gs_sys.gs_sys_energy_zones (
    id integer NOT NULL,
    number character varying(256) NOT NULL,
    name character varying(256) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    ref_uuid character varying(36) NOT NULL
);

COMMENT ON TABLE gs_sys.gs_sys_energy_zones IS 'энергозоны';

COMMENT ON COLUMN gs_sys.gs_sys_energy_zones.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_energy_zones.number IS 'номер';

COMMENT ON COLUMN gs_sys.gs_sys_energy_zones.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_energy_zones.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_energy_zones.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_energy_zones.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_energy_zones.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_energy_zones.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_energy_zones.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_energy_zones.ref_uuid IS 'стабильный UUID справочной сущности';

CREATE SEQUENCE gs_sys.energy_zones_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.energy_zones_id_seq OWNED BY gs_sys.gs_sys_energy_zones.id;

CREATE TABLE gs_sys.gs_sys_equipment_groups (
    id integer NOT NULL,
    name character varying(80) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    id_technology_type integer,
    id_technology_availability integer,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    display_order integer,
    ref_uuid character varying(36) NOT NULL
);

COMMENT ON TABLE gs_sys.gs_sys_equipment_groups IS 'типы групп оборудования';

COMMENT ON COLUMN gs_sys.gs_sys_equipment_groups.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_equipment_groups.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_equipment_groups.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_equipment_groups.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_equipment_groups.id_technology_type IS 'идентификатор типа технологии (FK)';

COMMENT ON COLUMN gs_sys.gs_sys_equipment_groups.id_technology_availability IS 'идентификатор доступности технологии (FK)';

COMMENT ON COLUMN gs_sys.gs_sys_equipment_groups.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_equipment_groups.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_equipment_groups.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_equipment_groups.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_equipment_groups.display_order IS 'порядок отображения';

COMMENT ON COLUMN gs_sys.gs_sys_equipment_groups.ref_uuid IS 'стабильный UUID справочной сущности';

CREATE SEQUENCE gs_sys.equipment_groups_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.equipment_groups_id_seq OWNED BY gs_sys.gs_sys_equipment_groups.id;

CREATE TABLE gs_sys.gs_sys_federal_districts (
    id integer NOT NULL,
    name character varying(80) NOT NULL,
    name_full character varying(80),
    name_abr character varying(80),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    display_order integer,
    ref_uuid character varying(36) NOT NULL
);

COMMENT ON TABLE gs_sys.gs_sys_federal_districts IS 'федеральные округа';

COMMENT ON COLUMN gs_sys.gs_sys_federal_districts.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_federal_districts.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_federal_districts.name_full IS 'полное наименование';

COMMENT ON COLUMN gs_sys.gs_sys_federal_districts.name_abr IS 'аббревиатура';

COMMENT ON COLUMN gs_sys.gs_sys_federal_districts.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_federal_districts.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_federal_districts.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_federal_districts.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_federal_districts.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_federal_districts.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_federal_districts.display_order IS 'порядок отображения';

COMMENT ON COLUMN gs_sys.gs_sys_federal_districts.ref_uuid IS 'стабильный UUID справочной сущности';

CREATE SEQUENCE gs_sys.federal_districts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.federal_districts_id_seq OWNED BY gs_sys.gs_sys_federal_districts.id;

CREATE TABLE gs_sys.gs_sys_fuel_types (
    id integer NOT NULL,
    name character varying(80) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    ref_uuid character varying(36) NOT NULL,
    nazvl character varying(80),
    display_order integer
);

COMMENT ON TABLE gs_sys.gs_sys_fuel_types IS 'типы топлива';

COMMENT ON COLUMN gs_sys.gs_sys_fuel_types.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_fuel_types.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_fuel_types.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_fuel_types.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_fuel_types.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_fuel_types.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_fuel_types.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_fuel_types.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_fuel_types.ref_uuid IS 'стабильный UUID справочной сущности';

COMMENT ON COLUMN gs_sys.gs_sys_fuel_types.nazvl IS 'наименование в БД топливо';

COMMENT ON COLUMN gs_sys.gs_sys_fuel_types.display_order IS 'порядок отображения';

CREATE SEQUENCE gs_sys.fuel_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.fuel_types_id_seq OWNED BY gs_sys.gs_sys_fuel_types.id;

CREATE TABLE gs_sys.gs_sys_fuels (
    id integer NOT NULL,
    name character varying(80) NOT NULL,
    id_fuel_type integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    ref_uuid character varying(36) NOT NULL,
    nazvl character varying(80),
    kmbur character varying(80),
    parent_id integer,
    kod integer
);

COMMENT ON TABLE gs_sys.gs_sys_fuels IS 'виды топлива';

COMMENT ON COLUMN gs_sys.gs_sys_fuels.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_fuels.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_fuels.id_fuel_type IS 'идентификатор типа топлива (FK)';

COMMENT ON COLUMN gs_sys.gs_sys_fuels.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_fuels.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_fuels.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_fuels.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_fuels.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_fuels.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_fuels.ref_uuid IS 'стабильный UUID справочной сущности';

COMMENT ON COLUMN gs_sys.gs_sys_fuels.nazvl IS 'наименование в БД топливо';

COMMENT ON COLUMN gs_sys.gs_sys_fuels.kmbur IS 'название типа угольного топлива из базы топливо (каменный/бурый)';

CREATE SEQUENCE gs_sys.fuels_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.fuels_id_seq OWNED BY gs_sys.gs_sys_fuels.id;

CREATE TABLE gs_sys.gs_sys_companies (
    id integer NOT NULL,
    name character varying(80) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    name_short character varying(80),
    ref_uuid character varying(36) NOT NULL
);

COMMENT ON TABLE gs_sys.gs_sys_companies IS 'справочник компаний';

COMMENT ON COLUMN gs_sys.gs_sys_companies.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_companies.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_companies.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_companies.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_companies.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_companies.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_companies.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_companies.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_companies.name_short IS 'наименование сокращенное';

COMMENT ON COLUMN gs_sys.gs_sys_companies.ref_uuid IS 'стабильный UUID справочной сущности';

CREATE SEQUENCE gs_sys.gen_companies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.gen_companies_id_seq OWNED BY gs_sys.gs_sys_companies.id;

CREATE TABLE gs_sys.gs_sys_tep_price_conversion_coefficients (
    id integer NOT NULL,
    id_year integer NOT NULL,
    coefficient numeric(24,10),
    database_version_id integer NOT NULL,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE gs_sys.gs_sys_tep_price_conversion_coefficients IS 'коэффициенты для перевода цен исходных данных ТЭП в цены текущего года (характеристика актуальных площадок размещения новых электростанций: АЭС, ГЭС, ГАЭС, ТЭС и др.)';

COMMENT ON COLUMN gs_sys.gs_sys_tep_price_conversion_coefficients.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_tep_price_conversion_coefficients.id_year IS 'идентификатор года';

COMMENT ON COLUMN gs_sys.gs_sys_tep_price_conversion_coefficients.coefficient IS 'коэффициент';

COMMENT ON COLUMN gs_sys.gs_sys_tep_price_conversion_coefficients.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_tep_price_conversion_coefficients.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_tep_price_conversion_coefficients.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_tep_price_conversion_coefficients.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_tep_price_conversion_coefficients.updated_at IS 'дата и время последнего обновления записи';

CREATE SEQUENCE gs_sys.ges_tep_price_conversion_coefficients_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.ges_tep_price_conversion_coefficients_id_seq OWNED BY gs_sys.gs_sys_tep_price_conversion_coefficients.id;

CREATE TABLE gs_sys.gs_sys_business_units (
    id integer NOT NULL,
    display_order integer,
    name character varying(80) NOT NULL,
    name_full character varying(80),
    name_abr character varying(80),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    ref_uuid character varying(36) NOT NULL
);

COMMENT ON TABLE gs_sys.gs_sys_business_units IS 'справочник бизнес-единиц для подсистемы топлива';

COMMENT ON COLUMN gs_sys.gs_sys_business_units.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_business_units.display_order IS 'порядок отображения';

COMMENT ON COLUMN gs_sys.gs_sys_business_units.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_business_units.name_full IS 'полное наименование';

COMMENT ON COLUMN gs_sys.gs_sys_business_units.name_abr IS 'аббревиатура';

COMMENT ON COLUMN gs_sys.gs_sys_business_units.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_business_units.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_business_units.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_business_units.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_business_units.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_business_units.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_business_units.ref_uuid IS 'стабильный UUID справочной сущности';

CREATE SEQUENCE gs_sys.gs_business_units_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.gs_business_units_id_seq OWNED BY gs_sys.gs_sys_business_units.id;

CREATE VIEW gs_sys.gs_database_versions AS
 SELECT gs_sys_database_versions.id,
    gs_sys_database_versions.version_number,
    gs_sys_database_versions.description,
    gs_sys_database_versions.is_active,
    gs_sys_database_versions.created_at,
    gs_sys_database_versions.updated_at,
    gs_sys_database_versions.snapshot_path,
    gs_sys_database_versions.snapshot_size,
    gs_sys_database_versions.parent_version_id,
    gs_sys_database_versions.created_by,
    gs_sys_database_versions.modified_by
   FROM gs_sys.gs_sys_database_versions;

COMMENT ON VIEW gs_sys.gs_database_versions IS 'Версии базы данных и сведения о снимках версий';

COMMENT ON COLUMN gs_sys.gs_database_versions.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_database_versions.version_number IS 'Номер версии базы данных';

COMMENT ON COLUMN gs_sys.gs_database_versions.description IS 'Описание версии базы данных';

COMMENT ON COLUMN gs_sys.gs_database_versions.is_active IS 'Признак активной версии базы данных';

COMMENT ON COLUMN gs_sys.gs_database_versions.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_database_versions.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_database_versions.snapshot_path IS 'Путь к файлу снимка версии базы данных';

COMMENT ON COLUMN gs_sys.gs_database_versions.snapshot_size IS 'Размер файла снимка версии базы данных в байтах';

COMMENT ON COLUMN gs_sys.gs_database_versions.parent_version_id IS 'Родительская версия, на основе которой создана текущая';

COMMENT ON COLUMN gs_sys.gs_database_versions.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_database_versions.modified_by IS 'пользователь, последним изменивший запись';

CREATE TABLE gs_sys.gs_sys_departments (
    id integer NOT NULL,
    display_order integer,
    name character varying(80) NOT NULL,
    name_full character varying(80),
    name_abr character varying(80),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    ref_uuid character varying(36) NOT NULL
);

COMMENT ON TABLE gs_sys.gs_sys_departments IS 'справочник департаментов для подсистемы топлива';

COMMENT ON COLUMN gs_sys.gs_sys_departments.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_departments.display_order IS 'порядок отображения';

COMMENT ON COLUMN gs_sys.gs_sys_departments.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_departments.name_full IS 'полное наименование';

COMMENT ON COLUMN gs_sys.gs_sys_departments.name_abr IS 'аббревиатура';

COMMENT ON COLUMN gs_sys.gs_sys_departments.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_departments.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_departments.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_departments.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_departments.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_departments.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_departments.ref_uuid IS 'стабильный UUID справочной сущности';

CREATE SEQUENCE gs_sys.gs_departments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.gs_departments_id_seq OWNED BY gs_sys.gs_sys_departments.id;

CREATE TABLE gs_sys.gs_sys_refdata_entities (
    id integer NOT NULL,
    entity_type character varying(80) NOT NULL,
    entity_id integer NOT NULL,
    database_version_id integer,
    ref_uuid character varying(36) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_sys.gs_sys_refdata_entities IS 'перечень справочников, для которых ведется история изменений';

COMMENT ON COLUMN gs_sys.gs_sys_refdata_entities.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_refdata_entities.entity_type IS 'тип сущности';

COMMENT ON COLUMN gs_sys.gs_sys_refdata_entities.entity_id IS 'идентификатор сущности';

COMMENT ON COLUMN gs_sys.gs_sys_refdata_entities.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_refdata_entities.ref_uuid IS 'стабильный UUID справочной сущности';

COMMENT ON COLUMN gs_sys.gs_sys_refdata_entities.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_refdata_entities.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_refdata_entities.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_refdata_entities.modified_by IS 'пользователь, последним изменивший запись';

CREATE SEQUENCE gs_sys.gs_refdata_entities_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.gs_refdata_entities_id_seq OWNED BY gs_sys.gs_sys_refdata_entities.id;

CREATE TABLE gs_sys.gs_sys_refdata_entity_years (
    id integer NOT NULL,
    refdata_entity_id integer NOT NULL,
    year integer NOT NULL,
    database_version_id integer,
    payload json,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by character varying(255),
    modified_by character varying(255)
);

COMMENT ON TABLE gs_sys.gs_sys_refdata_entity_years IS 'связь справочников с годами, по которым ведется история изменений';

COMMENT ON COLUMN gs_sys.gs_sys_refdata_entity_years.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_refdata_entity_years.refdata_entity_id IS 'идентификатор сущности справочных данных';

COMMENT ON COLUMN gs_sys.gs_sys_refdata_entity_years.year IS 'год';

COMMENT ON COLUMN gs_sys.gs_sys_refdata_entity_years.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_refdata_entity_years.payload IS 'годовой снимок данных (структура зависит от типа сущности)';

COMMENT ON COLUMN gs_sys.gs_sys_refdata_entity_years.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_refdata_entity_years.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_refdata_entity_years.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_refdata_entity_years.modified_by IS 'пользователь, последним изменивший запись';

CREATE SEQUENCE gs_sys.gs_refdata_entity_years_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.gs_refdata_entity_years_id_seq OWNED BY gs_sys.gs_sys_refdata_entity_years.id;

CREATE TABLE gs_sys.gs_sys_economic_activity_types (
    id integer NOT NULL,
    display_order integer,
    name character varying(255),
    ref_uuid character varying(36) NOT NULL,
    version integer DEFAULT 1 NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    name_2 character varying(255)
);

COMMENT ON TABLE gs_sys.gs_sys_economic_activity_types IS 'Справочник видов экономической деятельности (ВЭД)';

COMMENT ON COLUMN gs_sys.gs_sys_economic_activity_types.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_sys.gs_sys_economic_activity_types.display_order IS 'Порядок отображения';

COMMENT ON COLUMN gs_sys.gs_sys_economic_activity_types.name IS 'Вид экономической деятельности';

COMMENT ON COLUMN gs_sys.gs_sys_economic_activity_types.ref_uuid IS 'Стабильный UUID записи справочника (единый между версиями БД)';

COMMENT ON COLUMN gs_sys.gs_sys_economic_activity_types.version IS 'Номер версии записи (оптимистическая блокировка)';

COMMENT ON COLUMN gs_sys.gs_sys_economic_activity_types.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

COMMENT ON COLUMN gs_sys.gs_sys_economic_activity_types.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_economic_activity_types.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_economic_activity_types.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_economic_activity_types.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_sys.gs_sys_economic_activity_types.name_2 IS 'Вид экономической деятельности_2';

CREATE SEQUENCE gs_sys.gs_sys_economic_activity_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.gs_sys_economic_activity_types_id_seq OWNED BY gs_sys.gs_sys_economic_activity_types.id;

CREATE TABLE gs_sys.gs_sys_electricity_production_cost_types (
    id integer NOT NULL,
    cost_code integer,
    name character varying(255),
    ref_uuid character varying(36) NOT NULL,
    version integer DEFAULT 1 NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE gs_sys.gs_sys_electricity_production_cost_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.gs_sys_electricity_production_cost_types_id_seq OWNED BY gs_sys.gs_sys_electricity_production_cost_types.id;

CREATE TABLE gs_sys.gs_sys_entity_perimeter_bindings (
    id integer NOT NULL,
    entity_kind character varying(64) NOT NULL,
    entity_name character varying(255) NOT NULL,
    label_prefix character varying(255),
    sort_order integer DEFAULT 0 NOT NULL,
    id_perimeter_variant integer NOT NULL,
    ref_uuid character varying(36) NOT NULL,
    version integer DEFAULT 1 NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE gs_sys.gs_sys_entity_perimeter_bindings IS 'связи вариантов периметра с объектами разных уровней: ЕЭС России, ОЭС, синхронными зонами, федеральными округами, региональными энергосистемами и другими периметрами';

COMMENT ON COLUMN gs_sys.gs_sys_entity_perimeter_bindings.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_entity_perimeter_bindings.entity_kind IS 'вид сущности';

COMMENT ON COLUMN gs_sys.gs_sys_entity_perimeter_bindings.entity_name IS 'наименование (как в справочнике)';

COMMENT ON COLUMN gs_sys.gs_sys_entity_perimeter_bindings.label_prefix IS 'префикс подписи на сводке';

COMMENT ON COLUMN gs_sys.gs_sys_entity_perimeter_bindings.sort_order IS 'порядок сортировки';

COMMENT ON COLUMN gs_sys.gs_sys_entity_perimeter_bindings.id_perimeter_variant IS 'идентификатор варианта периметра';

COMMENT ON COLUMN gs_sys.gs_sys_entity_perimeter_bindings.ref_uuid IS 'стабильный UUID справочной сущности';

COMMENT ON COLUMN gs_sys.gs_sys_entity_perimeter_bindings.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_entity_perimeter_bindings.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_entity_perimeter_bindings.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_entity_perimeter_bindings.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_entity_perimeter_bindings.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_entity_perimeter_bindings.updated_at IS 'дата и время последнего обновления записи';

CREATE SEQUENCE gs_sys.gs_sys_entity_perimeter_bindings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.gs_sys_entity_perimeter_bindings_id_seq OWNED BY gs_sys.gs_sys_entity_perimeter_bindings.id;

CREATE TABLE gs_sys.gs_sys_foreign_border_countries (
    id integer NOT NULL,
    display_order integer,
    name character varying(255) NOT NULL,
    ref_uuid character varying(36) NOT NULL,
    version integer DEFAULT 1 NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE gs_sys.gs_sys_foreign_border_countries IS 'Справочник зарубежных стран, имеющих общие границы с РФ';

COMMENT ON COLUMN gs_sys.gs_sys_foreign_border_countries.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_sys.gs_sys_foreign_border_countries.display_order IS 'Порядок отображения';

COMMENT ON COLUMN gs_sys.gs_sys_foreign_border_countries.name IS 'Наименование зарубежной страны, имеющей общую границу с РФ';

COMMENT ON COLUMN gs_sys.gs_sys_foreign_border_countries.ref_uuid IS 'Стабильный UUID записи справочника';

COMMENT ON COLUMN gs_sys.gs_sys_foreign_border_countries.version IS 'Номер версии записи для оптимистической блокировки';

COMMENT ON COLUMN gs_sys.gs_sys_foreign_border_countries.database_version_id IS 'Версия базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_foreign_border_countries.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_foreign_border_countries.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_foreign_border_countries.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_foreign_border_countries.updated_at IS 'Дата и время последнего изменения записи';

CREATE SEQUENCE gs_sys.gs_sys_foreign_border_countries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.gs_sys_foreign_border_countries_id_seq OWNED BY gs_sys.gs_sys_foreign_border_countries.id;

CREATE TABLE gs_sys.gs_sys_machine_types (
    id integer NOT NULL,
    name character varying(80),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    ref_uuid character varying(36) NOT NULL
);

COMMENT ON TABLE gs_sys.gs_sys_machine_types IS 'типы агрегатов';

COMMENT ON COLUMN gs_sys.gs_sys_machine_types.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_machine_types.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_machine_types.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_machine_types.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_machine_types.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_machine_types.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_machine_types.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_machine_types.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_machine_types.ref_uuid IS 'стабильный UUID справочной сущности';

CREATE TABLE gs_sys.gs_sys_perimeter_variants (
    id integer NOT NULL,
    code character varying(64) NOT NULL,
    label_suffix character varying(255) NOT NULL,
    effective_from_year integer,
    effective_to_year integer,
    is_territorial_base boolean DEFAULT false NOT NULL,
    display_order integer,
    note text,
    ref_uuid character varying(36) NOT NULL,
    version integer DEFAULT 1 NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

COMMENT ON TABLE gs_sys.gs_sys_perimeter_variants IS 'варианты периметра';

COMMENT ON COLUMN gs_sys.gs_sys_perimeter_variants.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_perimeter_variants.code IS 'код';

COMMENT ON COLUMN gs_sys.gs_sys_perimeter_variants.label_suffix IS 'суффикс подписи варианта периметра';

COMMENT ON COLUMN gs_sys.gs_sys_perimeter_variants.effective_from_year IS 'действует с года';

COMMENT ON COLUMN gs_sys.gs_sys_perimeter_variants.effective_to_year IS 'действует по год';

COMMENT ON COLUMN gs_sys.gs_sys_perimeter_variants.is_territorial_base IS 'признак территориальной базы';

COMMENT ON COLUMN gs_sys.gs_sys_perimeter_variants.display_order IS 'порядок отображения';

COMMENT ON COLUMN gs_sys.gs_sys_perimeter_variants.note IS 'примечание';

COMMENT ON COLUMN gs_sys.gs_sys_perimeter_variants.ref_uuid IS 'стабильный UUID справочной сущности';

COMMENT ON COLUMN gs_sys.gs_sys_perimeter_variants.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_perimeter_variants.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_perimeter_variants.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_perimeter_variants.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_perimeter_variants.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_perimeter_variants.updated_at IS 'дата и время последнего обновления записи';

CREATE SEQUENCE gs_sys.gs_sys_perimeter_variants_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.gs_sys_perimeter_variants_id_seq OWNED BY gs_sys.gs_sys_perimeter_variants.id;

CREATE TABLE gs_sys.gs_sys_pgu_tes_machine_types (
    id integer NOT NULL,
    name character varying(80) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    ref_uuid character varying(36) NOT NULL
);

COMMENT ON TABLE gs_sys.gs_sys_pgu_tes_machine_types IS 'типы агрегатов ПГУ: ГТ/ПТ';

COMMENT ON COLUMN gs_sys.gs_sys_pgu_tes_machine_types.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_pgu_tes_machine_types.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_pgu_tes_machine_types.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_pgu_tes_machine_types.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_pgu_tes_machine_types.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_pgu_tes_machine_types.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_pgu_tes_machine_types.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_pgu_tes_machine_types.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_pgu_tes_machine_types.ref_uuid IS 'стабильный UUID справочной сущности';

CREATE TABLE gs_sys.gs_sys_regional_district_regional_energy_system (
    regional_district_id integer NOT NULL,
    regional_energy_system_id integer NOT NULL,
    database_version_id integer
);

COMMENT ON TABLE gs_sys.gs_sys_regional_district_regional_energy_system IS 'таблица связи субъектов РФ с региональными энергосистемами. Каждая запись задает связь одного субъекта РФ с одной региональной энергосистемой.';

COMMENT ON COLUMN gs_sys.gs_sys_regional_district_regional_energy_system.regional_district_id IS 'идентификатор субъекта РФ';

COMMENT ON COLUMN gs_sys.gs_sys_regional_district_regional_energy_system.regional_energy_system_id IS 'идентификатор региональной энергосистемы';

COMMENT ON COLUMN gs_sys.gs_sys_regional_district_regional_energy_system.database_version_id IS 'идентификатор версии базы данных';

CREATE TABLE gs_sys.gs_sys_regional_districts (
    id integer NOT NULL,
    region_number character varying(3),
    name character varying(80) NOT NULL,
    name_full character varying(255) NOT NULL,
    id_federal_district integer,
    id_energy_zone integer,
    id_synchronous_area integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    region_id character varying(3),
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    name_dp character varying(255) NOT NULL,
    name_rp character varying(255) NOT NULL,
    ref_uuid character varying(36) NOT NULL
);

COMMENT ON TABLE gs_sys.gs_sys_regional_districts IS 'субъекты РФ';

COMMENT ON COLUMN gs_sys.gs_sys_regional_districts.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_regional_districts.region_number IS 'номер региона РФ (может быть пустым)';

COMMENT ON COLUMN gs_sys.gs_sys_regional_districts.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_regional_districts.name_full IS 'полное наименование';

COMMENT ON COLUMN gs_sys.gs_sys_regional_districts.id_federal_district IS 'идентификатор федерального округа (FK)';

COMMENT ON COLUMN gs_sys.gs_sys_regional_districts.id_energy_zone IS 'идентификатор энергозоны (FK)';

COMMENT ON COLUMN gs_sys.gs_sys_regional_districts.id_synchronous_area IS 'идентификатор синхронной зоны (FK)';

COMMENT ON COLUMN gs_sys.gs_sys_regional_districts.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_regional_districts.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_regional_districts.region_id IS 'номер порядковый (может быть пустым)';

COMMENT ON COLUMN gs_sys.gs_sys_regional_districts.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_regional_districts.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_regional_districts.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_regional_districts.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_regional_districts.name_dp IS 'полное наименование в дательном падеже';

COMMENT ON COLUMN gs_sys.gs_sys_regional_districts.name_rp IS 'полное наименование в родительном падеже';

COMMENT ON COLUMN gs_sys.gs_sys_regional_districts.ref_uuid IS 'стабильный UUID справочной сущности';

CREATE TABLE gs_sys.gs_sys_regional_energy_systems (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    name_full character varying(255) NOT NULL,
    id_union_energy_system integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    name_rp character varying(255) NOT NULL,
    ref_uuid character varying(36) NOT NULL
);

COMMENT ON TABLE gs_sys.gs_sys_regional_energy_systems IS 'региональные энергосистемы';

COMMENT ON COLUMN gs_sys.gs_sys_regional_energy_systems.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_regional_energy_systems.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_regional_energy_systems.name_full IS 'полное наименование';

COMMENT ON COLUMN gs_sys.gs_sys_regional_energy_systems.id_union_energy_system IS 'идентификатор объединенной энергосистемы (FK)';

COMMENT ON COLUMN gs_sys.gs_sys_regional_energy_systems.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_regional_energy_systems.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_regional_energy_systems.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_regional_energy_systems.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_regional_energy_systems.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_regional_energy_systems.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_regional_energy_systems.name_rp IS 'полное наименование в родительном падеже';

COMMENT ON COLUMN gs_sys.gs_sys_regional_energy_systems.ref_uuid IS 'стабильный UUID справочной сущности';

CREATE TABLE gs_sys.gs_sys_station_types (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    ref_uuid character varying(36) NOT NULL,
    display_order integer
);

COMMENT ON TABLE gs_sys.gs_sys_station_types IS 'типы электростанций';

COMMENT ON COLUMN gs_sys.gs_sys_station_types.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_station_types.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_station_types.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_station_types.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_station_types.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_station_types.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_station_types.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_station_types.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_station_types.ref_uuid IS 'стабильный UUID справочной сущности';

COMMENT ON COLUMN gs_sys.gs_sys_station_types.display_order IS 'порядок отображения';

CREATE TABLE gs_sys.gs_sys_synchronous_areas (
    id integer NOT NULL,
    number character varying(256),
    name character varying(256) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    ref_uuid character varying(36) NOT NULL,
    display_order integer,
    name_full character varying(256)
);

COMMENT ON TABLE gs_sys.gs_sys_synchronous_areas IS 'синхронные зоны';

COMMENT ON COLUMN gs_sys.gs_sys_synchronous_areas.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_synchronous_areas.number IS 'номер';

COMMENT ON COLUMN gs_sys.gs_sys_synchronous_areas.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_synchronous_areas.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_synchronous_areas.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_synchronous_areas.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_synchronous_areas.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_synchronous_areas.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_synchronous_areas.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_synchronous_areas.ref_uuid IS 'стабильный UUID справочной сущности';

COMMENT ON COLUMN gs_sys.gs_sys_synchronous_areas.display_order IS 'порядок отображения';

CREATE TABLE gs_sys.gs_sys_technology_availabilities (
    id integer NOT NULL,
    name character varying(80),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    ref_uuid character varying(36) NOT NULL
);

COMMENT ON TABLE gs_sys.gs_sys_technology_availabilities IS 'доступность технологии';

COMMENT ON COLUMN gs_sys.gs_sys_technology_availabilities.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_technology_availabilities.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_technology_availabilities.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_technology_availabilities.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_technology_availabilities.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_technology_availabilities.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_technology_availabilities.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_technology_availabilities.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_technology_availabilities.ref_uuid IS 'стабильный UUID справочной сущности';

CREATE TABLE gs_sys.gs_sys_technology_types (
    id integer NOT NULL,
    name character varying(80),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    ref_uuid character varying(36) NOT NULL,
    display_order integer
);

COMMENT ON TABLE gs_sys.gs_sys_technology_types IS 'типы технологий';

COMMENT ON COLUMN gs_sys.gs_sys_technology_types.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_technology_types.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_technology_types.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_technology_types.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_technology_types.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_technology_types.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_technology_types.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_technology_types.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_technology_types.ref_uuid IS 'стабильный UUID справочной сущности';

COMMENT ON COLUMN gs_sys.gs_sys_technology_types.display_order IS 'порядок отображения';

CREATE TABLE gs_sys.gs_sys_tes_machine_types (
    id integer NOT NULL,
    name character varying(80) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    ref_uuid character varying(36) NOT NULL,
    display_order integer
);

COMMENT ON TABLE gs_sys.gs_sys_tes_machine_types IS 'типы агрегатов ТЭС';

COMMENT ON COLUMN gs_sys.gs_sys_tes_machine_types.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_tes_machine_types.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_tes_machine_types.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_tes_machine_types.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_tes_machine_types.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_tes_machine_types.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_tes_machine_types.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_tes_machine_types.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_tes_machine_types.ref_uuid IS 'стабильный UUID справочной сущности';

COMMENT ON COLUMN gs_sys.gs_sys_tes_machine_types.display_order IS 'порядок отображения';

CREATE TABLE gs_sys.gs_sys_tes_types (
    id integer NOT NULL,
    name character varying(80) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    ref_uuid character varying(36) NOT NULL,
    display_order integer
);

COMMENT ON TABLE gs_sys.gs_sys_tes_types IS 'типы ТЭС';

COMMENT ON COLUMN gs_sys.gs_sys_tes_types.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_tes_types.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_tes_types.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_tes_types.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_tes_types.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_tes_types.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_tes_types.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_tes_types.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_tes_types.ref_uuid IS 'стабильный UUID справочной сущности';

COMMENT ON COLUMN gs_sys.gs_sys_tes_types.display_order IS 'порядок отображения';

CREATE TABLE gs_sys.gs_sys_union_energy_systems (
    id integer NOT NULL,
    name character varying(80) NOT NULL,
    name_full character varying(80) NOT NULL,
    id_energy_system_type integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    display_order integer,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    ref_uuid character varying(36) NOT NULL
);

COMMENT ON TABLE gs_sys.gs_sys_union_energy_systems IS 'объединенные энергосистемы (ОЭС)';

COMMENT ON COLUMN gs_sys.gs_sys_union_energy_systems.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_union_energy_systems.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_union_energy_systems.name_full IS 'полное наименование';

COMMENT ON COLUMN gs_sys.gs_sys_union_energy_systems.id_energy_system_type IS 'идентификатор типа энергосистемы (FK)';

COMMENT ON COLUMN gs_sys.gs_sys_union_energy_systems.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_union_energy_systems.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_union_energy_systems.display_order IS 'порядок отображения';

COMMENT ON COLUMN gs_sys.gs_sys_union_energy_systems.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_union_energy_systems.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_union_energy_systems.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_union_energy_systems.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_union_energy_systems.ref_uuid IS 'стабильный UUID справочной сущности';

CREATE TABLE gs_sys.gs_sys_year_features (
    id integer NOT NULL,
    name character varying(80) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL
);

COMMENT ON TABLE gs_sys.gs_sys_year_features IS 'признаки года';

COMMENT ON COLUMN gs_sys.gs_sys_year_features.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_year_features.name IS 'наименование';

COMMENT ON COLUMN gs_sys.gs_sys_year_features.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_year_features.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_year_features.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_year_features.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_year_features.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_year_features.version IS 'версия записи';

CREATE TABLE gs_sys.gs_sys_year_service (
    id integer NOT NULL,
    year_sipr_start integer,
    year_sipr_end integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL,
    database_version_id integer,
    date_sipr_start date,
    date_sipr_end date
);

COMMENT ON TABLE gs_sys.gs_sys_year_service IS 'сервис управления годами СиПР';

COMMENT ON COLUMN gs_sys.gs_sys_year_service.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_year_service.year_sipr_start IS 'год начала СиПР';

COMMENT ON COLUMN gs_sys.gs_sys_year_service.year_sipr_end IS 'год конца СиПР';

COMMENT ON COLUMN gs_sys.gs_sys_year_service.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_year_service.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_year_service.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_year_service.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_year_service.version IS 'версия записи';

COMMENT ON COLUMN gs_sys.gs_sys_year_service.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_year_service.date_sipr_start IS 'дата начала СиПР';

COMMENT ON COLUMN gs_sys.gs_sys_year_service.date_sipr_end IS 'дата конца СиПР';

CREATE TABLE gs_sys.gs_sys_years (
    id integer NOT NULL,
    number integer NOT NULL,
    id_year_feature integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer,
    created_by character varying(255),
    modified_by character varying(255),
    version integer DEFAULT 1 NOT NULL
);

COMMENT ON TABLE gs_sys.gs_sys_years IS 'годы';

COMMENT ON COLUMN gs_sys.gs_sys_years.id IS 'идентификатор';

COMMENT ON COLUMN gs_sys.gs_sys_years.number IS 'номер';

COMMENT ON COLUMN gs_sys.gs_sys_years.id_year_feature IS 'идентификатор признака года (FK)';

COMMENT ON COLUMN gs_sys.gs_sys_years.created_at IS 'дата и время создания записи';

COMMENT ON COLUMN gs_sys.gs_sys_years.updated_at IS 'дата и время последнего обновления записи';

COMMENT ON COLUMN gs_sys.gs_sys_years.database_version_id IS 'идентификатор версии базы данных';

COMMENT ON COLUMN gs_sys.gs_sys_years.created_by IS 'пользователь, создавший запись';

COMMENT ON COLUMN gs_sys.gs_sys_years.modified_by IS 'пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_sys.gs_sys_years.version IS 'версия записи';

CREATE SEQUENCE gs_sys.gs_year_service_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.gs_year_service_id_seq OWNED BY gs_sys.gs_sys_year_service.id;

CREATE SEQUENCE gs_sys.machine_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.machine_types_id_seq OWNED BY gs_sys.gs_sys_machine_types.id;

CREATE SEQUENCE gs_sys.pgu_tes_machine_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.pgu_tes_machine_types_id_seq OWNED BY gs_sys.gs_sys_pgu_tes_machine_types.id;

CREATE SEQUENCE gs_sys.regional_districts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.regional_districts_id_seq OWNED BY gs_sys.gs_sys_regional_districts.id;

CREATE SEQUENCE gs_sys.regional_energy_systems_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.regional_energy_systems_id_seq OWNED BY gs_sys.gs_sys_regional_energy_systems.id;

CREATE SEQUENCE gs_sys.station_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.station_types_id_seq OWNED BY gs_sys.gs_sys_station_types.id;

CREATE SEQUENCE gs_sys.synchronous_areas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.synchronous_areas_id_seq OWNED BY gs_sys.gs_sys_synchronous_areas.id;

CREATE SEQUENCE gs_sys.technology_availabilities_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.technology_availabilities_id_seq OWNED BY gs_sys.gs_sys_technology_availabilities.id;

CREATE SEQUENCE gs_sys.technology_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.technology_types_id_seq OWNED BY gs_sys.gs_sys_technology_types.id;

CREATE SEQUENCE gs_sys.tes_machine_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.tes_machine_types_id_seq OWNED BY gs_sys.gs_sys_tes_machine_types.id;

CREATE SEQUENCE gs_sys.tes_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.tes_types_id_seq OWNED BY gs_sys.gs_sys_tes_types.id;

CREATE SEQUENCE gs_sys.union_energy_systems_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.union_energy_systems_id_seq OWNED BY gs_sys.gs_sys_union_energy_systems.id;

CREATE SEQUENCE gs_sys.year_features_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.year_features_id_seq OWNED BY gs_sys.gs_sys_year_features.id;

CREATE SEQUENCE gs_sys.years_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_sys.years_id_seq OWNED BY gs_sys.gs_sys_years.id;

CREATE TABLE gs_ter.gs_ter_energy_unit_power_transfer_values (
    id integer NOT NULL,
    id_energy_unit_power_transfer integer NOT NULL,
    year_number integer NOT NULL,
    transfer_mln_kvt_ch numeric(25,16),
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

COMMENT ON TABLE gs_ter.gs_ter_energy_unit_power_transfer_values IS 'Значения перетока электроэнергии по годам (млн кВт·ч)';

COMMENT ON COLUMN gs_ter.gs_ter_energy_unit_power_transfer_values.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ter.gs_ter_energy_unit_power_transfer_values.id_energy_unit_power_transfer IS 'Переток энергоузла (FK -> gs_ter.gs_ter_energy_unit_power_transfers)';

COMMENT ON COLUMN gs_ter.gs_ter_energy_unit_power_transfer_values.year_number IS 'Год';

COMMENT ON COLUMN gs_ter.gs_ter_energy_unit_power_transfer_values.transfer_mln_kvt_ch IS 'Переток электроэнергии, млн кВт·ч';

COMMENT ON COLUMN gs_ter.gs_ter_energy_unit_power_transfer_values.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ter.gs_ter_energy_unit_power_transfer_values.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ter.gs_ter_energy_unit_power_transfer_values.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ter.gs_ter_energy_unit_power_transfer_values.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ter.gs_ter_energy_unit_power_transfer_values.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

CREATE SEQUENCE gs_ter.gs_ter_energy_unit_power_transfer_values_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ter.gs_ter_energy_unit_power_transfer_values_id_seq OWNED BY gs_ter.gs_ter_energy_unit_power_transfer_values.id;

CREATE TABLE gs_ter.gs_ter_energy_unit_power_transfers (
    id integer NOT NULL,
    id_energy_unit integer NOT NULL,
    id_regional_district integer NOT NULL,
    direction text,
    created_by character varying(255),
    modified_by character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    database_version_id integer
);

COMMENT ON TABLE gs_ter.gs_ter_energy_unit_power_transfers IS 'Переток мощности энергоузла (субъект РФ, направление)';

COMMENT ON COLUMN gs_ter.gs_ter_energy_unit_power_transfers.id IS 'Уникальный идентификатор записи';

COMMENT ON COLUMN gs_ter.gs_ter_energy_unit_power_transfers.id_energy_unit IS 'Энергоузел (FK -> gs_sys.gs_sys_energy_units)';

COMMENT ON COLUMN gs_ter.gs_ter_energy_unit_power_transfers.id_regional_district IS 'Субъект РФ (FK -> gs_sys.gs_sys_regional_districts)';

COMMENT ON COLUMN gs_ter.gs_ter_energy_unit_power_transfers.direction IS 'Направление перетока';

COMMENT ON COLUMN gs_ter.gs_ter_energy_unit_power_transfers.created_by IS 'Пользователь, создавший запись';

COMMENT ON COLUMN gs_ter.gs_ter_energy_unit_power_transfers.modified_by IS 'Пользователь, последним изменивший запись';

COMMENT ON COLUMN gs_ter.gs_ter_energy_unit_power_transfers.created_at IS 'Дата и время создания записи';

COMMENT ON COLUMN gs_ter.gs_ter_energy_unit_power_transfers.updated_at IS 'Дата и время последнего изменения записи';

COMMENT ON COLUMN gs_ter.gs_ter_energy_unit_power_transfers.database_version_id IS 'Версия базы данных (FK -> gs_sys.gs_database_versions)';

CREATE SEQUENCE gs_ter.gs_ter_energy_unit_power_transfers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE gs_ter.gs_ter_energy_unit_power_transfers_id_seq OWNED BY gs_ter.gs_ter_energy_unit_power_transfers.id;

ALTER TABLE ONLY gs_auth.roles ALTER COLUMN id SET DEFAULT nextval('gs_auth.roles_id_seq'::regclass);

ALTER TABLE ONLY gs_auth.users ALTER COLUMN id SET DEFAULT nextval('gs_auth.users_id_seq'::regclass);

ALTER TABLE ONLY gs_bem.gs_bem_balance_row_notes ALTER COLUMN id SET DEFAULT nextval('gs_bem.gs_bem_balance_row_notes_id_seq'::regclass);

ALTER TABLE ONLY gs_bem.gs_bem_ee_balance_custom_flow_rows ALTER COLUMN id SET DEFAULT nextval('gs_bem.gs_bem_ee_balance_custom_flow_rows_id_seq'::regclass);

ALTER TABLE ONLY gs_bem.gs_bem_ee_balance_custom_flow_values ALTER COLUMN id SET DEFAULT nextval('gs_bem.gs_bem_ee_balance_custom_flow_values_id_seq'::regclass);

ALTER TABLE ONLY gs_bem.gs_bem_ee_balance_manual_generation_values ALTER COLUMN id SET DEFAULT nextval('gs_bem.gs_bem_ee_balance_manual_generation_values_id_seq'::regclass);

ALTER TABLE ONLY gs_bem.gs_bem_ee_balance_station_group_values ALTER COLUMN id SET DEFAULT nextval('gs_bem.gs_bem_ee_balance_station_group_values_id_seq'::regclass);

ALTER TABLE ONLY gs_bem.gs_bem_ee_balance_station_own_needs_coefficients ALTER COLUMN id SET DEFAULT nextval('gs_bem.gs_bem_ee_balance_station_own_needs_coefficients_id_seq'::regclass);

ALTER TABLE ONLY gs_bem.gs_bem_ee_balance_tes_monthly_values ALTER COLUMN id SET DEFAULT nextval('gs_bem.gs_bem_ee_balance_tes_monthly_values_id_seq'::regclass);

ALTER TABLE ONLY gs_bem.gs_bem_ee_import_export_oes_values ALTER COLUMN id SET DEFAULT nextval('gs_bem.gs_bem_ee_import_export_oes_values_id_seq'::regclass);

ALTER TABLE ONLY gs_bem.gs_bem_ee_receive_transfer_oes_values ALTER COLUMN id SET DEFAULT nextval('gs_bem.gs_bem_ee_receive_transfer_oes_values_id_seq'::regclass);

ALTER TABLE ONLY gs_bem.gs_bem_espp_energy_generations ALTER COLUMN id SET DEFAULT nextval('gs_bem.gs_gen_espp_energy_generations_id_seq'::regclass);

ALTER TABLE ONLY gs_bem.gs_bem_power_balance_custom_flow_rows ALTER COLUMN id SET DEFAULT nextval('gs_bem.gs_bem_power_balance_custom_flow_rows_id_seq'::regclass);

ALTER TABLE ONLY gs_bem.gs_bem_power_balance_custom_flow_values ALTER COLUMN id SET DEFAULT nextval('gs_bem.gs_bem_power_balance_custom_flow_values_id_seq'::regclass);

ALTER TABLE ONLY gs_bem.gs_bem_power_balance_demand_cold_values ALTER COLUMN id SET DEFAULT nextval('gs_bem.gs_bem_power_balance_demand_cold_values_id_seq'::regclass);

ALTER TABLE ONLY gs_bem.gs_bem_power_balance_export_values ALTER COLUMN id SET DEFAULT nextval('gs_bem.gs_bem_power_balance_export_values_id_seq'::regclass);

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_ee_exports ALTER COLUMN id SET DEFAULT nextval('gs_bem.gs_bem_regional_energy_system_ee_exports_id_seq'::regclass);

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_em_exports ALTER COLUMN id SET DEFAULT nextval('gs_bem.gs_bem_regional_energy_system_em_exports_id_seq'::regclass);

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_energy_generations ALTER COLUMN id SET DEFAULT nextval('gs_bem.gs_gen_regional_energy_system_energy_generations_id_seq'::regclass);

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_transfers ALTER COLUMN id SET DEFAULT nextval('gs_bem.gs_bem_regional_energy_system_transfers_id_seq'::regclass);

ALTER TABLE ONLY gs_bem.gs_bem_station_energy_generations ALTER COLUMN id SET DEFAULT nextval('gs_bem.gs_gen_station_energy_generations_id_seq'::regclass);

ALTER TABLE ONLY gs_ec.gs_ec_centralized_zone_consumption_params ALTER COLUMN id SET DEFAULT nextval('gs_ec.gs_ec_centralized_zone_consumption_params_id_seq'::regclass);

ALTER TABLE ONLY gs_ec.gs_ec_ees_consumption_params ALTER COLUMN id SET DEFAULT nextval('gs_ec.gs_ec_ees_consumption_params_id_seq'::regclass);

ALTER TABLE ONLY gs_ec.gs_ec_ees_russia_consumption_params ALTER COLUMN id SET DEFAULT nextval('gs_ec.gs_ec_ees_russia_consumption_params_id_seq'::regclass);

ALTER TABLE ONLY gs_ec.gs_ec_energy_area_consumption_params ALTER COLUMN id SET DEFAULT nextval('gs_ec.gs_ec_energy_area_consumption_params_id_seq'::regclass);

ALTER TABLE ONLY gs_ec.gs_ec_energy_system_type_consumption_params ALTER COLUMN id SET DEFAULT nextval('gs_ec.gs_ec_energy_system_type_consumption_params_id_seq'::regclass);

ALTER TABLE ONLY gs_ec.gs_ec_energy_unit_consumption_params ALTER COLUMN id SET DEFAULT nextval('gs_ec.gs_ec_energy_unit_consumption_params_id_seq'::regclass);

ALTER TABLE ONLY gs_ec.gs_ec_energy_zone_consumption_params ALTER COLUMN id SET DEFAULT nextval('gs_ec.gs_ec_energy_zone_consumption_params_id_seq'::regclass);

ALTER TABLE ONLY gs_ec.gs_ec_federal_district_consumption_params ALTER COLUMN id SET DEFAULT nextval('gs_ec.gs_ec_federal_district_consumption_params_id_seq'::regclass);

ALTER TABLE ONLY gs_ec.gs_ec_regional_district_consumption_params ALTER COLUMN id SET DEFAULT nextval('gs_ec.gs_ec_regional_district_consumption_params_id_seq'::regclass);

ALTER TABLE ONLY gs_ec.gs_ec_regional_energy_system_consumption_params ALTER COLUMN id SET DEFAULT nextval('gs_ec.gs_ec_regional_energy_system_consumption_params_id_seq'::regclass);

ALTER TABLE ONLY gs_ec.gs_ec_russia_federation_consumption_params ALTER COLUMN id SET DEFAULT nextval('gs_ec.gs_ec_russia_federation_consumption_params_id_seq'::regclass);

ALTER TABLE ONLY gs_ec.gs_ec_summary_formula_texts ALTER COLUMN id SET DEFAULT nextval('gs_ec.gs_ec_summary_formula_texts_id_seq'::regclass);

ALTER TABLE ONLY gs_ec.gs_ec_synchronous_area_consumption_params ALTER COLUMN id SET DEFAULT nextval('gs_ec.gs_ec_synchronous_area_consumption_params_id_seq'::regclass);

ALTER TABLE ONLY gs_ec.gs_ec_union_energy_system_consumption_params ALTER COLUMN id SET DEFAULT nextval('gs_ec.gs_ec_union_energy_system_consumption_params_id_seq'::regclass);

ALTER TABLE ONLY gs_eco.gs_eco_analysis_pg_params ALTER COLUMN id SET DEFAULT nextval('gs_eco.gs_eco_analysis_pg_params_id_seq'::regclass);

ALTER TABLE ONLY gs_eco.gs_eco_analysis_zv_params ALTER COLUMN id SET DEFAULT nextval('gs_eco.gs_eco_analysis_zv_params_id_seq'::regclass);

ALTER TABLE ONLY gs_eco.gs_eco_fuel_snapshots ALTER COLUMN id SET DEFAULT nextval('gs_eco.gs_eco_fuel_snapshots_id_seq'::regclass);

ALTER TABLE ONLY gs_eco.gs_eco_fuel_submissions ALTER COLUMN id SET DEFAULT nextval('gs_eco.gs_eco_fuel_submissions_id_seq'::regclass);

ALTER TABLE ONLY gs_eco.gs_eco_gis_tek_greenhouse_gas_params ALTER COLUMN id SET DEFAULT nextval('gs_eco.gs_eco_gis_tek_greenhouse_gas_params_id_seq'::regclass);

ALTER TABLE ONLY gs_eco.gs_eco_gis_tek_pollutant_params ALTER COLUMN id SET DEFAULT nextval('gs_eco.gs_eco_gis_tek_pollutant_params_id_seq'::regclass);

ALTER TABLE ONLY gs_eco.gs_eco_new_tes_norms ALTER COLUMN id SET DEFAULT nextval('gs_eco.gs_eco_new_tes_norms_id_seq'::regclass);

ALTER TABLE ONLY gs_eco.gs_eco_operating_tes_coefficients ALTER COLUMN id SET DEFAULT nextval('gs_eco.gs_eco_operating_tes_coefficients_id_seq'::regclass);

ALTER TABLE ONLY gs_eco.gs_eco_operating_tes_formula_texts ALTER COLUMN id SET DEFAULT nextval('gs_eco.gs_eco_operating_tes_formula_texts_id_seq'::regclass);

ALTER TABLE ONLY gs_eco.gs_eco_operating_tes_fuel_chars ALTER COLUMN id SET DEFAULT nextval('gs_eco.gs_eco_operating_tes_fuel_chars_id_seq'::regclass);

ALTER TABLE ONLY gs_eco.gs_eco_operating_tes_inputs ALTER COLUMN id SET DEFAULT nextval('gs_eco.gs_eco_operating_tes_inputs_id_seq'::regclass);

ALTER TABLE ONLY gs_ei.gs_ei_electrical_intensity_formula_texts ALTER COLUMN id SET DEFAULT nextval('gs_ei.gs_ec_long_term_electrical_intensity_formula_texts_id_seq'::regclass);

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_electrical_intensity_coefficients ALTER COLUMN id SET DEFAULT nextval('gs_ei.gs_ei_federal_district_electrical_intensity_coefficients_id_seq'::regclass);

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_electrical_intensity_year_params ALTER COLUMN id SET DEFAULT nextval('gs_ei.gs_ei_federal_district_electrical_intensity_year_params_id_seq'::regclass);

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_fd_total_consumption_coefficients ALTER COLUMN id SET DEFAULT nextval('gs_ei.gs_ei_federal_district_fd_total_consumption_coefficients_id_seq'::regclass);

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_population_consumption_coefficients ALTER COLUMN id SET DEFAULT nextval('gs_ei.gs_ec_federal_district_population_consumption_coefficien_id_seq'::regclass);

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_population_consumption_year_params ALTER COLUMN id SET DEFAULT nextval('gs_ei.gs_ec_federal_district_population_consumption_year_param_id_seq'::regclass);

ALTER TABLE ONLY gs_ei.gs_ei_russia_federation_electrical_intensity_coefficients ALTER COLUMN id SET DEFAULT nextval('gs_ei.gs_ec_russia_federation_electrical_intensity_coefficient_id_seq'::regclass);

ALTER TABLE ONLY gs_ei.gs_ei_russia_federation_electrical_intensity_year_params ALTER COLUMN id SET DEFAULT nextval('gs_ei.gs_ei_russia_federation_electrical_intensity_year_params_id_seq'::regclass);

ALTER TABLE ONLY gs_ekp.gs_ekp_accum_fixed_capital_formula_texts ALTER COLUMN id SET DEFAULT nextval('gs_ekp.gs_ekp_accum_fixed_capital_formula_texts_id_seq'::regclass);

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params ALTER COLUMN id SET DEFAULT nextval('gs_ekp.gs_ec_federal_district_economic_activity_accum_fixed_cap_id_seq'::regclass);

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_accum_monetary_income_params ALTER COLUMN id SET DEFAULT nextval('gs_ekp.gs_ekp_federal_district_accum_monetary_income_params_id_seq'::regclass);

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_eat_consumption_params ALTER COLUMN id SET DEFAULT nextval('gs_ekp.gs_ec_federal_district_economic_activity_consumption_par_id_seq'::regclass);

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_population_params ALTER COLUMN id SET DEFAULT nextval('gs_ekp.gs_ekp_federal_district_population_params_id_seq'::regclass);

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_product_output_params ALTER COLUMN id SET DEFAULT nextval('gs_ekp.gs_ec_federal_district_economic_activity_product_output__id_seq'::regclass);

ALTER TABLE ONLY gs_ekp.gs_ekp_product_output_formula_texts ALTER COLUMN id SET DEFAULT nextval('gs_ekp.gs_ekp_product_output_formula_texts_id_seq'::regclass);

ALTER TABLE ONLY gs_ekp.gs_ekp_russia_federation_accum_fixed_capital_params ALTER COLUMN id SET DEFAULT nextval('gs_ekp.gs_ec_russia_federation_economic_activity_accum_fixed_ca_id_seq'::regclass);

ALTER TABLE ONLY gs_ekp.gs_ekp_russia_federation_consumption_params ALTER COLUMN id SET DEFAULT nextval('gs_ekp.gs_ec_russia_federation_economic_activity_consumption_pa_id_seq'::regclass);

ALTER TABLE ONLY gs_ekp.gs_ekp_russia_federation_product_output_params ALTER COLUMN id SET DEFAULT nextval('gs_ekp.gs_ec_russia_federation_economic_activity_product_output_id_seq'::regclass);

ALTER TABLE ONLY gs_ekp.gs_ekp_ved_consumption_formula_texts ALTER COLUMN id SET DEFAULT nextval('gs_ekp.gs_ekp_ved_consumption_formula_texts_id_seq'::regclass);

ALTER TABLE ONLY gs_fue.gs_fue_allocatable_heat ALTER COLUMN id SET DEFAULT nextval('gs_fue.gs_fue_allocatable_heat_id_seq'::regclass);

ALTER TABLE ONLY gs_fue.gs_fue_distribution_coefficient_summaries ALTER COLUMN id SET DEFAULT nextval('gs_fue.gs_fue_distribution_coefficient_summaries_id_seq'::regclass);

ALTER TABLE ONLY gs_fue.gs_fue_distribution_parameters ALTER COLUMN id SET DEFAULT nextval('gs_fue.gs_fue_distribution_parameters_id_seq'::regclass);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_coefficient_results ALTER COLUMN id SET DEFAULT nextval('gs_fue.gs_fue_equipment_group_coefficient_results_id_seq'::regclass);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_electricity_production_cost ALTER COLUMN id SET DEFAULT nextval('gs_fue.gs_fue_equipment_group_electricity_production_cost_id_seq'::regclass);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_extra_fuel_param ALTER COLUMN id SET DEFAULT nextval('gs_fue.gs_fue_equipment_group_extra_fuel_param_id_seq'::regclass);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_fuel_formula ALTER COLUMN id SET DEFAULT nextval('gs_fue.gs_fue_equipment_group_fuel_formula_id_seq'::regclass);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_fuel_param ALTER COLUMN id SET DEFAULT nextval('gs_fue.gs_fue_equipment_group_fuel_param_id_seq'::regclass);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_heat_and_tariffs ALTER COLUMN id SET DEFAULT nextval('gs_fue.gs_fue_equipment_group_heat_and_tariffs_id_seq'::regclass);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_natural_fuel ALTER COLUMN id SET DEFAULT nextval('gs_fue.gs_fue_equipment_group_natural_fuel_id_seq'::regclass);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_specific_fuel_consumption ALTER COLUMN id SET DEFAULT nextval('gs_fue.gs_fue_equipment_group_specific_fuel_consumption_id_seq'::regclass);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_specific_fuel_cost ALTER COLUMN id SET DEFAULT nextval('gs_fue.gs_fue_equipment_group_specific_fuel_cost_id_seq'::regclass);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_specific_fuel_price ALTER COLUMN id SET DEFAULT nextval('gs_fue.gs_fue_equipment_group_specific_fuel_price_id_seq'::regclass);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_type_stations ALTER COLUMN id SET DEFAULT nextval('gs_fue.gs_fue_equipment_group_type_stations_id_seq'::regclass);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_groups ALTER COLUMN id SET DEFAULT nextval('gs_fue.gs_fue_equipment_groups_id_seq'::regclass);

ALTER TABLE ONLY gs_fue.gs_fue_fixed_heat ALTER COLUMN id SET DEFAULT nextval('gs_fue.gs_fue_fixed_heat_id_seq'::regclass);

ALTER TABLE ONLY gs_fue.gs_fue_formula_texts ALTER COLUMN id SET DEFAULT nextval('gs_fue.gs_fue_formula_texts_id_seq'::regclass);

ALTER TABLE ONLY gs_fue.gs_fue_machine_fuel_param ALTER COLUMN id SET DEFAULT nextval('gs_fue.gs_fue_machine_topl_agr_id_seq'::regclass);

ALTER TABLE ONLY gs_fue.gs_fue_restrictions ALTER COLUMN id SET DEFAULT nextval('gs_fue.gs_fue_restrictions_id_seq'::regclass);

ALTER TABLE ONLY gs_fue_em.gs_fue_em_business_unit ALTER COLUMN id SET DEFAULT nextval('gs_fue_em.gs_fue_em_business_unit_id_seq'::regclass);

ALTER TABLE ONLY gs_fue_em.gs_fue_em_cities ALTER COLUMN id SET DEFAULT nextval('gs_fue_em.gs_fue_em_cities_id_seq'::regclass);

ALTER TABLE ONLY gs_fue_em.gs_fue_em_economic_region ALTER COLUMN id SET DEFAULT nextval('gs_fue_em.gs_fue_em_economic_region_id_seq'::regclass);

ALTER TABLE ONLY gs_fue_em.gs_fue_em_equipment_group ALTER COLUMN id SET DEFAULT nextval('gs_fue_em.gs_fue_em_equipment_group_id_seq'::regclass);

ALTER TABLE ONLY gs_fue_em.gs_fue_em_federal_district ALTER COLUMN id SET DEFAULT nextval('gs_fue_em.gs_fue_em_federal_district_id_seq'::regclass);

ALTER TABLE ONLY gs_fue_em.gs_fue_em_gen_company ALTER COLUMN id SET DEFAULT nextval('gs_fue_em.gs_fue_em_gen_company_id_seq'::regclass);

ALTER TABLE ONLY gs_fue_em.gs_fue_em_gen_company_branch ALTER COLUMN id SET DEFAULT nextval('gs_fue_em.gs_fue_em_gen_company_branch_id_seq'::regclass);

ALTER TABLE ONLY gs_fue_em.gs_fue_em_territories_energy ALTER COLUMN id SET DEFAULT nextval('gs_fue_em.gs_fue_em_territories_energy_id_seq'::regclass);

ALTER TABLE ONLY gs_fue_em.gs_fue_em_union_energy_system ALTER COLUMN id SET DEFAULT nextval('gs_fue_em.gs_fue_em_union_energy_system_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_boilers ALTER COLUMN id SET DEFAULT nextval('gs_gen.boilers_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_documents_kommod ALTER COLUMN id SET DEFAULT nextval('gs_gen.documents_kommod_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_gaes_tep_source_project_indicators ALTER COLUMN id SET DEFAULT nextval('gs_gen.gaes_tep_source_project_indicators_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_ges_tep_source_project_indicators ALTER COLUMN id SET DEFAULT nextval('gs_gen.ges_tep_source_project_indicators_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_machine_fuels ALTER COLUMN id SET DEFAULT nextval('gs_gen.machine_fuels_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_machine_names ALTER COLUMN id SET DEFAULT nextval('gs_gen.machine_names_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_machine_powers ALTER COLUMN id SET DEFAULT nextval('gs_gen.machine_powers_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_machine_prospective_place_aes ALTER COLUMN id SET DEFAULT nextval('gs_gen.machine_prospective_place_aes_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_machine_tes_types ALTER COLUMN id SET DEFAULT nextval('gs_gen.machine_tes_types_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_machines ALTER COLUMN id SET DEFAULT nextval('gs_gen.machines_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_pgu_machine_names ALTER COLUMN id SET DEFAULT nextval('gs_gen.pgu_machine_names_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_pgu_machine_powers ALTER COLUMN id SET DEFAULT nextval('gs_gen.pgu_machine_powers_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_pgu_machines ALTER COLUMN id SET DEFAULT nextval('gs_gen.pgu_machines_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_prospective_place_hydro_energy_forecasts ALTER COLUMN id SET DEFAULT nextval('gs_gen.gs_gen_prospective_place_hydro_energy_forecasts_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_prospective_place_types ALTER COLUMN id SET DEFAULT nextval('gs_gen.gs_prospective_place_types_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_prospective_place_types_gaes ALTER COLUMN id SET DEFAULT nextval('gs_gen.gs_prospective_place_types_gaes_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_prospective_place_types_ges ALTER COLUMN id SET DEFAULT nextval('gs_gen.gs_prospective_place_types_ges_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_station_gaes_charge_consumptions ALTER COLUMN id SET DEFAULT nextval('gs_gen.gs_gen_station_gaes_charge_consumptions_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_station_groups ALTER COLUMN id SET DEFAULT nextval('gs_gen.station_groups_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_station_owner_energy_generations ALTER COLUMN id SET DEFAULT nextval('gs_gen.gs_gen_station_owner_energy_generations_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_station_prospective_place_aes ALTER COLUMN id SET DEFAULT nextval('gs_gen.station_prospective_place_aes_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_station_prospective_place_gaes ALTER COLUMN id SET DEFAULT nextval('gs_gen.station_prospective_place_gaes_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_station_prospective_place_ges ALTER COLUMN id SET DEFAULT nextval('gs_gen.station_prospective_place_ges_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_station_snee_efficiencies ALTER COLUMN id SET DEFAULT nextval('gs_gen.gs_gen_station_snee_efficiencies_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_station_snee_energy_consumptions ALTER COLUMN id SET DEFAULT nextval('gs_gen.gs_gen_station_snee_energy_consumptions_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_stations ALTER COLUMN id SET DEFAULT nextval('gs_gen.stations_id_seq'::regclass);

ALTER TABLE ONLY gs_gen.gs_gen_tep_price_conversion_coefficients ALTER COLUMN id SET DEFAULT nextval('gs_gen.ges_tep_price_conversion_coefficients_id_seq'::regclass);

ALTER TABLE ONLY gs_logs.logs ALTER COLUMN id SET DEFAULT nextval('gs_logs.logs_id_seq'::regclass);

ALTER TABLE ONLY gs_pd.gs_pd_centralized_zone_demand_params ALTER COLUMN id SET DEFAULT nextval('gs_pd.gs_centralized_zone_demand_params_id_seq'::regclass);

ALTER TABLE ONLY gs_pd.gs_pd_ees_demand_params ALTER COLUMN id SET DEFAULT nextval('gs_pd.gs_ees_demand_params_id_seq'::regclass);

ALTER TABLE ONLY gs_pd.gs_pd_ees_russia_demand_params ALTER COLUMN id SET DEFAULT nextval('gs_pd.gs_ees_russia_demand_params_id_seq'::regclass);

ALTER TABLE ONLY gs_pd.gs_pd_energy_area_demand_params ALTER COLUMN id SET DEFAULT nextval('gs_pd.gs_energy_area_demand_params_id_seq'::regclass);

ALTER TABLE ONLY gs_pd.gs_pd_energy_system_type_demand_params ALTER COLUMN id SET DEFAULT nextval('gs_pd.gs_energy_system_type_demand_params_id_seq'::regclass);

ALTER TABLE ONLY gs_pd.gs_pd_energy_unit_demand_params ALTER COLUMN id SET DEFAULT nextval('gs_pd.gs_energy_unit_demand_params_id_seq'::regclass);

ALTER TABLE ONLY gs_pd.gs_pd_energy_zone_demand_params ALTER COLUMN id SET DEFAULT nextval('gs_pd.gs_energy_zone_demand_params_id_seq'::regclass);

ALTER TABLE ONLY gs_pd.gs_pd_federal_district_demand_params ALTER COLUMN id SET DEFAULT nextval('gs_pd.gs_federal_district_demand_params_id_seq'::regclass);

ALTER TABLE ONLY gs_pd.gs_pd_ozp_max_power_params ALTER COLUMN id SET DEFAULT nextval('gs_pd.gs_pd_ozp_max_power_params_id_seq'::regclass);

ALTER TABLE ONLY gs_pd.gs_pd_regional_district_demand_params ALTER COLUMN id SET DEFAULT nextval('gs_pd.gs_regional_district_demand_params_id_seq'::regclass);

ALTER TABLE ONLY gs_pd.gs_pd_regional_energy_system_demand_params ALTER COLUMN id SET DEFAULT nextval('gs_pd.gs_regional_energy_system_demand_params_id_seq'::regclass);

ALTER TABLE ONLY gs_pd.gs_pd_russia_federation_demand_params ALTER COLUMN id SET DEFAULT nextval('gs_pd.gs_russia_federation_demand_params_id_seq'::regclass);

ALTER TABLE ONLY gs_pd.gs_pd_summary_formula_texts ALTER COLUMN id SET DEFAULT nextval('gs_pd.gs_pd_summary_formula_texts_id_seq'::regclass);

ALTER TABLE ONLY gs_pd.gs_pd_synchronous_area_demand_params ALTER COLUMN id SET DEFAULT nextval('gs_pd.gs_synchronous_area_demand_params_id_seq'::regclass);

ALTER TABLE ONLY gs_pd.gs_pd_union_energy_system_demand_params ALTER COLUMN id SET DEFAULT nextval('gs_pd.gs_union_energy_system_demand_params_id_seq'::regclass);

ALTER TABLE ONLY gs_rs.gs_rs_calculation_workbooks ALTER COLUMN id SET DEFAULT nextval('gs_rs.gs_rs_calculation_workbooks_id_seq'::regclass);

ALTER TABLE ONLY gs_rs.gs_rs_equipment_technical_characteristics ALTER COLUMN id SET DEFAULT nextval('gs_rs.gs_rs_turbine_technical_characteristics_id_seq'::regclass);

ALTER TABLE ONLY gs_rs.gs_rs_technical_inspection_codes ALTER COLUMN id SET DEFAULT nextval('gs_rs.gs_rs_technical_inspection_codes_id_seq'::regclass);

ALTER TABLE ONLY gs_rs.gs_rs_territory_inputs ALTER COLUMN id SET DEFAULT nextval('gs_rs.gs_rs_territory_inputs_id_seq'::regclass);

ALTER TABLE ONLY gs_rs.gs_rs_territory_technologies ALTER COLUMN id SET DEFAULT nextval('gs_rs.gs_rs_territory_technologies_id_seq'::regclass);

ALTER TABLE ONLY gs_rs.gs_rs_territory_transfer_sections ALTER COLUMN id SET DEFAULT nextval('gs_rs.gs_rs_territory_transfer_sections_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_business_units ALTER COLUMN id SET DEFAULT nextval('gs_sys.gs_business_units_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_companies ALTER COLUMN id SET DEFAULT nextval('gs_sys.gen_companies_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_condition_types ALTER COLUMN id SET DEFAULT nextval('gs_sys.condition_types_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_database_versions ALTER COLUMN id SET DEFAULT nextval('gs_sys.database_versions_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_departments ALTER COLUMN id SET DEFAULT nextval('gs_sys.gs_departments_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_economic_activity_types ALTER COLUMN id SET DEFAULT nextval('gs_sys.gs_sys_economic_activity_types_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_electricity_production_cost_types ALTER COLUMN id SET DEFAULT nextval('gs_sys.gs_sys_electricity_production_cost_types_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_energy_areas ALTER COLUMN id SET DEFAULT nextval('gs_sys.energy_areas_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_energy_system_types ALTER COLUMN id SET DEFAULT nextval('gs_sys.energy_system_types_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_energy_units ALTER COLUMN id SET DEFAULT nextval('gs_sys.energy_units_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_energy_zones ALTER COLUMN id SET DEFAULT nextval('gs_sys.energy_zones_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_entity_perimeter_bindings ALTER COLUMN id SET DEFAULT nextval('gs_sys.gs_sys_entity_perimeter_bindings_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_equipment_groups ALTER COLUMN id SET DEFAULT nextval('gs_sys.equipment_groups_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_federal_districts ALTER COLUMN id SET DEFAULT nextval('gs_sys.federal_districts_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_foreign_border_countries ALTER COLUMN id SET DEFAULT nextval('gs_sys.gs_sys_foreign_border_countries_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_fuel_types ALTER COLUMN id SET DEFAULT nextval('gs_sys.fuel_types_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_fuels ALTER COLUMN id SET DEFAULT nextval('gs_sys.fuels_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_machine_types ALTER COLUMN id SET DEFAULT nextval('gs_sys.machine_types_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_perimeter_variants ALTER COLUMN id SET DEFAULT nextval('gs_sys.gs_sys_perimeter_variants_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_pgu_tes_machine_types ALTER COLUMN id SET DEFAULT nextval('gs_sys.pgu_tes_machine_types_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_refdata_entities ALTER COLUMN id SET DEFAULT nextval('gs_sys.gs_refdata_entities_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_refdata_entity_years ALTER COLUMN id SET DEFAULT nextval('gs_sys.gs_refdata_entity_years_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_regional_districts ALTER COLUMN id SET DEFAULT nextval('gs_sys.regional_districts_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_regional_energy_systems ALTER COLUMN id SET DEFAULT nextval('gs_sys.regional_energy_systems_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_station_types ALTER COLUMN id SET DEFAULT nextval('gs_sys.station_types_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_synchronous_areas ALTER COLUMN id SET DEFAULT nextval('gs_sys.synchronous_areas_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_technology_availabilities ALTER COLUMN id SET DEFAULT nextval('gs_sys.technology_availabilities_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_technology_types ALTER COLUMN id SET DEFAULT nextval('gs_sys.technology_types_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_tep_price_conversion_coefficients ALTER COLUMN id SET DEFAULT nextval('gs_sys.ges_tep_price_conversion_coefficients_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_tes_machine_types ALTER COLUMN id SET DEFAULT nextval('gs_sys.tes_machine_types_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_tes_types ALTER COLUMN id SET DEFAULT nextval('gs_sys.tes_types_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_union_energy_systems ALTER COLUMN id SET DEFAULT nextval('gs_sys.union_energy_systems_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_year_features ALTER COLUMN id SET DEFAULT nextval('gs_sys.year_features_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_year_service ALTER COLUMN id SET DEFAULT nextval('gs_sys.gs_year_service_id_seq'::regclass);

ALTER TABLE ONLY gs_sys.gs_sys_years ALTER COLUMN id SET DEFAULT nextval('gs_sys.years_id_seq'::regclass);

ALTER TABLE ONLY gs_ter.gs_ter_energy_unit_power_transfer_values ALTER COLUMN id SET DEFAULT nextval('gs_ter.gs_ter_energy_unit_power_transfer_values_id_seq'::regclass);

ALTER TABLE ONLY gs_ter.gs_ter_energy_unit_power_transfers ALTER COLUMN id SET DEFAULT nextval('gs_ter.gs_ter_energy_unit_power_transfers_id_seq'::regclass);

ALTER TABLE ONLY gs_auth.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_auth.user_roles
    ADD CONSTRAINT user_roles_pkey PRIMARY KEY (user_id, role_id);

ALTER TABLE ONLY gs_auth.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_bem.gs_bem_balance_row_notes
    ADD CONSTRAINT gs_bem_balance_row_notes_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_bem.gs_bem_ee_balance_custom_flow_rows
    ADD CONSTRAINT gs_bem_ee_balance_custom_flow_rows_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_bem.gs_bem_ee_balance_custom_flow_values
    ADD CONSTRAINT gs_bem_ee_balance_custom_flow_values_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_bem.gs_bem_ee_balance_manual_generation_values
    ADD CONSTRAINT gs_bem_ee_balance_manual_generation_values_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_bem.gs_bem_ee_balance_station_group_values
    ADD CONSTRAINT gs_bem_ee_balance_station_group_values_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_bem.gs_bem_ee_balance_station_own_needs_coefficients
    ADD CONSTRAINT gs_bem_ee_balance_station_own_needs_coefficients_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_bem.gs_bem_ee_balance_tes_monthly_values
    ADD CONSTRAINT gs_bem_ee_balance_tes_monthly_values_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_bem.gs_bem_ee_import_export_oes_values
    ADD CONSTRAINT gs_bem_ee_import_export_oes_values_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_bem.gs_bem_ee_receive_transfer_oes_values
    ADD CONSTRAINT gs_bem_ee_receive_transfer_oes_values_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_bem.gs_bem_power_balance_custom_flow_rows
    ADD CONSTRAINT gs_bem_power_balance_custom_flow_rows_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_bem.gs_bem_power_balance_custom_flow_values
    ADD CONSTRAINT gs_bem_power_balance_custom_flow_values_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_bem.gs_bem_power_balance_demand_cold_values
    ADD CONSTRAINT gs_bem_power_balance_demand_cold_values_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_bem.gs_bem_power_balance_export_values
    ADD CONSTRAINT gs_bem_power_balance_export_values_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_ee_exports
    ADD CONSTRAINT gs_bem_regional_energy_system_ee_exports_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_em_exports
    ADD CONSTRAINT gs_bem_regional_energy_system_em_exports_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_transfers
    ADD CONSTRAINT gs_bem_regional_energy_system_transfers_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_bem.gs_bem_espp_energy_generations
    ADD CONSTRAINT gs_gen_espp_energy_generations_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_energy_generations
    ADD CONSTRAINT gs_gen_regional_energy_system_energy_generations_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_bem.gs_bem_station_energy_generations
    ADD CONSTRAINT gs_gen_station_energy_generations_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ec.gs_ec_centralized_zone_consumption_params
    ADD CONSTRAINT gs_ec_centralized_zone_consumption_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ec.gs_ec_ees_consumption_params
    ADD CONSTRAINT gs_ec_ees_consumption_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ec.gs_ec_ees_russia_consumption_params
    ADD CONSTRAINT gs_ec_ees_russia_consumption_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ec.gs_ec_energy_area_consumption_params
    ADD CONSTRAINT gs_ec_energy_area_consumption_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ec.gs_ec_energy_system_type_consumption_params
    ADD CONSTRAINT gs_ec_energy_system_type_consumption_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ec.gs_ec_energy_unit_consumption_params
    ADD CONSTRAINT gs_ec_energy_unit_consumption_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ec.gs_ec_energy_zone_consumption_params
    ADD CONSTRAINT gs_ec_energy_zone_consumption_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ec.gs_ec_federal_district_consumption_params
    ADD CONSTRAINT gs_ec_federal_district_consumption_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ec.gs_ec_regional_district_consumption_params
    ADD CONSTRAINT gs_ec_regional_district_consumption_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ec.gs_ec_regional_energy_system_consumption_params
    ADD CONSTRAINT gs_ec_regional_energy_system_consumption_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ec.gs_ec_russia_federation_consumption_params
    ADD CONSTRAINT gs_ec_russia_federation_consumption_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ec.gs_ec_summary_formula_texts
    ADD CONSTRAINT gs_ec_summary_formula_texts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ec.gs_ec_synchronous_area_consumption_params
    ADD CONSTRAINT gs_ec_synchronous_area_consumption_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ec.gs_ec_union_energy_system_consumption_params
    ADD CONSTRAINT gs_ec_union_energy_system_consumption_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ec.gs_ec_summary_formula_texts
    ADD CONSTRAINT uq_gs_ec_summary_formula_texts_key UNIQUE (formula_key);

ALTER TABLE ONLY gs_eco.gs_eco_analysis_pg_params
    ADD CONSTRAINT gs_eco_analysis_pg_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_eco.gs_eco_analysis_zv_params
    ADD CONSTRAINT gs_eco_analysis_zv_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_eco.gs_eco_fuel_snapshots
    ADD CONSTRAINT gs_eco_fuel_snapshots_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_eco.gs_eco_fuel_submissions
    ADD CONSTRAINT gs_eco_fuel_submissions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_eco.gs_eco_gis_tek_greenhouse_gas_params
    ADD CONSTRAINT gs_eco_gis_tek_greenhouse_gas_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_eco.gs_eco_gis_tek_pollutant_params
    ADD CONSTRAINT gs_eco_gis_tek_pollutant_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_eco.gs_eco_new_tes_norms
    ADD CONSTRAINT gs_eco_new_tes_norms_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_eco.gs_eco_operating_tes_coefficients
    ADD CONSTRAINT gs_eco_operating_tes_coefficients_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_eco.gs_eco_operating_tes_formula_texts
    ADD CONSTRAINT gs_eco_operating_tes_formula_texts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_eco.gs_eco_operating_tes_fuel_chars
    ADD CONSTRAINT gs_eco_operating_tes_fuel_chars_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_eco.gs_eco_operating_tes_inputs
    ADD CONSTRAINT gs_eco_operating_tes_inputs_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_eco.gs_eco_analysis_pg_params
    ADD CONSTRAINT uq_eco_analysis_pg_sheet_numb_year_ver UNIQUE (sheet_slug, station_numb, year_number, database_version_id);

ALTER TABLE ONLY gs_eco.gs_eco_analysis_zv_params
    ADD CONSTRAINT uq_eco_analysis_zv_sheet_numb_year_ver UNIQUE (sheet_slug, station_numb, year_number, database_version_id);

ALTER TABLE ONLY gs_eco.gs_eco_fuel_snapshots
    ADD CONSTRAINT uq_eco_fuel_snapshot_version_year_scope UNIQUE (database_version_id, year_number, scope);

ALTER TABLE ONLY gs_eco.gs_eco_gis_tek_greenhouse_gas_params
    ADD CONSTRAINT uq_eco_gis_tek_pg_numb_year_ver UNIQUE (station_numb, year_number, database_version_id);

ALTER TABLE ONLY gs_eco.gs_eco_gis_tek_pollutant_params
    ADD CONSTRAINT uq_eco_gis_tek_zv_numb_year_ver UNIQUE (station_numb, year_number, database_version_id);

ALTER TABLE ONLY gs_eco.gs_eco_new_tes_norms
    ADD CONSTRAINT uq_eco_nt_norm_fuel_class_year_ver UNIQUE (fuel_key, capacity_class, year_number, database_version_id);

ALTER TABLE ONLY gs_eco.gs_eco_operating_tes_coefficients
    ADD CONSTRAINT uq_eco_ot_coeff_slice_year_kind_ver UNIQUE (territory_slug, affiliation, year_number, kind, database_version_id);

ALTER TABLE ONLY gs_eco.gs_eco_operating_tes_fuel_chars
    ADD CONSTRAINT uq_eco_ot_fuel_char_slice_key_year_ver UNIQUE (territory_slug, fuel_key, year_number, database_version_id);

ALTER TABLE ONLY gs_eco.gs_eco_operating_tes_inputs
    ADD CONSTRAINT uq_eco_ot_input_terr_year_key_ver UNIQUE (territory_slug, year_number, row_key, database_version_id);

ALTER TABLE ONLY gs_eco.gs_eco_operating_tes_formula_texts
    ADD CONSTRAINT uq_gs_eco_operating_tes_formula_texts_key UNIQUE (formula_key);

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_electrical_intensity_coefficients
    ADD CONSTRAINT gs_ei_federal_district_electrical_intensity_coefficients_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_electrical_intensity_year_params
    ADD CONSTRAINT gs_ei_federal_district_electrical_intensity_year_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_fd_total_consumption_coefficients
    ADD CONSTRAINT gs_ei_federal_district_fd_total_consumption_coefficients_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_population_consumption_coefficients
    ADD CONSTRAINT gs_ei_federal_district_population_consumption_coefficients_pke PRIMARY KEY (id);

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_population_consumption_year_params
    ADD CONSTRAINT gs_ei_federal_district_population_consumption_year_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ei.gs_ei_electrical_intensity_formula_texts
    ADD CONSTRAINT gs_ei_long_term_electrical_intensity_formula_texts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ei.gs_ei_russia_federation_electrical_intensity_coefficients
    ADD CONSTRAINT gs_ei_russia_federation_electrical_intensity_coefficients_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ei.gs_ei_russia_federation_electrical_intensity_year_params
    ADD CONSTRAINT gs_ei_russia_federation_electrical_intensity_year_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ei.gs_ei_electrical_intensity_formula_texts
    ADD CONSTRAINT uq_gs_ei_ei_formula_texts_key UNIQUE (formula_key);

ALTER TABLE ONLY gs_ekp.gs_ekp_accum_fixed_capital_formula_texts
    ADD CONSTRAINT gs_ekp_accum_fixed_capital_formula_texts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_accum_monetary_income_params
    ADD CONSTRAINT gs_ekp_federal_district_accum_monetary_income_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params
    ADD CONSTRAINT gs_ekp_federal_district_economic_activity_accum_fixed_capit_pke PRIMARY KEY (id);

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_eat_consumption_params
    ADD CONSTRAINT gs_ekp_federal_district_economic_activity_consumption_param_pke PRIMARY KEY (id);

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_product_output_params
    ADD CONSTRAINT gs_ekp_federal_district_economic_activity_product_output_pa_pke PRIMARY KEY (id);

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_population_params
    ADD CONSTRAINT gs_ekp_federal_district_population_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ekp.gs_ekp_product_output_formula_texts
    ADD CONSTRAINT gs_ekp_product_output_formula_texts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ekp.gs_ekp_russia_federation_accum_fixed_capital_params
    ADD CONSTRAINT gs_ekp_russia_federation_economic_activity_accum_fixed_capi_pke PRIMARY KEY (id);

ALTER TABLE ONLY gs_ekp.gs_ekp_russia_federation_consumption_params
    ADD CONSTRAINT gs_ekp_russia_federation_economic_activity_consumption_para_pke PRIMARY KEY (id);

ALTER TABLE ONLY gs_ekp.gs_ekp_russia_federation_product_output_params
    ADD CONSTRAINT gs_ekp_russia_federation_economic_activity_product_output_p_pke PRIMARY KEY (id);

ALTER TABLE ONLY gs_ekp.gs_ekp_ved_consumption_formula_texts
    ADD CONSTRAINT gs_ekp_ved_consumption_formula_texts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ekp.gs_ekp_accum_fixed_capital_formula_texts
    ADD CONSTRAINT uq_gs_ekp_afci_formula_texts_key UNIQUE (formula_key);

ALTER TABLE ONLY gs_ekp.gs_ekp_product_output_formula_texts
    ADD CONSTRAINT uq_gs_ekp_po_formula_texts_key UNIQUE (formula_key);

ALTER TABLE ONLY gs_ekp.gs_ekp_ved_consumption_formula_texts
    ADD CONSTRAINT uq_gs_ekp_ved_formula_texts_key UNIQUE (formula_key);

ALTER TABLE ONLY gs_fue.gs_fue_allocatable_heat
    ADD CONSTRAINT gs_fue_allocatable_heat_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue.gs_fue_distribution_coefficient_summaries
    ADD CONSTRAINT gs_fue_distribution_coefficient_summaries_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue.gs_fue_distribution_parameters
    ADD CONSTRAINT gs_fue_distribution_parameters_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_coefficient_results
    ADD CONSTRAINT gs_fue_equipment_group_coefficient_results_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_electricity_production_cost
    ADD CONSTRAINT gs_fue_equipment_group_electricity_production_cost_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_extra_fuel_param
    ADD CONSTRAINT gs_fue_equipment_group_extra_fuel_param_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_fuel_formula
    ADD CONSTRAINT gs_fue_equipment_group_fuel_formula_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_fuel_param
    ADD CONSTRAINT gs_fue_equipment_group_fuel_param_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_heat_and_tariffs
    ADD CONSTRAINT gs_fue_equipment_group_heat_and_tariffs_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_natural_fuel
    ADD CONSTRAINT gs_fue_equipment_group_natural_fuel_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_sets
    ADD CONSTRAINT gs_fue_equipment_group_sets_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_specific_fuel_consumption
    ADD CONSTRAINT gs_fue_equipment_group_specific_fuel_consumption_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_specific_fuel_cost
    ADD CONSTRAINT gs_fue_equipment_group_specific_fuel_cost_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_specific_fuel_price
    ADD CONSTRAINT gs_fue_equipment_group_specific_fuel_price_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_type_stations
    ADD CONSTRAINT gs_fue_equipment_group_type_stations_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_groups
    ADD CONSTRAINT gs_fue_equipment_groups_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue.gs_fue_fixed_heat
    ADD CONSTRAINT gs_fue_fixed_heat_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue.gs_fue_formula_texts
    ADD CONSTRAINT gs_fue_formula_texts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue.gs_fue_machine_fuel_param
    ADD CONSTRAINT gs_fue_machine_topl_agr_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue.gs_fue_restrictions
    ADD CONSTRAINT gs_fue_restrictions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_coefficient_results
    ADD CONSTRAINT uq_eq_group_coeff_result_group_dist_year_version UNIQUE (equipment_group_id, distribution_parameter_id, year_number, database_version_id);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_fuel_formula
    ADD CONSTRAINT uq_eq_group_fuel_formula_group_year_variant_version UNIQUE (equipment_group_id, year_number, variant_number, database_version_id);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_type_stations
    ADD CONSTRAINT uq_eq_group_type_station_version UNIQUE (station_id, equipment_group_type_id, database_version_id);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_electricity_production_cost
    ADD CONSTRAINT uq_equipment_group_electricity_production_cost_group_year_code UNIQUE (equipment_group_id, year_number, cost_code);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_extra_fuel_param
    ADD CONSTRAINT uq_equipment_group_extra_fuel_param_group_year UNIQUE (equipment_group_id, year_number);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_fuel_param
    ADD CONSTRAINT uq_equipment_group_fuel_param_group_year UNIQUE (equipment_group_id, year_number);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_heat_and_tariffs
    ADD CONSTRAINT uq_equipment_group_heat_and_tariffs_key UNIQUE (kod_goroda, name_eto, numb1120, var_razv, year_number, database_version_id);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_natural_fuel
    ADD CONSTRAINT uq_equipment_group_natural_fuel_group_year UNIQUE (equipment_group_id, year_number);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_sets
    ADD CONSTRAINT uq_equipment_group_set_link UNIQUE (equipment_group_id, equipment_group_set_station_id);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_specific_fuel_consumption
    ADD CONSTRAINT uq_equipment_group_specific_fuel_consumption_group_year UNIQUE (equipment_group_id, year_number);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_specific_fuel_cost
    ADD CONSTRAINT uq_equipment_group_specific_fuel_cost_group_year UNIQUE (equipment_group_id, year_number);

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_specific_fuel_price
    ADD CONSTRAINT uq_equipment_group_specific_fuel_price_group_year UNIQUE (equipment_group_id, year_number);

ALTER TABLE ONLY gs_fue.gs_fue_allocatable_heat
    ADD CONSTRAINT uq_fue_allocatable_heat_scope_code_year_ver UNIQUE (scope, code, year_number, database_version_id);

ALTER TABLE ONLY gs_fue.gs_fue_distribution_coefficient_summaries
    ADD CONSTRAINT uq_fue_dist_coeff_summary_param_year_version UNIQUE (distribution_parameter_id, year_number, database_version_id);

ALTER TABLE ONLY gs_fue.gs_fue_fixed_heat
    ADD CONSTRAINT uq_fue_fixed_heat_numb_ver UNIQUE (numb1120, database_version_id);

ALTER TABLE ONLY gs_fue.gs_fue_formula_texts
    ADD CONSTRAINT uq_gs_fue_formula_texts_key UNIQUE (formula_key);

ALTER TABLE ONLY gs_fue.gs_fue_machine_fuel_param
    ADD CONSTRAINT uq_machine_fuel_param_machine_id UNIQUE (machine_id);

ALTER TABLE ONLY gs_fue_em.gs_fue_em_business_unit
    ADD CONSTRAINT gs_fue_em_business_unit_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue_em.gs_fue_em_cities
    ADD CONSTRAINT gs_fue_em_cities_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue_em.gs_fue_em_department
    ADD CONSTRAINT gs_fue_em_department_pkey PRIMARY KEY (external_id);

ALTER TABLE ONLY gs_fue_em.gs_fue_em_economic_region
    ADD CONSTRAINT gs_fue_em_economic_region_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue_em.gs_fue_em_equipment_group
    ADD CONSTRAINT gs_fue_em_equipment_group_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue_em.gs_fue_em_federal_district
    ADD CONSTRAINT gs_fue_em_federal_district_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue_em.gs_fue_em_gen_company_branch
    ADD CONSTRAINT gs_fue_em_gen_company_branch_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue_em.gs_fue_em_gen_company
    ADD CONSTRAINT gs_fue_em_gen_company_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue_em.gs_fue_em_territories_energy
    ADD CONSTRAINT gs_fue_em_territories_energy_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue_em.gs_fue_em_union_energy_system
    ADD CONSTRAINT gs_union_energy_system_external_mappings_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_fue_em.gs_fue_em_cities
    ADD CONSTRAINT uq_fue_em_cities_code_topl UNIQUE (code);

ALTER TABLE ONLY gs_fue_em.gs_fue_em_economic_region
    ADD CONSTRAINT uq_gs_fue_em_economic_region_external_id UNIQUE (external_id);

ALTER TABLE ONLY gs_fue_em.gs_fue_em_federal_district
    ADD CONSTRAINT uq_gs_fue_em_federal_district_external_id UNIQUE (external_id);

ALTER TABLE ONLY gs_fue_em.gs_fue_em_union_energy_system
    ADD CONSTRAINT uq_gs_fue_em_union_energy_system_external_id UNIQUE (external_id);

ALTER TABLE ONLY gs_gen.gs_gen_boilers
    ADD CONSTRAINT boilers_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_documents_kommod
    ADD CONSTRAINT documents_kommod_name_version_key UNIQUE (name, database_version_id);

ALTER TABLE ONLY gs_gen.gs_gen_documents_kommod
    ADD CONSTRAINT documents_kommod_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_gaes_tep_source_project_indicators
    ADD CONSTRAINT gaes_tep_source_project_indicators_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_tep_price_conversion_coefficients
    ADD CONSTRAINT ges_tep_price_conversion_coefficients_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_ges_tep_source_project_indicators
    ADD CONSTRAINT ges_tep_source_project_indicators_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_prospective_place_hydro_energy_forecasts
    ADD CONSTRAINT gs_gen_prospective_place_hydro_energy_forecasts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_station_gaes_charge_consumptions
    ADD CONSTRAINT gs_gen_station_gaes_charge_consumptions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_station_owner_energy_generations
    ADD CONSTRAINT gs_gen_station_owner_energy_generations_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_station_snee_efficiencies
    ADD CONSTRAINT gs_gen_station_snee_efficiencies_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_station_snee_energy_consumptions
    ADD CONSTRAINT gs_gen_station_snee_energy_consumptions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_prospective_place_types_gaes
    ADD CONSTRAINT gs_prospective_place_types_gaes_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_prospective_place_types_ges
    ADD CONSTRAINT gs_prospective_place_types_ges_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_prospective_place_types
    ADD CONSTRAINT gs_prospective_place_types_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_machine_fuels
    ADD CONSTRAINT machine_fuels_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_machine_names
    ADD CONSTRAINT machine_names_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_machine_powers
    ADD CONSTRAINT machine_powers_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_machine_prospective_place_aes
    ADD CONSTRAINT machine_prospective_place_aes_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_machine_tes_types
    ADD CONSTRAINT machine_tes_types_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_machines
    ADD CONSTRAINT machines_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_pgu_machine_names
    ADD CONSTRAINT pgu_machine_names_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_pgu_machine_powers
    ADD CONSTRAINT pgu_machine_powers_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_pgu_machines
    ADD CONSTRAINT pgu_machines_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_station_groups
    ADD CONSTRAINT station_groups_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_station_prospective_place_aes
    ADD CONSTRAINT station_prospective_place_aes_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_station_prospective_place_gaes
    ADD CONSTRAINT station_prospective_place_gaes_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_station_prospective_place_ges
    ADD CONSTRAINT station_prospective_place_ges_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_stations
    ADD CONSTRAINT stations_kto_version_key UNIQUE (kto, database_version_id);

ALTER TABLE ONLY gs_gen.gs_gen_stations
    ADD CONSTRAINT stations_location_key UNIQUE (location);

ALTER TABLE ONLY gs_gen.gs_gen_stations
    ADD CONSTRAINT stations_location_version_key UNIQUE (location, database_version_id);

ALTER TABLE ONLY gs_gen.gs_gen_stations
    ADD CONSTRAINT stations_name_archive_key UNIQUE (name_archive);

ALTER TABLE ONLY gs_gen.gs_gen_stations
    ADD CONSTRAINT stations_name_archive_version_key UNIQUE (name_archive, database_version_id);

ALTER TABLE ONLY gs_gen.gs_gen_stations
    ADD CONSTRAINT stations_name_combined_key UNIQUE (name_combined);

ALTER TABLE ONLY gs_gen.gs_gen_stations
    ADD CONSTRAINT stations_name_combined_version_key UNIQUE (name_combined, database_version_id);

ALTER TABLE ONLY gs_gen.gs_gen_stations
    ADD CONSTRAINT stations_name_so_key UNIQUE (name_so);

ALTER TABLE ONLY gs_gen.gs_gen_stations
    ADD CONSTRAINT stations_name_so_version_key UNIQUE (name_so, database_version_id);

ALTER TABLE ONLY gs_gen.gs_gen_stations
    ADD CONSTRAINT stations_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_gen.gs_gen_stations
    ADD CONSTRAINT uq_gs_gen_stations_ver_kto UNIQUE (database_version_id, kto);

ALTER TABLE ONLY gs_gen.gs_gen_prospective_place_types_gaes
    ADD CONSTRAINT uq_gs_prospective_place_types_gaes_name UNIQUE (name);

ALTER TABLE ONLY gs_gen.gs_gen_prospective_place_types_ges
    ADD CONSTRAINT uq_gs_prospective_place_types_ges_name UNIQUE (name);

ALTER TABLE ONLY gs_gen.gs_gen_tep_price_conversion_coefficients
    ADD CONSTRAINT uq_tep_price_conv_coeff_version_year UNIQUE (database_version_id, id_year);

ALTER TABLE ONLY gs_logs.logs
    ADD CONSTRAINT logs_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_pd.gs_pd_centralized_zone_demand_params
    ADD CONSTRAINT gs_centralized_zone_demand_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_pd.gs_pd_ees_demand_params
    ADD CONSTRAINT gs_ees_demand_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_pd.gs_pd_ees_russia_demand_params
    ADD CONSTRAINT gs_ees_russia_demand_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_pd.gs_pd_energy_area_demand_params
    ADD CONSTRAINT gs_energy_area_demand_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_pd.gs_pd_energy_system_type_demand_params
    ADD CONSTRAINT gs_energy_system_type_demand_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_pd.gs_pd_energy_unit_demand_params
    ADD CONSTRAINT gs_energy_unit_demand_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_pd.gs_pd_energy_zone_demand_params
    ADD CONSTRAINT gs_energy_zone_demand_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_pd.gs_pd_federal_district_demand_params
    ADD CONSTRAINT gs_federal_district_demand_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_pd.gs_pd_ozp_max_power_params
    ADD CONSTRAINT gs_pd_ozp_max_power_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_pd.gs_pd_summary_formula_texts
    ADD CONSTRAINT gs_pd_summary_formula_texts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_pd.gs_pd_regional_district_demand_params
    ADD CONSTRAINT gs_regional_district_demand_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_pd.gs_pd_regional_energy_system_demand_params
    ADD CONSTRAINT gs_regional_energy_system_demand_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_pd.gs_pd_russia_federation_demand_params
    ADD CONSTRAINT gs_russia_federation_demand_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_pd.gs_pd_synchronous_area_demand_params
    ADD CONSTRAINT gs_synchronous_area_demand_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_pd.gs_pd_union_energy_system_demand_params
    ADD CONSTRAINT gs_union_energy_system_demand_params_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_pd.gs_pd_summary_formula_texts
    ADD CONSTRAINT uq_gs_pd_summary_formula_texts_key UNIQUE (formula_key);

ALTER TABLE ONLY gs_rs.gs_rs_calculation_workbooks
    ADD CONSTRAINT gs_rs_calculation_workbooks_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_rs.gs_rs_technical_inspection_codes
    ADD CONSTRAINT gs_rs_technical_inspection_codes_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_rs.gs_rs_territory_discount_rates
    ADD CONSTRAINT gs_rs_territory_discount_rates_pkey PRIMARY KEY (database_version_id);

ALTER TABLE ONLY gs_rs.gs_rs_territory_inputs
    ADD CONSTRAINT gs_rs_territory_inputs_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_rs.gs_rs_territory_technologies
    ADD CONSTRAINT gs_rs_territory_technologies_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_rs.gs_rs_territory_transfer_sections
    ADD CONSTRAINT gs_rs_territory_transfer_sections_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_rs.gs_rs_equipment_technical_characteristics
    ADD CONSTRAINT gs_rs_turbine_technical_characteristics_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_rs.gs_rs_calculation_workbooks
    ADD CONSTRAINT uq_rs_calculation_workbook_version_kind UNIQUE (database_version_id, kind);

ALTER TABLE ONLY gs_rs.gs_rs_equipment_technical_characteristics
    ADD CONSTRAINT uq_rs_equipment_code_year_version UNIQUE (database_version_id, equipment_type, equipment_code, report_year);

ALTER TABLE ONLY gs_rs.gs_rs_technical_inspection_codes
    ADD CONSTRAINT uq_rs_inspection_code_version UNIQUE (database_version_id, equipment_code);

ALTER TABLE ONLY gs_rs.gs_rs_territory_inputs
    ADD CONSTRAINT uq_rs_territory_input_version_zone UNIQUE (database_version_id, energy_zone_id);

ALTER TABLE ONLY gs_rs.gs_rs_territory_technologies
    ADD CONSTRAINT uq_rs_territory_technology UNIQUE (database_version_id, energy_zone_id, name);

ALTER TABLE ONLY gs_rs.gs_rs_territory_transfer_sections
    ADD CONSTRAINT uq_rs_territory_transfer_section UNIQUE (database_version_id, name);

ALTER TABLE ONLY gs_sys.gs_sys_condition_types
    ADD CONSTRAINT condition_types_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_database_versions
    ADD CONSTRAINT database_versions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_database_versions
    ADD CONSTRAINT database_versions_version_number_key UNIQUE (version_number);

ALTER TABLE ONLY gs_sys.gs_sys_energy_areas
    ADD CONSTRAINT energy_areas_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_energy_system_types
    ADD CONSTRAINT energy_system_types_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_energy_units
    ADD CONSTRAINT energy_units_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_energy_zones
    ADD CONSTRAINT energy_zones_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_equipment_groups
    ADD CONSTRAINT equipment_groups_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_federal_districts
    ADD CONSTRAINT federal_districts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_fuel_types
    ADD CONSTRAINT fuel_types_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_fuels
    ADD CONSTRAINT fuels_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_companies
    ADD CONSTRAINT gen_companies_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_tep_price_conversion_coefficients
    ADD CONSTRAINT ges_tep_price_conversion_coefficients_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_business_units
    ADD CONSTRAINT gs_business_units_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_departments
    ADD CONSTRAINT gs_departments_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_refdata_entities
    ADD CONSTRAINT gs_refdata_entities_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_refdata_entity_years
    ADD CONSTRAINT gs_refdata_entity_years_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_economic_activity_types
    ADD CONSTRAINT gs_sys_economic_activity_types_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_electricity_production_cost_types
    ADD CONSTRAINT gs_sys_electricity_production_cost_types_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_entity_perimeter_bindings
    ADD CONSTRAINT gs_sys_entity_perimeter_bindings_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_foreign_border_countries
    ADD CONSTRAINT gs_sys_foreign_border_countries_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_perimeter_variants
    ADD CONSTRAINT gs_sys_perimeter_variants_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_year_service
    ADD CONSTRAINT gs_year_service_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_machine_types
    ADD CONSTRAINT machine_types_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_pgu_tes_machine_types
    ADD CONSTRAINT pgu_tes_machine_types_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_regional_district_regional_energy_system
    ADD CONSTRAINT regional_district_regional_energy_system_pkey PRIMARY KEY (regional_district_id, regional_energy_system_id);

ALTER TABLE ONLY gs_sys.gs_sys_regional_districts
    ADD CONSTRAINT regional_districts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_regional_energy_systems
    ADD CONSTRAINT regional_energy_systems_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_station_types
    ADD CONSTRAINT station_types_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_synchronous_areas
    ADD CONSTRAINT synchronous_areas_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_technology_availabilities
    ADD CONSTRAINT technology_availabilities_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_technology_types
    ADD CONSTRAINT technology_types_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_tes_machine_types
    ADD CONSTRAINT tes_machine_types_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_tes_types
    ADD CONSTRAINT tes_types_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_union_energy_systems
    ADD CONSTRAINT union_energy_systems_name_full_version_key UNIQUE (name_full, database_version_id);

ALTER TABLE ONLY gs_sys.gs_sys_union_energy_systems
    ADD CONSTRAINT union_energy_systems_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_economic_activity_types
    ADD CONSTRAINT uq_gs_sys_economic_activity_types_ver_name UNIQUE (database_version_id, name);

ALTER TABLE ONLY gs_sys.gs_sys_electricity_production_cost_types
    ADD CONSTRAINT uq_gs_sys_electricity_production_cost_types_ver_name UNIQUE (database_version_id, name);

ALTER TABLE ONLY gs_sys.gs_sys_entity_perimeter_bindings
    ADD CONSTRAINT uq_gs_sys_entity_perimeter_bindings_entity_variant UNIQUE (entity_kind, entity_name, id_perimeter_variant);

ALTER TABLE ONLY gs_sys.gs_sys_foreign_border_countries
    ADD CONSTRAINT uq_gs_sys_foreign_border_countries_ver_name UNIQUE (database_version_id, name);

ALTER TABLE ONLY gs_sys.gs_sys_perimeter_variants
    ADD CONSTRAINT uq_gs_sys_perimeter_variants_code UNIQUE (code);

ALTER TABLE ONLY gs_sys.gs_sys_years
    ADD CONSTRAINT uq_gs_years_number_version UNIQUE (number, database_version_id);

ALTER TABLE ONLY gs_sys.gs_sys_business_units
    ADD CONSTRAINT uq_refdata_business_units_ver_name UNIQUE (database_version_id, name);

ALTER TABLE ONLY gs_sys.gs_sys_business_units
    ADD CONSTRAINT uq_refdata_business_units_ver_name_abr UNIQUE (database_version_id, name_abr);

ALTER TABLE ONLY gs_sys.gs_sys_business_units
    ADD CONSTRAINT uq_refdata_business_units_ver_name_full UNIQUE (database_version_id, name_full);

ALTER TABLE ONLY gs_sys.gs_sys_departments
    ADD CONSTRAINT uq_refdata_departments_ver_name UNIQUE (database_version_id, name);

ALTER TABLE ONLY gs_sys.gs_sys_departments
    ADD CONSTRAINT uq_refdata_departments_ver_name_abr UNIQUE (database_version_id, name_abr);

ALTER TABLE ONLY gs_sys.gs_sys_departments
    ADD CONSTRAINT uq_refdata_departments_ver_name_full UNIQUE (database_version_id, name_full);

ALTER TABLE ONLY gs_sys.gs_sys_energy_areas
    ADD CONSTRAINT uq_refdata_energy_areas_ver_name UNIQUE (database_version_id, name);

ALTER TABLE ONLY gs_sys.gs_sys_energy_units
    ADD CONSTRAINT uq_refdata_energy_units_ver_name UNIQUE (database_version_id, name);

ALTER TABLE ONLY gs_sys.gs_sys_energy_zones
    ADD CONSTRAINT uq_refdata_energy_zones_ver_name UNIQUE (database_version_id, name);

ALTER TABLE ONLY gs_sys.gs_sys_energy_zones
    ADD CONSTRAINT uq_refdata_energy_zones_ver_number UNIQUE (database_version_id, number);

ALTER TABLE ONLY gs_sys.gs_sys_refdata_entities
    ADD CONSTRAINT uq_refdata_entities_type_id_version UNIQUE (entity_type, entity_id, database_version_id);

ALTER TABLE ONLY gs_sys.gs_sys_refdata_entities
    ADD CONSTRAINT uq_refdata_entities_uuid UNIQUE (ref_uuid);

ALTER TABLE ONLY gs_sys.gs_sys_refdata_entity_years
    ADD CONSTRAINT uq_refdata_entity_years_entity_year_version UNIQUE (refdata_entity_id, year, database_version_id);

ALTER TABLE ONLY gs_sys.gs_sys_federal_districts
    ADD CONSTRAINT uq_refdata_federal_districts_ver_name UNIQUE (database_version_id, name);

ALTER TABLE ONLY gs_sys.gs_sys_federal_districts
    ADD CONSTRAINT uq_refdata_federal_districts_ver_name_abr UNIQUE (database_version_id, name_abr);

ALTER TABLE ONLY gs_sys.gs_sys_federal_districts
    ADD CONSTRAINT uq_refdata_federal_districts_ver_name_full UNIQUE (database_version_id, name_full);

ALTER TABLE ONLY gs_sys.gs_sys_regional_districts
    ADD CONSTRAINT uq_refdata_regional_districts_ver_name UNIQUE (database_version_id, name);

ALTER TABLE ONLY gs_sys.gs_sys_regional_districts
    ADD CONSTRAINT uq_refdata_regional_districts_ver_name_full UNIQUE (database_version_id, name_full);

ALTER TABLE ONLY gs_sys.gs_sys_union_energy_systems
    ADD CONSTRAINT uq_refdata_ues_ver_name UNIQUE (database_version_id, name);

ALTER TABLE ONLY gs_sys.gs_sys_union_energy_systems
    ADD CONSTRAINT uq_refdata_ues_ver_name_full UNIQUE (database_version_id, name_full);

ALTER TABLE ONLY gs_sys.gs_sys_tep_price_conversion_coefficients
    ADD CONSTRAINT uq_tep_price_conv_coeff_version_year UNIQUE (database_version_id, id_year);

ALTER TABLE ONLY gs_sys.gs_sys_year_features
    ADD CONSTRAINT year_features_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_sys.gs_sys_years
    ADD CONSTRAINT years_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ter.gs_ter_energy_unit_power_transfer_values
    ADD CONSTRAINT gs_ter_energy_unit_power_transfer_values_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ter.gs_ter_energy_unit_power_transfers
    ADD CONSTRAINT gs_ter_energy_unit_power_transfers_pkey PRIMARY KEY (id);

ALTER TABLE ONLY gs_ter.gs_ter_energy_unit_power_transfer_values
    ADD CONSTRAINT uq_gs_ter_eu_pt_val_transfer_year_ver UNIQUE (id_energy_unit_power_transfer, year_number, database_version_id);

CREATE UNIQUE INDEX ix_auth_roles_name ON gs_auth.roles USING btree (name);

CREATE UNIQUE INDEX ix_auth_roles_name_full ON gs_auth.roles USING btree (name_full);

CREATE UNIQUE INDEX ix_auth_users_email ON gs_auth.users USING btree (email);

CREATE INDEX ix_auth_users_username ON gs_auth.users USING btree (username);

CREATE INDEX ix_users_last_database_version_id ON gs_auth.users USING btree (last_database_version_id);

CREATE INDEX ix_ee_bal_own_needs_dbver ON gs_bem.gs_bem_ee_balance_station_own_needs_coefficients USING btree (database_version_id);

CREATE INDEX ix_ee_bal_own_needs_station ON gs_bem.gs_bem_ee_balance_station_own_needs_coefficients USING btree (id_station);

CREATE INDEX ix_ee_bal_own_needs_type ON gs_bem.gs_bem_ee_balance_station_own_needs_coefficients USING btree (station_type_key);

CREATE INDEX ix_ee_balance_group_version ON gs_bem.gs_bem_ee_balance_station_group_values USING btree (database_version_id);

CREATE INDEX ix_ee_export_from_rd ON gs_bem.gs_bem_regional_energy_system_ee_exports USING btree (id_from_regional_district);

CREATE INDEX ix_ee_export_from_res ON gs_bem.gs_bem_regional_energy_system_ee_exports USING btree (id_from_regional_energy_system);

CREATE INDEX ix_ee_export_from_to_year_month ON gs_bem.gs_bem_regional_energy_system_ee_exports USING btree (id_from_regional_energy_system, id_from_regional_district, id_to_regional_energy_system, id_to_foreign_border_country, id_to_regional_district, id_to_energy_unit, year_number, month_number);

CREATE INDEX ix_ee_export_month_number ON gs_bem.gs_bem_regional_energy_system_ee_exports USING btree (month_number);

CREATE INDEX ix_ee_export_to_country ON gs_bem.gs_bem_regional_energy_system_ee_exports USING btree (id_to_foreign_border_country);

CREATE INDEX ix_ee_export_to_eu ON gs_bem.gs_bem_regional_energy_system_ee_exports USING btree (id_to_energy_unit);

CREATE INDEX ix_ee_export_to_rd ON gs_bem.gs_bem_regional_energy_system_ee_exports USING btree (id_to_regional_district);

CREATE INDEX ix_ee_export_to_res ON gs_bem.gs_bem_regional_energy_system_ee_exports USING btree (id_to_regional_energy_system);

CREATE INDEX ix_ee_export_ues ON gs_bem.gs_bem_regional_energy_system_ee_exports USING btree (id_union_energy_system);

CREATE INDEX ix_ee_export_year_number ON gs_bem.gs_bem_regional_energy_system_ee_exports USING btree (year_number);

CREATE INDEX ix_ee_import_export_oes_country ON gs_bem.gs_bem_ee_import_export_oes_values USING btree (id_foreign_border_country);

CREATE INDEX ix_ee_import_export_oes_ues ON gs_bem.gs_bem_ee_import_export_oes_values USING btree (id_union_energy_system);

CREATE INDEX ix_ee_import_export_oes_year ON gs_bem.gs_bem_ee_import_export_oes_values USING btree (year_number);

CREATE INDEX ix_ee_receive_transfer_oes_source ON gs_bem.gs_bem_ee_receive_transfer_oes_values USING btree (id_source_union_energy_system);

CREATE INDEX ix_ee_receive_transfer_oes_target ON gs_bem.gs_bem_ee_receive_transfer_oes_values USING btree (id_target_union_energy_system);

CREATE INDEX ix_ee_receive_transfer_oes_year ON gs_bem.gs_bem_ee_receive_transfer_oes_values USING btree (year_number);

CREATE INDEX ix_ee_transfer_from_rd ON gs_bem.gs_bem_regional_energy_system_transfers USING btree (id_from_regional_district);

CREATE INDEX ix_ee_transfer_from_res ON gs_bem.gs_bem_regional_energy_system_transfers USING btree (id_from_regional_energy_system);

CREATE INDEX ix_ee_transfer_from_to_year_month ON gs_bem.gs_bem_regional_energy_system_transfers USING btree (id_from_regional_energy_system, id_from_regional_district, id_to_regional_energy_system, id_to_foreign_border_country, id_to_regional_district, id_to_energy_unit, year_number, month_number);

CREATE INDEX ix_ee_transfer_month_number ON gs_bem.gs_bem_regional_energy_system_transfers USING btree (month_number);

CREATE INDEX ix_ee_transfer_to_country ON gs_bem.gs_bem_regional_energy_system_transfers USING btree (id_to_foreign_border_country);

CREATE INDEX ix_ee_transfer_to_eu ON gs_bem.gs_bem_regional_energy_system_transfers USING btree (id_to_energy_unit);

CREATE INDEX ix_ee_transfer_to_rd ON gs_bem.gs_bem_regional_energy_system_transfers USING btree (id_to_regional_district);

CREATE INDEX ix_ee_transfer_to_res ON gs_bem.gs_bem_regional_energy_system_transfers USING btree (id_to_regional_energy_system);

CREATE INDEX ix_ee_transfer_ues ON gs_bem.gs_bem_regional_energy_system_transfers USING btree (id_union_energy_system);

CREATE INDEX ix_ee_transfer_year_number ON gs_bem.gs_bem_regional_energy_system_transfers USING btree (year_number);

CREATE INDEX ix_em_export_from_rd ON gs_bem.gs_bem_regional_energy_system_em_exports USING btree (id_from_regional_district);

CREATE INDEX ix_em_export_from_res ON gs_bem.gs_bem_regional_energy_system_em_exports USING btree (id_from_regional_energy_system);

CREATE INDEX ix_em_export_from_to_year_month ON gs_bem.gs_bem_regional_energy_system_em_exports USING btree (id_from_regional_energy_system, id_from_regional_district, id_to_regional_energy_system, id_to_foreign_border_country, id_to_regional_district, id_to_energy_unit, year_number, month_number);

CREATE INDEX ix_em_export_month_number ON gs_bem.gs_bem_regional_energy_system_em_exports USING btree (month_number);

CREATE INDEX ix_em_export_to_country ON gs_bem.gs_bem_regional_energy_system_em_exports USING btree (id_to_foreign_border_country);

CREATE INDEX ix_em_export_to_eu ON gs_bem.gs_bem_regional_energy_system_em_exports USING btree (id_to_energy_unit);

CREATE INDEX ix_em_export_to_rd ON gs_bem.gs_bem_regional_energy_system_em_exports USING btree (id_to_regional_district);

CREATE INDEX ix_em_export_to_res ON gs_bem.gs_bem_regional_energy_system_em_exports USING btree (id_to_regional_energy_system);

CREATE INDEX ix_em_export_ues ON gs_bem.gs_bem_regional_energy_system_em_exports USING btree (id_union_energy_system);

CREATE INDEX ix_em_export_year_number ON gs_bem.gs_bem_regional_energy_system_em_exports USING btree (year_number);

CREATE INDEX ix_espp_energy_gen_id_regional_energy_system ON gs_bem.gs_bem_espp_energy_generations USING btree (id_regional_energy_system);

CREATE INDEX ix_espp_energy_gen_month_number ON gs_bem.gs_bem_espp_energy_generations USING btree (month_number);

CREATE INDEX ix_espp_energy_gen_res_year_month ON gs_bem.gs_bem_espp_energy_generations USING btree (id_regional_energy_system, year_number, month_number);

CREATE INDEX ix_espp_energy_gen_year_number ON gs_bem.gs_bem_espp_energy_generations USING btree (year_number);

CREATE INDEX ix_gs_bem_bal_row_note_dbver ON gs_bem.gs_bem_balance_row_notes USING btree (database_version_id);

CREATE INDEX ix_gs_bem_bal_row_note_kind ON gs_bem.gs_bem_balance_row_notes USING btree (balance_kind);

CREATE INDEX ix_gs_bem_bal_row_note_sheet ON gs_bem.gs_bem_balance_row_notes USING btree (sheet_slug);

CREATE INDEX ix_gs_bem_eb_cfr_dbver ON gs_bem.gs_bem_ee_balance_custom_flow_rows USING btree (database_version_id);

CREATE INDEX ix_gs_bem_eb_cfr_direction ON gs_bem.gs_bem_ee_balance_custom_flow_rows USING btree (direction);

CREATE INDEX ix_gs_bem_eb_cfr_parent_key ON gs_bem.gs_bem_ee_balance_custom_flow_rows USING btree (parent_key);

CREATE INDEX ix_gs_bem_eb_cfr_sheet ON gs_bem.gs_bem_ee_balance_custom_flow_rows USING btree (sheet_slug);

CREATE INDEX ix_gs_bem_eb_cfr_sheet_dir_ord ON gs_bem.gs_bem_ee_balance_custom_flow_rows USING btree (sheet_slug, direction, sort_order);

CREATE INDEX ix_gs_bem_eb_cfv_dbver ON gs_bem.gs_bem_ee_balance_custom_flow_values USING btree (database_version_id);

CREATE INDEX ix_gs_bem_eb_cfv_row ON gs_bem.gs_bem_ee_balance_custom_flow_values USING btree (id_row);

CREATE INDEX ix_gs_bem_eb_cfv_year ON gs_bem.gs_bem_ee_balance_custom_flow_values USING btree (year_number);

CREATE INDEX ix_gs_bem_eb_mgen_dbver ON gs_bem.gs_bem_ee_balance_manual_generation_values USING btree (database_version_id);

CREATE INDEX ix_gs_bem_eb_mgen_row ON gs_bem.gs_bem_ee_balance_manual_generation_values USING btree (row_key);

CREATE INDEX ix_gs_bem_eb_mgen_sheet ON gs_bem.gs_bem_ee_balance_manual_generation_values USING btree (sheet_slug);

CREATE INDEX ix_gs_bem_eb_mgen_year ON gs_bem.gs_bem_ee_balance_manual_generation_values USING btree (year_number);

CREATE INDEX ix_gs_bem_eb_tes_m_dbver ON gs_bem.gs_bem_ee_balance_tes_monthly_values USING btree (database_version_id);

CREATE INDEX ix_gs_bem_eb_tes_m_month ON gs_bem.gs_bem_ee_balance_tes_monthly_values USING btree (month_number);

CREATE INDEX ix_gs_bem_eb_tes_m_row ON gs_bem.gs_bem_ee_balance_tes_monthly_values USING btree (row_key);

CREATE INDEX ix_gs_bem_eb_tes_m_sheet ON gs_bem.gs_bem_ee_balance_tes_monthly_values USING btree (sheet_slug);

CREATE INDEX ix_gs_bem_eb_tes_m_year ON gs_bem.gs_bem_ee_balance_tes_monthly_values USING btree (year_number);

CREATE INDEX ix_gs_bem_gs_bem_balance_row_notes_balance_kind ON gs_bem.gs_bem_balance_row_notes USING btree (balance_kind);

CREATE INDEX ix_gs_bem_gs_bem_balance_row_notes_database_version_id ON gs_bem.gs_bem_balance_row_notes USING btree (database_version_id);

CREATE INDEX ix_gs_bem_gs_bem_balance_row_notes_row_key ON gs_bem.gs_bem_balance_row_notes USING btree (row_key);

CREATE INDEX ix_gs_bem_gs_bem_balance_row_notes_sheet_slug ON gs_bem.gs_bem_balance_row_notes USING btree (sheet_slug);

CREATE INDEX ix_gs_bem_gs_bem_ee_balance_tes_monthly_values_database_718b ON gs_bem.gs_bem_ee_balance_tes_monthly_values USING btree (database_version_id);

CREATE INDEX ix_gs_bem_gs_bem_ee_balance_tes_monthly_values_month_number ON gs_bem.gs_bem_ee_balance_tes_monthly_values USING btree (month_number);

CREATE INDEX ix_gs_bem_gs_bem_ee_balance_tes_monthly_values_row_key ON gs_bem.gs_bem_ee_balance_tes_monthly_values USING btree (row_key);

CREATE INDEX ix_gs_bem_gs_bem_ee_balance_tes_monthly_values_sheet_slug ON gs_bem.gs_bem_ee_balance_tes_monthly_values USING btree (sheet_slug);

CREATE INDEX ix_gs_bem_gs_bem_ee_balance_tes_monthly_values_year_number ON gs_bem.gs_bem_ee_balance_tes_monthly_values USING btree (year_number);

CREATE INDEX ix_gs_bem_gs_bem_power_balance_demand_cold_values_datab_77c9 ON gs_bem.gs_bem_power_balance_demand_cold_values USING btree (database_version_id);

CREATE INDEX ix_gs_bem_gs_bem_power_balance_demand_cold_values_sheet_slug ON gs_bem.gs_bem_power_balance_demand_cold_values USING btree (sheet_slug);

CREATE INDEX ix_gs_bem_gs_bem_power_balance_demand_cold_values_year_number ON gs_bem.gs_bem_power_balance_demand_cold_values USING btree (year_number);

CREATE INDEX ix_gs_bem_pb_cfr_dbver ON gs_bem.gs_bem_power_balance_custom_flow_rows USING btree (database_version_id);

CREATE INDEX ix_gs_bem_pb_cfr_direction ON gs_bem.gs_bem_power_balance_custom_flow_rows USING btree (direction);

CREATE INDEX ix_gs_bem_pb_cfr_parent_key ON gs_bem.gs_bem_power_balance_custom_flow_rows USING btree (parent_key);

CREATE INDEX ix_gs_bem_pb_cfr_sheet ON gs_bem.gs_bem_power_balance_custom_flow_rows USING btree (sheet_slug);

CREATE INDEX ix_gs_bem_pb_cfr_sheet_dir_ord ON gs_bem.gs_bem_power_balance_custom_flow_rows USING btree (sheet_slug, direction, sort_order);

CREATE INDEX ix_gs_bem_pb_cfv_dbver ON gs_bem.gs_bem_power_balance_custom_flow_values USING btree (database_version_id);

CREATE INDEX ix_gs_bem_pb_cfv_row ON gs_bem.gs_bem_power_balance_custom_flow_values USING btree (id_row);

CREATE INDEX ix_gs_bem_pb_cfv_year ON gs_bem.gs_bem_power_balance_custom_flow_values USING btree (year_number);

CREATE INDEX ix_gs_bem_pb_cold_dbver ON gs_bem.gs_bem_power_balance_demand_cold_values USING btree (database_version_id);

CREATE INDEX ix_gs_bem_pb_cold_sheet ON gs_bem.gs_bem_power_balance_demand_cold_values USING btree (sheet_slug);

CREATE INDEX ix_gs_bem_pb_cold_year ON gs_bem.gs_bem_power_balance_demand_cold_values USING btree (year_number);

CREATE INDEX ix_gs_bem_pb_exp_dbver ON gs_bem.gs_bem_power_balance_export_values USING btree (database_version_id);

CREATE INDEX ix_gs_bem_pb_exp_sheet ON gs_bem.gs_bem_power_balance_export_values USING btree (sheet_slug);

CREATE INDEX ix_gs_bem_pb_exp_year ON gs_bem.gs_bem_power_balance_export_values USING btree (year_number);

CREATE INDEX ix_res_energy_gen_id_regional_energy_system ON gs_bem.gs_bem_regional_energy_system_energy_generations USING btree (id_regional_energy_system);

CREATE INDEX ix_res_energy_gen_month_number ON gs_bem.gs_bem_regional_energy_system_energy_generations USING btree (month_number);

CREATE INDEX ix_res_energy_gen_res_year_month ON gs_bem.gs_bem_regional_energy_system_energy_generations USING btree (id_regional_energy_system, year_number, month_number);

CREATE INDEX ix_res_energy_gen_year_number ON gs_bem.gs_bem_regional_energy_system_energy_generations USING btree (year_number);

CREATE INDEX ix_station_energy_gen_id_station ON gs_bem.gs_bem_station_energy_generations USING btree (id_station);

CREATE INDEX ix_station_energy_gen_month_number ON gs_bem.gs_bem_station_energy_generations USING btree (month_number);

CREATE INDEX ix_station_energy_gen_station_year_month ON gs_bem.gs_bem_station_energy_generations USING btree (id_station, year_number, month_number);

CREATE INDEX ix_station_energy_gen_year_number ON gs_bem.gs_bem_station_energy_generations USING btree (year_number);

CREATE UNIQUE INDEX uq_ee_bal_own_needs_station_type_year_ver ON gs_bem.gs_bem_ee_balance_station_own_needs_coefficients USING btree (id_station, station_type_key, COALESCE(year_number, '-1'::integer), COALESCE(database_version_id, '-1'::integer));

CREATE UNIQUE INDEX uq_ee_balance_group_page_year_version ON gs_bem.gs_bem_ee_balance_station_group_values USING btree (id_station_group, page_key, year_number, COALESCE(database_version_id, '-1'::integer));

CREATE UNIQUE INDEX uq_ee_export_from_to_ues_year_month_ver ON gs_bem.gs_bem_regional_energy_system_ee_exports USING btree (COALESCE(id_from_regional_energy_system, '-1'::integer), COALESCE(id_from_regional_district, '-1'::integer), COALESCE(id_to_regional_energy_system, '-1'::integer), COALESCE(id_to_foreign_border_country, '-1'::integer), COALESCE(id_to_regional_district, '-1'::integer), COALESCE(id_to_energy_unit, '-1'::integer), id_union_energy_system, year_number, month_number, COALESCE(database_version_id, '-1'::integer));

CREATE UNIQUE INDEX uq_ee_import_export_oes_country_year_ver ON gs_bem.gs_bem_ee_import_export_oes_values USING btree (id_union_energy_system, id_foreign_border_country, year_number, COALESCE(database_version_id, '-1'::integer));

CREATE UNIQUE INDEX uq_ee_receive_transfer_oes_pair_year_ver ON gs_bem.gs_bem_ee_receive_transfer_oes_values USING btree (id_source_union_energy_system, id_target_union_energy_system, year_number, COALESCE(database_version_id, '-1'::integer));

CREATE UNIQUE INDEX uq_ee_transfer_from_to_ues_year_month_ver ON gs_bem.gs_bem_regional_energy_system_transfers USING btree (COALESCE(id_from_regional_energy_system, '-1'::integer), COALESCE(id_from_regional_district, '-1'::integer), COALESCE(id_to_regional_energy_system, '-1'::integer), COALESCE(id_to_foreign_border_country, '-1'::integer), COALESCE(id_to_regional_district, '-1'::integer), COALESCE(id_to_energy_unit, '-1'::integer), id_union_energy_system, year_number, month_number, COALESCE(database_version_id, '-1'::integer));

CREATE UNIQUE INDEX uq_em_export_from_to_ues_year_month_ver ON gs_bem.gs_bem_regional_energy_system_em_exports USING btree (COALESCE(id_from_regional_energy_system, '-1'::integer), COALESCE(id_from_regional_district, '-1'::integer), COALESCE(id_to_regional_energy_system, '-1'::integer), COALESCE(id_to_foreign_border_country, '-1'::integer), COALESCE(id_to_regional_district, '-1'::integer), COALESCE(id_to_energy_unit, '-1'::integer), id_union_energy_system, year_number, month_number, COALESCE(database_version_id, '-1'::integer));

CREATE UNIQUE INDEX uq_espp_energy_gen_res_year_month_ver ON gs_bem.gs_bem_espp_energy_generations USING btree (id_regional_energy_system, year_number, month_number, COALESCE(database_version_id, '-1'::integer));

CREATE UNIQUE INDEX uq_gs_bem_bal_row_note_sheet_kind_key_ver ON gs_bem.gs_bem_balance_row_notes USING btree (sheet_slug, balance_kind, row_key, COALESCE(database_version_id, '-1'::integer));

CREATE UNIQUE INDEX uq_gs_bem_eb_cfv_row_year_ver ON gs_bem.gs_bem_ee_balance_custom_flow_values USING btree (id_row, year_number, COALESCE(database_version_id, '-1'::integer));

CREATE UNIQUE INDEX uq_gs_bem_eb_mgen_sheet_row_year_ver ON gs_bem.gs_bem_ee_balance_manual_generation_values USING btree (sheet_slug, row_key, year_number, COALESCE(database_version_id, '-1'::integer));

CREATE UNIQUE INDEX uq_gs_bem_eb_tes_m_sheet_row_year_month_ver ON gs_bem.gs_bem_ee_balance_tes_monthly_values USING btree (sheet_slug, row_key, year_number, month_number, COALESCE(database_version_id, '-1'::integer));

CREATE UNIQUE INDEX uq_gs_bem_pb_cfv_row_year_ver ON gs_bem.gs_bem_power_balance_custom_flow_values USING btree (id_row, year_number, COALESCE(database_version_id, '-1'::integer));

CREATE UNIQUE INDEX uq_gs_bem_pb_cold_sheet_year_ver ON gs_bem.gs_bem_power_balance_demand_cold_values USING btree (sheet_slug, year_number, COALESCE(database_version_id, '-1'::integer));

CREATE UNIQUE INDEX uq_gs_bem_pb_exp_sheet_year_ver ON gs_bem.gs_bem_power_balance_export_values USING btree (sheet_slug, year_number, COALESCE(database_version_id, '-1'::integer));

CREATE UNIQUE INDEX uq_res_energy_gen_res_year_month_ver ON gs_bem.gs_bem_regional_energy_system_energy_generations USING btree (id_regional_energy_system, year_number, month_number, COALESCE(database_version_id, '-1'::integer));

CREATE UNIQUE INDEX uq_station_energy_gen_station_year_month_ver ON gs_bem.gs_bem_station_energy_generations USING btree (id_station, year_number, month_number, COALESCE(database_version_id, '-1'::integer));

CREATE INDEX ix_gs_ec_centralized_zone_dbver ON gs_ec.gs_ec_centralized_zone_consumption_params USING btree (database_version_id);

CREATE INDEX ix_gs_ec_centralized_zone_pvc ON gs_ec.gs_ec_centralized_zone_consumption_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_ec_centralized_zone_year ON gs_ec.gs_ec_centralized_zone_consumption_params USING btree (year_number);

CREATE INDEX ix_gs_ec_ees_dbver ON gs_ec.gs_ec_ees_consumption_params USING btree (database_version_id);

CREATE INDEX ix_gs_ec_ees_pvc ON gs_ec.gs_ec_ees_consumption_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_ec_ees_russia_dbver ON gs_ec.gs_ec_ees_russia_consumption_params USING btree (database_version_id);

CREATE INDEX ix_gs_ec_ees_russia_pvc ON gs_ec.gs_ec_ees_russia_consumption_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_ec_ees_russia_year ON gs_ec.gs_ec_ees_russia_consumption_params USING btree (year_number);

CREATE INDEX ix_gs_ec_ees_year ON gs_ec.gs_ec_ees_consumption_params USING btree (year_number);

CREATE INDEX ix_gs_ec_energy_area_dbver ON gs_ec.gs_ec_energy_area_consumption_params USING btree (database_version_id);

CREATE INDEX ix_gs_ec_energy_area_id_energy_ar ON gs_ec.gs_ec_energy_area_consumption_params USING btree (id_energy_area);

CREATE INDEX ix_gs_ec_energy_area_pvc ON gs_ec.gs_ec_energy_area_consumption_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_ec_energy_area_year ON gs_ec.gs_ec_energy_area_consumption_params USING btree (year_number);

CREATE INDEX ix_gs_ec_energy_system_type_dbver ON gs_ec.gs_ec_energy_system_type_consumption_params USING btree (database_version_id);

CREATE INDEX ix_gs_ec_energy_system_type_id_energy_sy ON gs_ec.gs_ec_energy_system_type_consumption_params USING btree (id_energy_system_type);

CREATE INDEX ix_gs_ec_energy_system_type_pvc ON gs_ec.gs_ec_energy_system_type_consumption_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_ec_energy_system_type_year ON gs_ec.gs_ec_energy_system_type_consumption_params USING btree (year_number);

CREATE INDEX ix_gs_ec_energy_unit_dbver ON gs_ec.gs_ec_energy_unit_consumption_params USING btree (database_version_id);

CREATE INDEX ix_gs_ec_energy_unit_id_energy_un ON gs_ec.gs_ec_energy_unit_consumption_params USING btree (id_energy_unit);

CREATE INDEX ix_gs_ec_energy_unit_pvc ON gs_ec.gs_ec_energy_unit_consumption_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_ec_energy_unit_year ON gs_ec.gs_ec_energy_unit_consumption_params USING btree (year_number);

CREATE INDEX ix_gs_ec_energy_zone_dbver ON gs_ec.gs_ec_energy_zone_consumption_params USING btree (database_version_id);

CREATE INDEX ix_gs_ec_energy_zone_id_energy_zo ON gs_ec.gs_ec_energy_zone_consumption_params USING btree (id_energy_zone);

CREATE INDEX ix_gs_ec_energy_zone_pvc ON gs_ec.gs_ec_energy_zone_consumption_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_ec_energy_zone_year ON gs_ec.gs_ec_energy_zone_consumption_params USING btree (year_number);

CREATE INDEX ix_gs_ec_federal_district_dbver ON gs_ec.gs_ec_federal_district_consumption_params USING btree (database_version_id);

CREATE INDEX ix_gs_ec_federal_district_id_federal_d ON gs_ec.gs_ec_federal_district_consumption_params USING btree (id_federal_district);

CREATE INDEX ix_gs_ec_federal_district_pvc ON gs_ec.gs_ec_federal_district_consumption_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_ec_federal_district_year ON gs_ec.gs_ec_federal_district_consumption_params USING btree (year_number);

CREATE INDEX ix_gs_ec_regional_district_dbver ON gs_ec.gs_ec_regional_district_consumption_params USING btree (database_version_id);

CREATE INDEX ix_gs_ec_regional_district_id_regional_ ON gs_ec.gs_ec_regional_district_consumption_params USING btree (id_regional_district);

CREATE INDEX ix_gs_ec_regional_district_pvc ON gs_ec.gs_ec_regional_district_consumption_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_ec_regional_district_year ON gs_ec.gs_ec_regional_district_consumption_params USING btree (year_number);

CREATE INDEX ix_gs_ec_regional_energy_system_dbver ON gs_ec.gs_ec_regional_energy_system_consumption_params USING btree (database_version_id);

CREATE INDEX ix_gs_ec_regional_energy_system_id_regional_ ON gs_ec.gs_ec_regional_energy_system_consumption_params USING btree (id_regional_energy_system);

CREATE INDEX ix_gs_ec_regional_energy_system_pvc ON gs_ec.gs_ec_regional_energy_system_consumption_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_ec_regional_energy_system_year ON gs_ec.gs_ec_regional_energy_system_consumption_params USING btree (year_number);

CREATE INDEX ix_gs_ec_russia_federation_dbver ON gs_ec.gs_ec_russia_federation_consumption_params USING btree (database_version_id);

CREATE INDEX ix_gs_ec_russia_federation_pvc ON gs_ec.gs_ec_russia_federation_consumption_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_ec_russia_federation_year ON gs_ec.gs_ec_russia_federation_consumption_params USING btree (year_number);

CREATE INDEX ix_gs_ec_summary_formula_texts_formula_key ON gs_ec.gs_ec_summary_formula_texts USING btree (formula_key);

CREATE INDEX ix_gs_ec_synchronous_area_dbver ON gs_ec.gs_ec_synchronous_area_consumption_params USING btree (database_version_id);

CREATE INDEX ix_gs_ec_synchronous_area_id_synchrono ON gs_ec.gs_ec_synchronous_area_consumption_params USING btree (id_synchronous_area);

CREATE INDEX ix_gs_ec_synchronous_area_pvc ON gs_ec.gs_ec_synchronous_area_consumption_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_ec_synchronous_area_year ON gs_ec.gs_ec_synchronous_area_consumption_params USING btree (year_number);

CREATE INDEX ix_gs_ec_union_energy_system_dbver ON gs_ec.gs_ec_union_energy_system_consumption_params USING btree (database_version_id);

CREATE INDEX ix_gs_ec_union_energy_system_id_union_ene ON gs_ec.gs_ec_union_energy_system_consumption_params USING btree (id_union_energy_system);

CREATE INDEX ix_gs_ec_union_energy_system_pvc ON gs_ec.gs_ec_union_energy_system_consumption_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_ec_union_energy_system_year ON gs_ec.gs_ec_union_energy_system_consumption_params USING btree (year_number);

CREATE UNIQUE INDEX uq_gs_ec_centralized_zone_nullyear ON gs_ec.gs_ec_centralized_zone_consumption_params USING btree (COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NULL);

CREATE UNIQUE INDEX uq_gs_ec_centralized_zone_year ON gs_ec.gs_ec_centralized_zone_consumption_params USING btree (year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NOT NULL);

CREATE UNIQUE INDEX uq_gs_ec_ees_nullyear ON gs_ec.gs_ec_ees_consumption_params USING btree (COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NULL);

CREATE UNIQUE INDEX uq_gs_ec_ees_russia_nullyear ON gs_ec.gs_ec_ees_russia_consumption_params USING btree (COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NULL);

CREATE UNIQUE INDEX uq_gs_ec_ees_russia_year ON gs_ec.gs_ec_ees_russia_consumption_params USING btree (year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NOT NULL);

CREATE UNIQUE INDEX uq_gs_ec_ees_year ON gs_ec.gs_ec_ees_consumption_params USING btree (year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NOT NULL);

CREATE UNIQUE INDEX uq_gs_ec_energy_area_nullyear ON gs_ec.gs_ec_energy_area_consumption_params USING btree (id_energy_area, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NULL);

CREATE UNIQUE INDEX uq_gs_ec_energy_area_year ON gs_ec.gs_ec_energy_area_consumption_params USING btree (id_energy_area, year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NOT NULL);

CREATE UNIQUE INDEX uq_gs_ec_energy_system_type_nullyear ON gs_ec.gs_ec_energy_system_type_consumption_params USING btree (id_energy_system_type, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NULL);

CREATE UNIQUE INDEX uq_gs_ec_energy_system_type_year ON gs_ec.gs_ec_energy_system_type_consumption_params USING btree (id_energy_system_type, year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NOT NULL);

CREATE UNIQUE INDEX uq_gs_ec_energy_unit_nullyear ON gs_ec.gs_ec_energy_unit_consumption_params USING btree (id_energy_unit, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NULL);

CREATE UNIQUE INDEX uq_gs_ec_energy_unit_year ON gs_ec.gs_ec_energy_unit_consumption_params USING btree (id_energy_unit, year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NOT NULL);

CREATE UNIQUE INDEX uq_gs_ec_energy_zone_nullyear ON gs_ec.gs_ec_energy_zone_consumption_params USING btree (id_energy_zone, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NULL);

CREATE UNIQUE INDEX uq_gs_ec_energy_zone_year ON gs_ec.gs_ec_energy_zone_consumption_params USING btree (id_energy_zone, year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NOT NULL);

CREATE UNIQUE INDEX uq_gs_ec_federal_district_nullyear ON gs_ec.gs_ec_federal_district_consumption_params USING btree (id_federal_district, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NULL);

CREATE UNIQUE INDEX uq_gs_ec_federal_district_year ON gs_ec.gs_ec_federal_district_consumption_params USING btree (id_federal_district, year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NOT NULL);

CREATE UNIQUE INDEX uq_gs_ec_regional_district_nullyear ON gs_ec.gs_ec_regional_district_consumption_params USING btree (id_regional_district, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NULL);

CREATE UNIQUE INDEX uq_gs_ec_regional_district_year ON gs_ec.gs_ec_regional_district_consumption_params USING btree (id_regional_district, year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NOT NULL);

CREATE UNIQUE INDEX uq_gs_ec_regional_energy_system_nullyear ON gs_ec.gs_ec_regional_energy_system_consumption_params USING btree (id_regional_energy_system, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NULL);

CREATE UNIQUE INDEX uq_gs_ec_regional_energy_system_year ON gs_ec.gs_ec_regional_energy_system_consumption_params USING btree (id_regional_energy_system, year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NOT NULL);

CREATE UNIQUE INDEX uq_gs_ec_russia_federation_nullyear ON gs_ec.gs_ec_russia_federation_consumption_params USING btree (COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NULL);

CREATE UNIQUE INDEX uq_gs_ec_russia_federation_year ON gs_ec.gs_ec_russia_federation_consumption_params USING btree (year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NOT NULL);

CREATE UNIQUE INDEX uq_gs_ec_synchronous_area_nullyear ON gs_ec.gs_ec_synchronous_area_consumption_params USING btree (id_synchronous_area, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NULL);

CREATE UNIQUE INDEX uq_gs_ec_synchronous_area_year ON gs_ec.gs_ec_synchronous_area_consumption_params USING btree (id_synchronous_area, year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NOT NULL);

CREATE UNIQUE INDEX uq_gs_ec_union_energy_system_nullyear ON gs_ec.gs_ec_union_energy_system_consumption_params USING btree (id_union_energy_system, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NULL);

CREATE UNIQUE INDEX uq_gs_ec_union_energy_system_year ON gs_ec.gs_ec_union_energy_system_consumption_params USING btree (id_union_energy_system, year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (year_number IS NOT NULL);

CREATE INDEX ix_eco_fuel_submission_version_year_scope_status ON gs_eco.gs_eco_fuel_submissions USING btree (database_version_id, year_number, scope, status);

CREATE INDEX ix_eco_gis_tek_pg_dbver ON gs_eco.gs_eco_gis_tek_greenhouse_gas_params USING btree (database_version_id);

CREATE INDEX ix_eco_gis_tek_pg_eg ON gs_eco.gs_eco_gis_tek_greenhouse_gas_params USING btree (equipment_group_id);

CREATE INDEX ix_eco_gis_tek_pg_numb ON gs_eco.gs_eco_gis_tek_greenhouse_gas_params USING btree (station_numb);

CREATE INDEX ix_eco_gis_tek_pg_year ON gs_eco.gs_eco_gis_tek_greenhouse_gas_params USING btree (year_number);

CREATE INDEX ix_eco_gis_tek_zv_dbver ON gs_eco.gs_eco_gis_tek_pollutant_params USING btree (database_version_id);

CREATE INDEX ix_eco_gis_tek_zv_eg ON gs_eco.gs_eco_gis_tek_pollutant_params USING btree (equipment_group_id);

CREATE INDEX ix_eco_gis_tek_zv_numb ON gs_eco.gs_eco_gis_tek_pollutant_params USING btree (station_numb);

CREATE INDEX ix_eco_gis_tek_zv_year ON gs_eco.gs_eco_gis_tek_pollutant_params USING btree (year_number);

CREATE INDEX ix_eco_nt_norm_class ON gs_eco.gs_eco_new_tes_norms USING btree (capacity_class);

CREATE INDEX ix_eco_nt_norm_dbver ON gs_eco.gs_eco_new_tes_norms USING btree (database_version_id);

CREATE INDEX ix_eco_nt_norm_fuel ON gs_eco.gs_eco_new_tes_norms USING btree (fuel_key);

CREATE INDEX ix_eco_nt_norm_year ON gs_eco.gs_eco_new_tes_norms USING btree (year_number);

CREATE INDEX ix_eco_ot_coeff_dbver ON gs_eco.gs_eco_operating_tes_coefficients USING btree (database_version_id);

CREATE INDEX ix_eco_ot_coeff_kind ON gs_eco.gs_eco_operating_tes_coefficients USING btree (kind);

CREATE INDEX ix_eco_ot_coeff_terr ON gs_eco.gs_eco_operating_tes_coefficients USING btree (territory_slug);

CREATE INDEX ix_eco_ot_coeff_year ON gs_eco.gs_eco_operating_tes_coefficients USING btree (year_number);

CREATE INDEX ix_eco_ot_fuel_char_dbver ON gs_eco.gs_eco_operating_tes_fuel_chars USING btree (database_version_id);

CREATE INDEX ix_eco_ot_fuel_char_key ON gs_eco.gs_eco_operating_tes_fuel_chars USING btree (fuel_key);

CREATE INDEX ix_eco_ot_fuel_char_year ON gs_eco.gs_eco_operating_tes_fuel_chars USING btree (year_number);

CREATE INDEX ix_eco_ot_input_dbver ON gs_eco.gs_eco_operating_tes_inputs USING btree (database_version_id);

CREATE INDEX ix_eco_ot_input_key ON gs_eco.gs_eco_operating_tes_inputs USING btree (row_key);

CREATE INDEX ix_eco_ot_input_terr ON gs_eco.gs_eco_operating_tes_inputs USING btree (territory_slug);

CREATE INDEX ix_eco_ot_input_year ON gs_eco.gs_eco_operating_tes_inputs USING btree (year_number);

CREATE INDEX ix_gs_eco_analysis_pg_params_database_version_id ON gs_eco.gs_eco_analysis_pg_params USING btree (database_version_id);

CREATE INDEX ix_gs_eco_analysis_pg_params_sheet_slug ON gs_eco.gs_eco_analysis_pg_params USING btree (sheet_slug);

CREATE INDEX ix_gs_eco_analysis_pg_params_station_numb ON gs_eco.gs_eco_analysis_pg_params USING btree (station_numb);

CREATE INDEX ix_gs_eco_analysis_pg_params_year_number ON gs_eco.gs_eco_analysis_pg_params USING btree (year_number);

CREATE INDEX ix_gs_eco_analysis_zv_params_database_version_id ON gs_eco.gs_eco_analysis_zv_params USING btree (database_version_id);

CREATE INDEX ix_gs_eco_analysis_zv_params_sheet_slug ON gs_eco.gs_eco_analysis_zv_params USING btree (sheet_slug);

CREATE INDEX ix_gs_eco_analysis_zv_params_station_numb ON gs_eco.gs_eco_analysis_zv_params USING btree (station_numb);

CREATE INDEX ix_gs_eco_analysis_zv_params_year_number ON gs_eco.gs_eco_analysis_zv_params USING btree (year_number);

CREATE INDEX ix_gs_eco_gs_eco_operating_tes_fuel_chars_territory_slug ON gs_eco.gs_eco_operating_tes_fuel_chars USING btree (territory_slug);

CREATE INDEX ix_gs_eco_operating_tes_formula_texts_formula_key ON gs_eco.gs_eco_operating_tes_formula_texts USING btree (formula_key);

CREATE INDEX ix_ei_fd_pop_cons_coef_fd ON gs_ei.gs_ei_federal_district_population_consumption_coefficients USING btree (id_federal_district);

CREATE INDEX ix_ei_fd_pop_cons_year_fd ON gs_ei.gs_ei_federal_district_population_consumption_year_params USING btree (id_federal_district);

CREATE INDEX ix_ei_fd_pop_cons_year_kind ON gs_ei.gs_ei_federal_district_population_consumption_year_params USING btree (row_kind);

CREATE INDEX ix_ei_fd_pop_cons_year_num ON gs_ei.gs_ei_federal_district_population_consumption_year_params USING btree (year_number);

CREATE INDEX ix_ei_fd_total_cons_coef_fd ON gs_ei.gs_ei_federal_district_fd_total_consumption_coefficients USING btree (id_federal_district);

CREATE UNIQUE INDEX ix_ei_fd_total_cons_coef_fd_kind_ver ON gs_ei.gs_ei_federal_district_fd_total_consumption_coefficients USING btree (id_federal_district, row_kind, database_version_id);

CREATE INDEX ix_ei_fd_total_cons_coef_row_kind ON gs_ei.gs_ei_federal_district_fd_total_consumption_coefficients USING btree (row_kind);

CREATE INDEX ix_gs_ei_ei_formula_key ON gs_ei.gs_ei_electrical_intensity_formula_texts USING btree (formula_key);

CREATE INDEX ix_gs_ei_fd_ei_c_fd ON gs_ei.gs_ei_federal_district_electrical_intensity_coefficients USING btree (id_federal_district);

CREATE INDEX ix_gs_ei_fd_ei_c_ved ON gs_ei.gs_ei_federal_district_electrical_intensity_coefficients USING btree (id_economic_activity_type);

CREATE INDEX ix_gs_ei_fd_ei_y_dbver ON gs_ei.gs_ei_federal_district_electrical_intensity_year_params USING btree (database_version_id);

CREATE INDEX ix_gs_ei_fd_ei_y_fd ON gs_ei.gs_ei_federal_district_electrical_intensity_year_params USING btree (id_federal_district);

CREATE INDEX ix_gs_ei_fd_ei_y_kind ON gs_ei.gs_ei_federal_district_electrical_intensity_year_params USING btree (row_kind);

CREATE INDEX ix_gs_ei_fd_ei_y_ved ON gs_ei.gs_ei_federal_district_electrical_intensity_year_params USING btree (id_economic_activity_type);

CREATE INDEX ix_gs_ei_fd_ei_y_year ON gs_ei.gs_ei_federal_district_electrical_intensity_year_params USING btree (year_number);

CREATE INDEX ix_gs_ei_rf_ei_y_dbver ON gs_ei.gs_ei_russia_federation_electrical_intensity_year_params USING btree (database_version_id);

CREATE INDEX ix_gs_ei_rf_ei_y_kind ON gs_ei.gs_ei_russia_federation_electrical_intensity_year_params USING btree (row_kind);

CREATE INDEX ix_gs_ei_rf_ei_y_year ON gs_ei.gs_ei_russia_federation_electrical_intensity_year_params USING btree (year_number);

CREATE UNIQUE INDEX uq_gs_ei_fd_ei_c_coef ON gs_ei.gs_ei_federal_district_electrical_intensity_coefficients USING btree (id_federal_district, id_economic_activity_type, COALESCE(database_version_id, 0));

CREATE UNIQUE INDEX uq_gs_ei_fd_ei_y_year ON gs_ei.gs_ei_federal_district_electrical_intensity_year_params USING btree (id_federal_district, id_economic_activity_type, row_kind, year_number, COALESCE(database_version_id, 0)) WHERE (year_number IS NOT NULL);

CREATE UNIQUE INDEX uq_gs_ei_rf_ei_c_coef ON gs_ei.gs_ei_russia_federation_electrical_intensity_coefficients USING btree (COALESCE(database_version_id, 0));

CREATE UNIQUE INDEX uq_gs_ei_rf_ei_y_year ON gs_ei.gs_ei_russia_federation_electrical_intensity_year_params USING btree (row_kind, year_number, COALESCE(database_version_id, 0)) WHERE (year_number IS NOT NULL);

CREATE INDEX ix_ekp_fd_po_id_year_spec_out ON gs_ekp.gs_ekp_federal_district_product_output_params USING btree (id_year_specific_product_output);

CREATE INDEX ix_ekp_rf_po_id_year_spec_out ON gs_ekp.gs_ekp_russia_federation_product_output_params USING btree (id_year_specific_product_output);

CREATE INDEX ix_gs_ekp_afci_formula_key ON gs_ekp.gs_ekp_accum_fixed_capital_formula_texts USING btree (formula_key);

CREATE INDEX ix_gs_ekp_fd_afci_dbver ON gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params USING btree (database_version_id);

CREATE INDEX ix_gs_ekp_fd_afci_fd ON gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params USING btree (id_federal_district);

CREATE INDEX ix_gs_ekp_fd_afci_ved ON gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params USING btree (id_economic_activity_type);

CREATE INDEX ix_gs_ekp_fd_afci_year ON gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params USING btree (year_number);

CREATE INDEX ix_gs_ekp_fd_ami_dbver ON gs_ekp.gs_ekp_federal_district_accum_monetary_income_params USING btree (database_version_id);

CREATE INDEX ix_gs_ekp_fd_ami_fd ON gs_ekp.gs_ekp_federal_district_accum_monetary_income_params USING btree (id_federal_district);

CREATE INDEX ix_gs_ekp_fd_ami_year ON gs_ekp.gs_ekp_federal_district_accum_monetary_income_params USING btree (year_number);

CREATE INDEX ix_gs_ekp_fd_po_dbver ON gs_ekp.gs_ekp_federal_district_product_output_params USING btree (database_version_id);

CREATE INDEX ix_gs_ekp_fd_po_fd ON gs_ekp.gs_ekp_federal_district_product_output_params USING btree (id_federal_district);

CREATE INDEX ix_gs_ekp_fd_po_ved ON gs_ekp.gs_ekp_federal_district_product_output_params USING btree (id_economic_activity_type);

CREATE INDEX ix_gs_ekp_fd_po_year ON gs_ekp.gs_ekp_federal_district_product_output_params USING btree (year_number);

CREATE INDEX ix_gs_ekp_fd_pop_dbver ON gs_ekp.gs_ekp_federal_district_population_params USING btree (database_version_id);

CREATE INDEX ix_gs_ekp_fd_pop_fd ON gs_ekp.gs_ekp_federal_district_population_params USING btree (id_federal_district);

CREATE INDEX ix_gs_ekp_fd_pop_year ON gs_ekp.gs_ekp_federal_district_population_params USING btree (year_number);

CREATE INDEX ix_gs_ekp_fd_ved_dbver ON gs_ekp.gs_ekp_federal_district_eat_consumption_params USING btree (database_version_id);

CREATE INDEX ix_gs_ekp_fd_ved_fd ON gs_ekp.gs_ekp_federal_district_eat_consumption_params USING btree (id_federal_district);

CREATE INDEX ix_gs_ekp_fd_ved_ved ON gs_ekp.gs_ekp_federal_district_eat_consumption_params USING btree (id_economic_activity_type);

CREATE INDEX ix_gs_ekp_fd_ved_year ON gs_ekp.gs_ekp_federal_district_eat_consumption_params USING btree (year_number);

CREATE INDEX ix_gs_ekp_po_formula_key ON gs_ekp.gs_ekp_product_output_formula_texts USING btree (formula_key);

CREATE INDEX ix_gs_ekp_rf_afci_dbver ON gs_ekp.gs_ekp_russia_federation_accum_fixed_capital_params USING btree (database_version_id);

CREATE INDEX ix_gs_ekp_rf_afci_ved ON gs_ekp.gs_ekp_russia_federation_accum_fixed_capital_params USING btree (id_economic_activity_type);

CREATE INDEX ix_gs_ekp_rf_afci_year ON gs_ekp.gs_ekp_russia_federation_accum_fixed_capital_params USING btree (year_number);

CREATE INDEX ix_gs_ekp_rf_po_dbver ON gs_ekp.gs_ekp_russia_federation_product_output_params USING btree (database_version_id);

CREATE INDEX ix_gs_ekp_rf_po_ved ON gs_ekp.gs_ekp_russia_federation_product_output_params USING btree (id_economic_activity_type);

CREATE INDEX ix_gs_ekp_rf_po_year ON gs_ekp.gs_ekp_russia_federation_product_output_params USING btree (year_number);

CREATE INDEX ix_gs_ekp_rf_ved_dbver ON gs_ekp.gs_ekp_russia_federation_consumption_params USING btree (database_version_id);

CREATE INDEX ix_gs_ekp_rf_ved_ved ON gs_ekp.gs_ekp_russia_federation_consumption_params USING btree (id_economic_activity_type);

CREATE INDEX ix_gs_ekp_rf_ved_year ON gs_ekp.gs_ekp_russia_federation_consumption_params USING btree (year_number);

CREATE INDEX ix_gs_ekp_ved_formula_key ON gs_ekp.gs_ekp_ved_consumption_formula_texts USING btree (formula_key);

CREATE UNIQUE INDEX uq_gs_ekp_fd_afci_year ON gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params USING btree (id_federal_district, id_economic_activity_type, year_number, COALESCE(database_version_id, 0)) WHERE (year_number IS NOT NULL);

CREATE UNIQUE INDEX uq_gs_ekp_fd_ami_year ON gs_ekp.gs_ekp_federal_district_accum_monetary_income_params USING btree (id_federal_district, year_number, COALESCE(database_version_id, 0)) WHERE (year_number IS NOT NULL);

CREATE UNIQUE INDEX uq_gs_ekp_fd_po_year ON gs_ekp.gs_ekp_federal_district_product_output_params USING btree (id_federal_district, id_economic_activity_type, year_number, COALESCE(database_version_id, 0)) WHERE (year_number IS NOT NULL);

CREATE UNIQUE INDEX uq_gs_ekp_fd_pop_year ON gs_ekp.gs_ekp_federal_district_population_params USING btree (id_federal_district, year_number, COALESCE(database_version_id, 0)) WHERE (year_number IS NOT NULL);

CREATE UNIQUE INDEX uq_gs_ekp_fd_ved_year ON gs_ekp.gs_ekp_federal_district_eat_consumption_params USING btree (id_federal_district, id_economic_activity_type, year_number, COALESCE(database_version_id, 0)) WHERE (year_number IS NOT NULL);

CREATE UNIQUE INDEX uq_gs_ekp_rf_afci_year ON gs_ekp.gs_ekp_russia_federation_accum_fixed_capital_params USING btree (id_economic_activity_type, year_number, COALESCE(database_version_id, 0)) WHERE (year_number IS NOT NULL);

CREATE UNIQUE INDEX uq_gs_ekp_rf_po_year ON gs_ekp.gs_ekp_russia_federation_product_output_params USING btree (id_economic_activity_type, year_number, COALESCE(database_version_id, 0)) WHERE (year_number IS NOT NULL);

CREATE UNIQUE INDEX uq_gs_ekp_rf_ved_year ON gs_ekp.gs_ekp_russia_federation_consumption_params USING btree (id_economic_activity_type, year_number, COALESCE(database_version_id, 0)) WHERE (year_number IS NOT NULL);

CREATE INDEX ix_equipment_group_external_code ON gs_fue.gs_fue_equipment_groups USING btree (external_code);

CREATE INDEX ix_fue_dist_coeff_sum_db_ver ON gs_fue.gs_fue_distribution_coefficient_summaries USING btree (database_version_id);

CREATE INDEX ix_fue_dist_coeff_sum_param ON gs_fue.gs_fue_distribution_coefficient_summaries USING btree (distribution_parameter_id);

CREATE INDEX ix_fue_dist_coeff_sum_year ON gs_fue.gs_fue_distribution_coefficient_summaries USING btree (year_number);

CREATE INDEX ix_fue_eg_coeff_res_db_ver ON gs_fue.gs_fue_equipment_group_coefficient_results USING btree (database_version_id);

CREATE INDEX ix_fue_eg_coeff_res_dist_id ON gs_fue.gs_fue_equipment_group_coefficient_results USING btree (distribution_parameter_id);

CREATE INDEX ix_fue_eg_coeff_res_eg_id ON gs_fue.gs_fue_equipment_group_coefficient_results USING btree (equipment_group_id);

CREATE INDEX ix_fue_eg_coeff_res_year ON gs_fue.gs_fue_equipment_group_coefficient_results USING btree (year_number);

CREATE INDEX ix_gs_fue_allocatable_heat_code ON gs_fue.gs_fue_allocatable_heat USING btree (code);

CREATE INDEX ix_gs_fue_allocatable_heat_database_version_id ON gs_fue.gs_fue_allocatable_heat USING btree (database_version_id);

CREATE INDEX ix_gs_fue_allocatable_heat_scope ON gs_fue.gs_fue_allocatable_heat USING btree (scope);

CREATE INDEX ix_gs_fue_allocatable_heat_year_number ON gs_fue.gs_fue_allocatable_heat USING btree (year_number);

CREATE INDEX ix_gs_fue_distribution_parameters_database_version_id ON gs_fue.gs_fue_distribution_parameters USING btree (database_version_id);

CREATE INDEX ix_gs_fue_distribution_parameters_id_base_year ON gs_fue.gs_fue_distribution_parameters USING btree (id_base_year);

CREATE INDEX ix_gs_fue_distribution_parameters_id_union_energy_system ON gs_fue.gs_fue_distribution_parameters USING btree (id_union_energy_system);

CREATE INDEX ix_gs_fue_distribution_parameters_id_year ON gs_fue.gs_fue_distribution_parameters USING btree (id_year);

CREATE INDEX ix_gs_fue_distribution_parameters_ref_uuid ON gs_fue.gs_fue_distribution_parameters USING btree (ref_uuid);

CREATE INDEX ix_gs_fue_eg_electricity_production_cost_cost_code ON gs_fue.gs_fue_equipment_group_electricity_production_cost USING btree (cost_code);

CREATE INDEX ix_gs_fue_eg_electricity_production_cost_database_version_id ON gs_fue.gs_fue_equipment_group_electricity_production_cost USING btree (database_version_id);

CREATE INDEX ix_gs_fue_eg_electricity_production_cost_equipment_group_id ON gs_fue.gs_fue_equipment_group_electricity_production_cost USING btree (equipment_group_id);

CREATE INDEX ix_gs_fue_eg_electricity_production_cost_numb1120 ON gs_fue.gs_fue_equipment_group_electricity_production_cost USING btree (numb1120);

CREATE INDEX ix_gs_fue_eg_electricity_production_cost_year_number ON gs_fue.gs_fue_equipment_group_electricity_production_cost USING btree (year_number);

CREATE INDEX ix_gs_fue_eg_heat_and_tariffs_database_version_id ON gs_fue.gs_fue_equipment_group_heat_and_tariffs USING btree (database_version_id);

CREATE INDEX ix_gs_fue_eg_heat_and_tariffs_equipment_group_id ON gs_fue.gs_fue_equipment_group_heat_and_tariffs USING btree (equipment_group_id);

CREATE INDEX ix_gs_fue_eg_heat_and_tariffs_kod_goroda ON gs_fue.gs_fue_equipment_group_heat_and_tariffs USING btree (kod_goroda);

CREATE INDEX ix_gs_fue_eg_heat_and_tariffs_numb1120 ON gs_fue.gs_fue_equipment_group_heat_and_tariffs USING btree (numb1120);

CREATE INDEX ix_gs_fue_eg_heat_and_tariffs_year_number ON gs_fue.gs_fue_equipment_group_heat_and_tariffs USING btree (year_number);

CREATE INDEX ix_gs_fue_equipment_group_extra_fuel_param_database_version_id ON gs_fue.gs_fue_equipment_group_extra_fuel_param USING btree (database_version_id);

CREATE INDEX ix_gs_fue_equipment_group_extra_fuel_param_equipment_group_id ON gs_fue.gs_fue_equipment_group_extra_fuel_param USING btree (equipment_group_id);

CREATE INDEX ix_gs_fue_equipment_group_extra_fuel_param_numb1120 ON gs_fue.gs_fue_equipment_group_extra_fuel_param USING btree (numb1120);

CREATE INDEX ix_gs_fue_equipment_group_extra_fuel_param_year_number ON gs_fue.gs_fue_equipment_group_extra_fuel_param USING btree (year_number);

CREATE INDEX ix_gs_fue_equipment_group_fuel_formula_database_version_id ON gs_fue.gs_fue_equipment_group_fuel_formula USING btree (database_version_id);

CREATE INDEX ix_gs_fue_equipment_group_fuel_formula_equipment_group_id ON gs_fue.gs_fue_equipment_group_fuel_formula USING btree (equipment_group_id);

CREATE INDEX ix_gs_fue_equipment_group_fuel_formula_numb1 ON gs_fue.gs_fue_equipment_group_fuel_formula USING btree (numb1);

CREATE INDEX ix_gs_fue_equipment_group_fuel_formula_numb1120 ON gs_fue.gs_fue_equipment_group_fuel_formula USING btree (numb1120);

CREATE INDEX ix_gs_fue_equipment_group_fuel_formula_variant_number ON gs_fue.gs_fue_equipment_group_fuel_formula USING btree (variant_number);

CREATE INDEX ix_gs_fue_equipment_group_fuel_formula_year_number ON gs_fue.gs_fue_equipment_group_fuel_formula USING btree (year_number);

CREATE INDEX ix_gs_fue_equipment_group_fuel_param_be ON gs_fue.gs_fue_equipment_group_fuel_param USING btree (be);

CREATE INDEX ix_gs_fue_equipment_group_fuel_param_database_version_id ON gs_fue.gs_fue_equipment_group_fuel_param USING btree (database_version_id);

CREATE INDEX ix_gs_fue_equipment_group_fuel_param_dep ON gs_fue.gs_fue_equipment_group_fuel_param USING btree (dep);

CREATE INDEX ix_gs_fue_equipment_group_fuel_param_equipment_group_id ON gs_fue.gs_fue_equipment_group_fuel_param USING btree (equipment_group_id);

CREATE INDEX ix_gs_fue_equipment_group_fuel_param_er ON gs_fue.gs_fue_equipment_group_fuel_param USING btree (er);

CREATE INDEX ix_gs_fue_equipment_group_fuel_param_gk ON gs_fue.gs_fue_equipment_group_fuel_param USING btree (gk);

CREATE INDEX ix_gs_fue_equipment_group_fuel_param_obl ON gs_fue.gs_fue_equipment_group_fuel_param USING btree (obl);

CREATE INDEX ix_gs_fue_equipment_group_fuel_param_obor ON gs_fue.gs_fue_equipment_group_fuel_param USING btree (obor);

CREATE INDEX ix_gs_fue_equipment_group_fuel_param_oes ON gs_fue.gs_fue_equipment_group_fuel_param USING btree (oes);

CREATE INDEX ix_gs_fue_equipment_group_fuel_param_year_number ON gs_fue.gs_fue_equipment_group_fuel_param USING btree (year_number);

CREATE INDEX ix_gs_fue_equipment_group_natural_fuel_database_version_id ON gs_fue.gs_fue_equipment_group_natural_fuel USING btree (database_version_id);

CREATE INDEX ix_gs_fue_equipment_group_natural_fuel_dep ON gs_fue.gs_fue_equipment_group_natural_fuel USING btree (dep);

CREATE INDEX ix_gs_fue_equipment_group_natural_fuel_equipment_group_id ON gs_fue.gs_fue_equipment_group_natural_fuel USING btree (equipment_group_id);

CREATE INDEX ix_gs_fue_equipment_group_natural_fuel_er ON gs_fue.gs_fue_equipment_group_natural_fuel USING btree (er);

CREATE INDEX ix_gs_fue_equipment_group_natural_fuel_numb1120 ON gs_fue.gs_fue_equipment_group_natural_fuel USING btree (numb1120);

CREATE INDEX ix_gs_fue_equipment_group_natural_fuel_obl ON gs_fue.gs_fue_equipment_group_natural_fuel USING btree (obl);

CREATE INDEX ix_gs_fue_equipment_group_natural_fuel_oes ON gs_fue.gs_fue_equipment_group_natural_fuel USING btree (oes);

CREATE INDEX ix_gs_fue_equipment_group_natural_fuel_year_number ON gs_fue.gs_fue_equipment_group_natural_fuel USING btree (year_number);

CREATE INDEX ix_gs_fue_equipment_groups_be ON gs_fue.gs_fue_equipment_groups USING btree (be);

CREATE INDEX ix_gs_fue_equipment_groups_dep ON gs_fue.gs_fue_equipment_groups USING btree (dep);

CREATE INDEX ix_gs_fue_equipment_groups_energy_unit_id ON gs_fue.gs_fue_equipment_groups USING btree (energy_unit_id);

CREATE INDEX ix_gs_fue_equipment_groups_er ON gs_fue.gs_fue_equipment_groups USING btree (er);

CREATE INDEX ix_gs_fue_equipment_groups_fo ON gs_fue.gs_fue_equipment_groups USING btree (fo);

CREATE INDEX ix_gs_fue_equipment_groups_gk ON gs_fue.gs_fue_equipment_groups USING btree (gk);

CREATE INDEX ix_gs_fue_equipment_groups_gkf ON gs_fue.gs_fue_equipment_groups USING btree (gkf);

CREATE INDEX ix_gs_fue_equipment_groups_obl ON gs_fue.gs_fue_equipment_groups USING btree (obl);

CREATE INDEX ix_gs_fue_equipment_groups_oes ON gs_fue.gs_fue_equipment_groups USING btree (oes);

CREATE INDEX ix_gs_fue_equipment_groups_regional_district_id ON gs_fue.gs_fue_equipment_groups USING btree (regional_district_id);

CREATE INDEX ix_gs_fue_equipment_groups_regional_energy_system_id ON gs_fue.gs_fue_equipment_groups USING btree (regional_energy_system_id);

CREATE INDEX ix_gs_fue_fixed_heat_database_version_id ON gs_fue.gs_fue_fixed_heat USING btree (database_version_id);

CREATE INDEX ix_gs_fue_fixed_heat_numb1120 ON gs_fue.gs_fue_fixed_heat USING btree (numb1120);

CREATE INDEX ix_gs_fue_formula_texts_formula_key ON gs_fue.gs_fue_formula_texts USING btree (formula_key);

CREATE INDEX ix_gs_fue_machine_fuel_param_database_version_id ON gs_fue.gs_fue_machine_fuel_param USING btree (database_version_id);

CREATE INDEX ix_gs_fue_machine_fuel_param_equipment_group_id ON gs_fue.gs_fue_machine_fuel_param USING btree (equipment_group_id);

CREATE INDEX ix_gs_fue_machine_fuel_param_grcode ON gs_fue.gs_fue_machine_fuel_param USING btree (grcode);

CREATE INDEX ix_gs_fue_restrictions_database_version_id ON gs_fue.gs_fue_restrictions USING btree (database_version_id);

CREATE INDEX ix_gs_fue_restrictions_obl ON gs_fue.gs_fue_restrictions USING btree (obl);

CREATE INDEX ix_bu_em_external_id ON gs_fue_em.gs_fue_em_business_unit USING btree (external_id);

CREATE INDEX ix_fd_em_external_id ON gs_fue_em.gs_fue_em_federal_district USING btree (external_id);

CREATE INDEX ix_fd_em_federal_district_ref_uuid ON gs_fue_em.gs_fue_em_federal_district USING btree (federal_district_ref_uuid);

CREATE UNIQUE INDEX ix_fue_em_cities_code_topl ON gs_fue_em.gs_fue_em_cities USING btree (code);

CREATE INDEX ix_fue_em_cities_obl ON gs_fue_em.gs_fue_em_cities USING btree (obl);

CREATE INDEX ix_fue_em_eq_group_code ON gs_fue_em.gs_fue_em_equipment_group USING btree (code);

CREATE INDEX ix_fue_em_eq_group_ref_uuid ON gs_fue_em.gs_fue_em_equipment_group USING btree (equipment_group_ref_uuid);

CREATE INDEX ix_gc_branch_em_external_id ON gs_fue_em.gs_fue_em_gen_company_branch USING btree (external_id);

CREATE INDEX ix_gc_branch_em_gen_company_ref_uuid ON gs_fue_em.gs_fue_em_gen_company_branch USING btree (gen_company_ref_uuid);

CREATE UNIQUE INDEX ix_gen_company_em_external_id ON gs_fue_em.gs_fue_em_gen_company USING btree (external_id);

CREATE INDEX ix_gen_company_em_gen_company_ref_uuid ON gs_fue_em.gs_fue_em_gen_company USING btree (gen_company_ref_uuid);

CREATE UNIQUE INDEX ix_gs_fue_em_territories_energy_external_id ON gs_fue_em.gs_fue_em_territories_energy USING btree (external_id);

CREATE INDEX ix_gs_fue_em_territories_energy_ez_uuid ON gs_fue_em.gs_fue_em_territories_energy USING btree (energy_zone_ref_uuid);

CREATE INDEX ix_gs_fue_em_territories_energy_rd_uuid ON gs_fue_em.gs_fue_em_territories_energy USING btree (regional_district_ref_uuid);

CREATE INDEX ix_gs_fue_em_territories_energy_res_uuid ON gs_fue_em.gs_fue_em_territories_energy USING btree (regional_energy_system_ref_uuid);

CREATE INDEX ix_ues_external_mappings_external_id ON gs_fue_em.gs_fue_em_union_energy_system USING btree (external_id);

CREATE INDEX ix_ues_external_mappings_union_energy_system_ref_uuid ON gs_fue_em.gs_fue_em_union_energy_system USING btree (union_energy_system_ref_uuid);

CREATE UNIQUE INDEX uq_gs_fue_em_business_unit_external_id ON gs_fue_em.gs_fue_em_business_unit USING btree (external_id);

CREATE UNIQUE INDEX uq_gs_fue_em_equipment_group_code ON gs_fue_em.gs_fue_em_equipment_group USING btree (code);

CREATE INDEX ix_gaes_tep_cap_cost_ges_year ON gs_gen.gs_gen_gaes_tep_source_project_indicators USING btree (id_year_capital_cost_wo_pir_ges_with_reservoir);

CREATE INDEX ix_gaes_tep_cap_cost_svm_year ON gs_gen.gs_gen_gaes_tep_source_project_indicators USING btree (id_year_capital_cost_wo_pir_svm);

CREATE INDEX ix_gaes_tep_cap_cost_total_year ON gs_gen.gs_gen_gaes_tep_source_project_indicators USING btree (id_year_capital_cost_wo_pir_total);

CREATE INDEX ix_gaes_tep_source_id_prospective_place_type_gaes ON gs_gen.gs_gen_gaes_tep_source_project_indicators USING btree (id_prospective_place_type_gaes);

CREATE INDEX ix_gaes_tep_source_id_station ON gs_gen.gs_gen_gaes_tep_source_project_indicators USING btree (id_station_prospective_place_gaes);

CREATE INDEX ix_gaes_tep_source_project_indicators_database_version_id ON gs_gen.gs_gen_gaes_tep_source_project_indicators USING btree (database_version_id);

CREATE INDEX ix_gaes_tep_src_id_year_spec_capital ON gs_gen.gs_gen_gaes_tep_source_project_indicators USING btree (id_year_specific_capital_investment);

CREATE INDEX ix_gaes_tep_src_id_year_spec_semifixed ON gs_gen.gs_gen_gaes_tep_source_project_indicators USING btree (id_year_specific_semifixed_operating_costs);

CREATE INDEX ix_generation_boilers_database_version_id ON gs_gen.gs_gen_boilers USING btree (database_version_id);

CREATE INDEX ix_generation_boilers_id_station ON gs_gen.gs_gen_boilers USING btree (id_station);

CREATE INDEX ix_generation_documents_kommod_database_version_id ON gs_gen.gs_gen_documents_kommod USING btree (database_version_id);

CREATE INDEX ix_generation_machine_fuels_database_version_id ON gs_gen.gs_gen_machine_fuels USING btree (database_version_id);

CREATE INDEX ix_generation_machine_fuels_id_fuel ON gs_gen.gs_gen_machine_fuels USING btree (id_fuel);

CREATE INDEX ix_generation_machine_fuels_id_machine ON gs_gen.gs_gen_machine_fuels USING btree (id_machine);

CREATE INDEX ix_generation_machine_fuels_year_number ON gs_gen.gs_gen_machine_fuels USING btree (year_number);

CREATE INDEX ix_generation_machine_powers_database_version_id ON gs_gen.gs_gen_machine_powers USING btree (database_version_id);

CREATE INDEX ix_generation_machine_powers_id_machine ON gs_gen.gs_gen_machine_powers USING btree (id_machine);

CREATE INDEX ix_generation_machine_powers_year_number ON gs_gen.gs_gen_machine_powers USING btree (year_number);

CREATE INDEX ix_generation_machine_tes_types_database_version_id ON gs_gen.gs_gen_machine_tes_types USING btree (database_version_id);

CREATE INDEX ix_generation_machine_tes_types_id_machine ON gs_gen.gs_gen_machine_tes_types USING btree (id_machine);

CREATE INDEX ix_generation_machine_tes_types_id_tes_type ON gs_gen.gs_gen_machine_tes_types USING btree (id_tes_type);

CREATE INDEX ix_generation_machine_tes_types_year_number ON gs_gen.gs_gen_machine_tes_types USING btree (year_number);

CREATE INDEX ix_generation_machines_database_version_id ON gs_gen.gs_gen_machines USING btree (database_version_id);

CREATE INDEX ix_generation_machines_id_condition_type ON gs_gen.gs_gen_machines USING btree (id_condition_type);

CREATE INDEX ix_generation_machines_id_energy_area ON gs_gen.gs_gen_machines USING btree (id_energy_area);

CREATE INDEX ix_generation_machines_id_equipment_group ON gs_gen.gs_gen_machines USING btree (id_equipment_group);

CREATE INDEX ix_generation_machines_id_gen_company ON gs_gen.gs_gen_machines USING btree (id_gen_company);

CREATE INDEX ix_generation_machines_id_machine_type ON gs_gen.gs_gen_machines USING btree (id_machine_type);

CREATE INDEX ix_generation_machines_id_station ON gs_gen.gs_gen_machines USING btree (id_station);

CREATE INDEX ix_generation_machines_id_technology_availability ON gs_gen.gs_gen_machines USING btree (id_technology_availability);

CREATE INDEX ix_generation_machines_id_technology_type ON gs_gen.gs_gen_machines USING btree (id_technology_type);

CREATE INDEX ix_generation_machines_id_tes_machine_type ON gs_gen.gs_gen_machines USING btree (id_tes_machine_type);

CREATE INDEX ix_generation_machines_machine_name ON gs_gen.gs_gen_machines USING btree (machine_name);

CREATE INDEX ix_generation_machines_machine_number ON gs_gen.gs_gen_machines USING btree (machine_number);

CREATE INDEX ix_generation_pgu_machine_powers_database_version_id ON gs_gen.gs_gen_pgu_machine_powers USING btree (database_version_id);

CREATE INDEX ix_generation_pgu_machine_powers_id_pgu_machine ON gs_gen.gs_gen_pgu_machine_powers USING btree (id_pgu_machine);

CREATE INDEX ix_generation_pgu_machine_powers_year_number ON gs_gen.gs_gen_pgu_machine_powers USING btree (year_number);

CREATE INDEX ix_generation_pgu_machines_database_version_id ON gs_gen.gs_gen_pgu_machines USING btree (database_version_id);

CREATE INDEX ix_generation_pgu_machines_id_condition_type ON gs_gen.gs_gen_pgu_machines USING btree (id_condition_type);

CREATE INDEX ix_generation_pgu_machines_id_parent_machine ON gs_gen.gs_gen_pgu_machines USING btree (id_parent_machine);

CREATE INDEX ix_generation_pgu_machines_id_pgu_tes_machine_type ON gs_gen.gs_gen_pgu_machines USING btree (id_pgu_tes_machine_type);

CREATE INDEX ix_generation_pgu_machines_id_tes_machine_type ON gs_gen.gs_gen_pgu_machines USING btree (id_tes_machine_type);

CREATE INDEX ix_generation_pgu_machines_machine_name ON gs_gen.gs_gen_pgu_machines USING btree (machine_name);

CREATE INDEX ix_generation_pgu_machines_machine_number ON gs_gen.gs_gen_pgu_machines USING btree (machine_number);

CREATE INDEX ix_generation_station_groups_database_version_id ON gs_gen.gs_gen_station_groups USING btree (database_version_id);

CREATE INDEX ix_generation_stations_database_version_id ON gs_gen.gs_gen_stations USING btree (database_version_id);

CREATE INDEX ix_generation_stations_id_condition_type ON gs_gen.gs_gen_stations USING btree (id_condition_type);

CREATE INDEX ix_generation_stations_id_energy_unit ON gs_gen.gs_gen_stations USING btree (id_energy_unit);

CREATE INDEX ix_generation_stations_id_regional_district ON gs_gen.gs_gen_stations USING btree (id_regional_district);

CREATE INDEX ix_generation_stations_id_station_group ON gs_gen.gs_gen_stations USING btree (id_station_group);

CREATE INDEX ix_ges_tep_cap_cost_ges_year ON gs_gen.gs_gen_ges_tep_source_project_indicators USING btree (id_year_capital_cost_wo_pir_ges_with_reservoir);

CREATE INDEX ix_ges_tep_cap_cost_svm_year ON gs_gen.gs_gen_ges_tep_source_project_indicators USING btree (id_year_capital_cost_wo_pir_svm);

CREATE INDEX ix_ges_tep_cap_cost_total_year ON gs_gen.gs_gen_ges_tep_source_project_indicators USING btree (id_year_capital_cost_wo_pir_total);

CREATE INDEX ix_ges_tep_source_id_prospective_place_type_ges ON gs_gen.gs_gen_ges_tep_source_project_indicators USING btree (id_prospective_place_type_ges);

CREATE INDEX ix_ges_tep_source_id_station ON gs_gen.gs_gen_ges_tep_source_project_indicators USING btree (id_station_prospective_place_ges);

CREATE INDEX ix_ges_tep_source_project_indicators_database_version_id ON gs_gen.gs_gen_ges_tep_source_project_indicators USING btree (database_version_id);

CREATE INDEX ix_ges_tep_src_id_year_spec_capital ON gs_gen.gs_gen_ges_tep_source_project_indicators USING btree (id_year_specific_capital_investment);

CREATE INDEX ix_ges_tep_src_id_year_spec_semifixed ON gs_gen.gs_gen_ges_tep_source_project_indicators USING btree (id_year_specific_semifixed_operating_costs);

CREATE INDEX ix_gs_gen_machines_is_archived ON gs_gen.gs_gen_machines USING btree (is_archived);

CREATE UNIQUE INDEX ix_gs_prospective_place_types_name ON gs_gen.gs_gen_prospective_place_types USING btree (name);

CREATE INDEX ix_machine_date_decompressing_expected ON gs_gen.gs_gen_machines USING btree (date_decompressing_expected);

CREATE INDEX ix_machine_date_exploitation ON gs_gen.gs_gen_machines USING btree (date_exploitation);

CREATE INDEX ix_machine_date_modernization_no_power_change_expected ON gs_gen.gs_gen_machines USING btree (date_modernization_no_power_change_expected);

CREATE INDEX ix_machine_date_modernization_power_change_expected ON gs_gen.gs_gen_machines USING btree (date_modernization_power_change_expected);

CREATE INDEX ix_machine_external_code ON gs_gen.gs_gen_machines USING btree (external_code);

CREATE INDEX ix_machine_fuel_id_fuel ON gs_gen.gs_gen_machine_fuels USING btree (id_fuel);

CREATE INDEX ix_machine_fuel_id_machine ON gs_gen.gs_gen_machine_fuels USING btree (id_machine);

CREATE INDEX ix_machine_fuel_id_year_number ON gs_gen.gs_gen_machine_fuels USING btree (year_number);

CREATE INDEX ix_machine_fuels_machine_year ON gs_gen.gs_gen_machine_fuels USING btree (id_machine, year_number);

CREATE INDEX ix_machine_id_condition_type ON gs_gen.gs_gen_machines USING btree (id_condition_type);

CREATE INDEX ix_machine_id_energy_area ON gs_gen.gs_gen_machines USING btree (id_energy_area);

CREATE INDEX ix_machine_id_equipment_group ON gs_gen.gs_gen_machines USING btree (id_equipment_group);

CREATE INDEX ix_machine_id_gen_company ON gs_gen.gs_gen_machines USING btree (id_gen_company);

CREATE INDEX ix_machine_id_station ON gs_gen.gs_gen_machines USING btree (id_station);

CREATE INDEX ix_machine_id_tes_machine_type ON gs_gen.gs_gen_machines USING btree (id_tes_machine_type);

CREATE INDEX ix_machine_name_id_machine ON gs_gen.gs_gen_machine_names USING btree (id_machine);

CREATE INDEX ix_machine_name_year_number ON gs_gen.gs_gen_machine_names USING btree (year_number);

CREATE INDEX ix_machine_names_machine_year ON gs_gen.gs_gen_machine_names USING btree (id_machine, year_number);

CREATE INDEX ix_machine_power_id_machine ON gs_gen.gs_gen_machine_powers USING btree (id_machine);

CREATE INDEX ix_machine_power_year_number ON gs_gen.gs_gen_machine_powers USING btree (year_number);

CREATE INDEX ix_machine_powers_station_year ON gs_gen.gs_gen_machine_powers USING btree (id_machine, year_number);

CREATE INDEX ix_machine_prospective_place_aes_id_prospective_place_type ON gs_gen.gs_gen_machine_prospective_place_aes USING btree (id_prospective_place_type);

CREATE INDEX ix_machine_prospective_place_aes_id_station_prospective_place ON gs_gen.gs_gen_machine_prospective_place_aes USING btree (id_station_prospective_place_aes);

CREATE INDEX ix_machine_tes_type_id_machine ON gs_gen.gs_gen_machine_tes_types USING btree (id_machine);

CREATE INDEX ix_machine_tes_type_id_tes_type ON gs_gen.gs_gen_machine_tes_types USING btree (id_tes_type);

CREATE INDEX ix_machine_tes_type_year_number ON gs_gen.gs_gen_machine_tes_types USING btree (year_number);

CREATE INDEX ix_mpp_aes_id_year_spec_cap ON gs_gen.gs_gen_machine_prospective_place_aes USING btree (id_year_specific_capital_investment);

CREATE INDEX ix_mpp_aes_id_year_spec_decom ON gs_gen.gs_gen_machine_prospective_place_aes USING btree (id_year_specific_decommissioning);

CREATE INDEX ix_mpp_aes_id_year_spec_fixed_op ON gs_gen.gs_gen_machine_prospective_place_aes USING btree (id_year_specific_fixed_operating_costs);

CREATE INDEX ix_mpp_aes_id_year_spec_fuel ON gs_gen.gs_gen_machine_prospective_place_aes USING btree (id_year_specific_fuel_cost);

CREATE INDEX ix_pgu_machine_id_condition_type ON gs_gen.gs_gen_pgu_machines USING btree (id_condition_type);

CREATE INDEX ix_pgu_machine_id_parent_machine ON gs_gen.gs_gen_pgu_machines USING btree (id_parent_machine);

CREATE INDEX ix_pgu_machine_id_tes_machine_type ON gs_gen.gs_gen_pgu_machines USING btree (id_tes_machine_type);

CREATE INDEX ix_pgu_machine_name_id_pgu_machine ON gs_gen.gs_gen_pgu_machine_names USING btree (id_pgu_machine);

CREATE INDEX ix_pgu_machine_name_year_number ON gs_gen.gs_gen_pgu_machine_names USING btree (year_number);

CREATE INDEX ix_pgu_machine_names_pgu_machine_year ON gs_gen.gs_gen_pgu_machine_names USING btree (id_pgu_machine, year_number);

CREATE INDEX ix_pgu_machine_power_id_pgu_machine ON gs_gen.gs_gen_pgu_machine_powers USING btree (id_pgu_machine);

CREATE INDEX ix_pgu_machine_power_year_number ON gs_gen.gs_gen_pgu_machine_powers USING btree (year_number);

CREATE INDEX ix_pp_hydro_forecast_database_version_id ON gs_gen.gs_gen_prospective_place_hydro_energy_forecasts USING btree (database_version_id);

CREATE INDEX ix_pp_hydro_forecast_month ON gs_gen.gs_gen_prospective_place_hydro_energy_forecasts USING btree (month_number);

CREATE INDEX ix_pp_hydro_forecast_place ON gs_gen.gs_gen_prospective_place_hydro_energy_forecasts USING btree (place_kind, place_id);

CREATE INDEX ix_pp_hydro_forecast_scenario ON gs_gen.gs_gen_prospective_place_hydro_energy_forecasts USING btree (scenario);

CREATE INDEX ix_station_external_code ON gs_gen.gs_gen_stations USING btree (external_code);

CREATE INDEX ix_station_gaes_charge_id_station ON gs_gen.gs_gen_station_gaes_charge_consumptions USING btree (id_station);

CREATE INDEX ix_station_gaes_charge_station_year ON gs_gen.gs_gen_station_gaes_charge_consumptions USING btree (id_station, year_number);

CREATE INDEX ix_station_gaes_charge_year_number ON gs_gen.gs_gen_station_gaes_charge_consumptions USING btree (year_number);

CREATE INDEX ix_station_id_regional_district ON gs_gen.gs_gen_stations USING btree (id_regional_district);

CREATE INDEX ix_station_id_station_group ON gs_gen.gs_gen_stations USING btree (id_station_group);

CREATE INDEX ix_station_id_station_type ON gs_gen.gs_gen_stations USING btree (id_station_type);

CREATE INDEX ix_station_name ON gs_gen.gs_gen_stations USING btree (name);

CREATE INDEX ix_station_owner_energy_gen_id_station ON gs_gen.gs_gen_station_owner_energy_generations USING btree (id_station);

CREATE INDEX ix_station_owner_energy_gen_station_year ON gs_gen.gs_gen_station_owner_energy_generations USING btree (id_station, year_number);

CREATE INDEX ix_station_owner_energy_gen_year_number ON gs_gen.gs_gen_station_owner_energy_generations USING btree (year_number);

CREATE INDEX ix_station_pp_gaes_id_place_type_gaes ON gs_gen.gs_gen_station_prospective_place_gaes USING btree (id_prospective_place_type_gaes);

CREATE INDEX ix_station_prospective_place_aes_external_code ON gs_gen.gs_gen_station_prospective_place_aes USING btree (external_code);

CREATE INDEX ix_station_prospective_place_aes_id_regional_district ON gs_gen.gs_gen_station_prospective_place_aes USING btree (id_regional_district);

CREATE INDEX ix_station_prospective_place_aes_id_regional_energy_system ON gs_gen.gs_gen_station_prospective_place_aes USING btree (id_regional_energy_system);

CREATE INDEX ix_station_prospective_place_aes_site_name ON gs_gen.gs_gen_station_prospective_place_aes USING btree (site_name);

CREATE INDEX ix_station_prospective_place_gaes_database_version_id ON gs_gen.gs_gen_station_prospective_place_gaes USING btree (database_version_id);

CREATE INDEX ix_station_prospective_place_gaes_external_code ON gs_gen.gs_gen_station_prospective_place_gaes USING btree (external_code);

CREATE INDEX ix_station_prospective_place_gaes_id_regional_district ON gs_gen.gs_gen_station_prospective_place_gaes USING btree (id_regional_district);

CREATE INDEX ix_station_prospective_place_gaes_id_regional_energy_system ON gs_gen.gs_gen_station_prospective_place_gaes USING btree (id_regional_energy_system);

CREATE INDEX ix_station_prospective_place_gaes_site_name ON gs_gen.gs_gen_station_prospective_place_gaes USING btree (site_name);

CREATE INDEX ix_station_prospective_place_ges_database_version_id ON gs_gen.gs_gen_station_prospective_place_ges USING btree (database_version_id);

CREATE INDEX ix_station_prospective_place_ges_external_code ON gs_gen.gs_gen_station_prospective_place_ges USING btree (external_code);

CREATE INDEX ix_station_prospective_place_ges_id_prospective_place_type_ges ON gs_gen.gs_gen_station_prospective_place_ges USING btree (id_prospective_place_type_ges);

CREATE INDEX ix_station_prospective_place_ges_id_regional_district ON gs_gen.gs_gen_station_prospective_place_ges USING btree (id_regional_district);

CREATE INDEX ix_station_prospective_place_ges_id_regional_energy_system ON gs_gen.gs_gen_station_prospective_place_ges USING btree (id_regional_energy_system);

CREATE INDEX ix_station_prospective_place_ges_site_name ON gs_gen.gs_gen_station_prospective_place_ges USING btree (site_name);

CREATE INDEX ix_station_snee_efficiency_database_version_id ON gs_gen.gs_gen_station_snee_efficiencies USING btree (database_version_id);

CREATE INDEX ix_station_snee_efficiency_id_station ON gs_gen.gs_gen_station_snee_efficiencies USING btree (id_station);

CREATE INDEX ix_station_snee_energy_consumption_id_station ON gs_gen.gs_gen_station_snee_energy_consumptions USING btree (id_station);

CREATE INDEX ix_station_snee_energy_consumption_station_year ON gs_gen.gs_gen_station_snee_energy_consumptions USING btree (id_station, year_number);

CREATE INDEX ix_station_snee_energy_consumption_year_number ON gs_gen.gs_gen_station_snee_energy_consumptions USING btree (year_number);

CREATE INDEX ix_stations_id_regional_energy_system ON gs_gen.gs_gen_stations USING btree (id_regional_energy_system);

CREATE INDEX ix_tep_price_conv_coeff_database_version_id ON gs_gen.gs_gen_tep_price_conversion_coefficients USING btree (database_version_id);

CREATE INDEX ix_tep_price_conv_coeff_id_year ON gs_gen.gs_gen_tep_price_conversion_coefficients USING btree (id_year);

CREATE UNIQUE INDEX uq_machine_names_machine_year_ver ON gs_gen.gs_gen_machine_names USING btree (id_machine, year_number, COALESCE(database_version_id, '-1'::integer));

CREATE UNIQUE INDEX uq_pgu_machine_names_machine_year_ver ON gs_gen.gs_gen_pgu_machine_names USING btree (id_pgu_machine, year_number, COALESCE(database_version_id, '-1'::integer));

CREATE UNIQUE INDEX uq_pgu_machine_powers_machine_year_ver ON gs_gen.gs_gen_pgu_machine_powers USING btree (id_pgu_machine, year_number, COALESCE(database_version_id, '-1'::integer));

CREATE UNIQUE INDEX uq_pp_hydro_forecast_place_scenario_month_ver ON gs_gen.gs_gen_prospective_place_hydro_energy_forecasts USING btree (place_kind, place_id, scenario, month_number, COALESCE(database_version_id, '-1'::integer));

CREATE UNIQUE INDEX uq_station_gaes_charge_station_year_ver ON gs_gen.gs_gen_station_gaes_charge_consumptions USING btree (id_station, year_number, COALESCE(database_version_id, '-1'::integer));

CREATE UNIQUE INDEX uq_station_owner_energy_gen_station_year_ver ON gs_gen.gs_gen_station_owner_energy_generations USING btree (id_station, year_number, COALESCE(database_version_id, '-1'::integer));

CREATE UNIQUE INDEX uq_station_snee_efficiency_station_ver ON gs_gen.gs_gen_station_snee_efficiencies USING btree (id_station, COALESCE(database_version_id, '-1'::integer));

CREATE UNIQUE INDEX uq_station_snee_energy_consumption_station_year_ver ON gs_gen.gs_gen_station_snee_energy_consumptions USING btree (id_station, year_number, COALESCE(database_version_id, '-1'::integer));

CREATE INDEX ix_gs_logs_logs_module ON gs_logs.logs USING btree (module);

CREATE INDEX ix_logs_logs_action ON gs_logs.logs USING btree (action);

CREATE INDEX ix_logs_logs_database_version_id ON gs_logs.logs USING btree (database_version_id);

CREATE INDEX ix_logs_logs_entity_id ON gs_logs.logs USING btree (entity_id);

CREATE INDEX ix_logs_logs_entity_type ON gs_logs.logs USING btree (entity_type);

CREATE INDEX ix_logs_logs_timestamp ON gs_logs.logs USING btree ("timestamp");

CREATE INDEX ix_logs_logs_username ON gs_logs.logs USING btree (username);

CREATE INDEX ix_gs_centralized_zone_dp_dbver ON gs_pd.gs_pd_centralized_zone_demand_params USING btree (database_version_id);

CREATE INDEX ix_gs_centralized_zone_dp_year ON gs_pd.gs_pd_centralized_zone_demand_params USING btree (year_number);

CREATE INDEX ix_gs_ees_dp_dbver ON gs_pd.gs_pd_ees_demand_params USING btree (database_version_id);

CREATE INDEX ix_gs_ees_dp_year ON gs_pd.gs_pd_ees_demand_params USING btree (year_number);

CREATE INDEX ix_gs_ees_ru_dp_dbver ON gs_pd.gs_pd_ees_russia_demand_params USING btree (database_version_id);

CREATE INDEX ix_gs_ees_ru_dp_year ON gs_pd.gs_pd_ees_russia_demand_params USING btree (year_number);

CREATE INDEX ix_gs_energy_area_demand_params_database_version_id ON gs_pd.gs_pd_energy_area_demand_params USING btree (database_version_id);

CREATE INDEX ix_gs_energy_area_demand_params_id_energy_area ON gs_pd.gs_pd_energy_area_demand_params USING btree (id_energy_area);

CREATE INDEX ix_gs_energy_area_demand_params_year_number ON gs_pd.gs_pd_energy_area_demand_params USING btree (year_number);

CREATE INDEX ix_gs_energy_system_type_demand_params_database_version_id ON gs_pd.gs_pd_energy_system_type_demand_params USING btree (database_version_id);

CREATE INDEX ix_gs_energy_system_type_demand_params_id_energy_system_type ON gs_pd.gs_pd_energy_system_type_demand_params USING btree (id_energy_system_type);

CREATE INDEX ix_gs_energy_system_type_demand_params_year_number ON gs_pd.gs_pd_energy_system_type_demand_params USING btree (year_number);

CREATE INDEX ix_gs_energy_unit_demand_params_database_version_id ON gs_pd.gs_pd_energy_unit_demand_params USING btree (database_version_id);

CREATE INDEX ix_gs_energy_unit_demand_params_id_energy_unit ON gs_pd.gs_pd_energy_unit_demand_params USING btree (id_energy_unit);

CREATE INDEX ix_gs_energy_unit_demand_params_year_number ON gs_pd.gs_pd_energy_unit_demand_params USING btree (year_number);

CREATE INDEX ix_gs_energy_zone_demand_params_database_version_id ON gs_pd.gs_pd_energy_zone_demand_params USING btree (database_version_id);

CREATE INDEX ix_gs_energy_zone_demand_params_id_energy_zone ON gs_pd.gs_pd_energy_zone_demand_params USING btree (id_energy_zone);

CREATE INDEX ix_gs_energy_zone_demand_params_year_number ON gs_pd.gs_pd_energy_zone_demand_params USING btree (year_number);

CREATE INDEX ix_gs_federal_district_demand_params_database_version_id ON gs_pd.gs_pd_federal_district_demand_params USING btree (database_version_id);

CREATE INDEX ix_gs_federal_district_demand_params_id_federal_district ON gs_pd.gs_pd_federal_district_demand_params USING btree (id_federal_district);

CREATE INDEX ix_gs_federal_district_demand_params_year_number ON gs_pd.gs_pd_federal_district_demand_params USING btree (year_number);

CREATE INDEX ix_gs_pd_centralized_zone_demand_params_pvc ON gs_pd.gs_pd_centralized_zone_demand_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_pd_ees_demand_params_pvc ON gs_pd.gs_pd_ees_demand_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_pd_ees_russia_demand_params_pvc ON gs_pd.gs_pd_ees_russia_demand_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_pd_energy_system_type_demand_params_pvc ON gs_pd.gs_pd_energy_system_type_demand_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_pd_energy_unit_demand_params_perimeter_variant_code ON gs_pd.gs_pd_energy_unit_demand_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_pd_energy_zone_demand_params_perimeter_variant_code ON gs_pd.gs_pd_energy_zone_demand_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_pd_federal_district_demand_params_pvc ON gs_pd.gs_pd_federal_district_demand_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_pd_ozp_max_power_params_database_version_id ON gs_pd.gs_pd_ozp_max_power_params USING btree (database_version_id);

CREATE INDEX ix_gs_pd_ozp_max_power_params_ozp_end_year ON gs_pd.gs_pd_ozp_max_power_params USING btree (ozp_end_year);

CREATE INDEX ix_gs_pd_regional_district_demand_params_pvc ON gs_pd.gs_pd_regional_district_demand_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_pd_regional_energy_system_demand_params_pvc ON gs_pd.gs_pd_regional_energy_system_demand_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_pd_russia_federation_demand_params_pvc ON gs_pd.gs_pd_russia_federation_demand_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_pd_summary_formula_texts_formula_key ON gs_pd.gs_pd_summary_formula_texts USING btree (formula_key);

CREATE INDEX ix_gs_pd_synchronous_area_demand_params_pvc ON gs_pd.gs_pd_synchronous_area_demand_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_pd_ues_demand_params_perimeter_variant_code ON gs_pd.gs_pd_union_energy_system_demand_params USING btree (perimeter_variant_code);

CREATE INDEX ix_gs_regional_district_demand_params_database_version_id ON gs_pd.gs_pd_regional_district_demand_params USING btree (database_version_id);

CREATE INDEX ix_gs_regional_district_demand_params_id_regional_district ON gs_pd.gs_pd_regional_district_demand_params USING btree (id_regional_district);

CREATE INDEX ix_gs_regional_district_demand_params_year_number ON gs_pd.gs_pd_regional_district_demand_params USING btree (year_number);

CREATE INDEX ix_gs_res_dparam_dbver ON gs_pd.gs_pd_regional_energy_system_demand_params USING btree (database_version_id);

CREATE INDEX ix_gs_res_dparam_id_res ON gs_pd.gs_pd_regional_energy_system_demand_params USING btree (id_regional_energy_system);

CREATE INDEX ix_gs_res_dparam_year ON gs_pd.gs_pd_regional_energy_system_demand_params USING btree (year_number);

CREATE INDEX ix_gs_russia_federation_demand_params_database_version_id ON gs_pd.gs_pd_russia_federation_demand_params USING btree (database_version_id);

CREATE INDEX ix_gs_russia_federation_demand_params_year_number ON gs_pd.gs_pd_russia_federation_demand_params USING btree (year_number);

CREATE INDEX ix_gs_synchronous_area_demand_params_database_version_id ON gs_pd.gs_pd_synchronous_area_demand_params USING btree (database_version_id);

CREATE INDEX ix_gs_synchronous_area_demand_params_id_synchronous_area ON gs_pd.gs_pd_synchronous_area_demand_params USING btree (id_synchronous_area);

CREATE INDEX ix_gs_synchronous_area_demand_params_year_number ON gs_pd.gs_pd_synchronous_area_demand_params USING btree (year_number);

CREATE INDEX ix_gs_union_energy_system_demand_params_database_version_id ON gs_pd.gs_pd_union_energy_system_demand_params USING btree (database_version_id);

CREATE INDEX ix_gs_union_energy_system_demand_params_id_union_energy_system ON gs_pd.gs_pd_union_energy_system_demand_params USING btree (id_union_energy_system);

CREATE INDEX ix_gs_union_energy_system_demand_params_year_number ON gs_pd.gs_pd_union_energy_system_demand_params USING btree (year_number);

CREATE UNIQUE INDEX uq_ea_demand_params_hist ON gs_pd.gs_pd_energy_area_demand_params USING btree (id_energy_area, COALESCE(database_version_id, 0)) WHERE (is_historical_maximum = true);

CREATE UNIQUE INDEX uq_ea_demand_params_year ON gs_pd.gs_pd_energy_area_demand_params USING btree (id_energy_area, year_number, COALESCE(database_version_id, 0)) WHERE (is_historical_maximum = false);

CREATE UNIQUE INDEX uq_eu_demand_params_hist ON gs_pd.gs_pd_energy_unit_demand_params USING btree (id_energy_unit, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = true);

CREATE UNIQUE INDEX uq_eu_demand_params_year ON gs_pd.gs_pd_energy_unit_demand_params USING btree (id_energy_unit, year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = false);

CREATE UNIQUE INDEX uq_ez_demand_params_hist ON gs_pd.gs_pd_energy_zone_demand_params USING btree (id_energy_zone, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = true);

CREATE UNIQUE INDEX uq_ez_demand_params_year ON gs_pd.gs_pd_energy_zone_demand_params USING btree (id_energy_zone, year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = false);

CREATE UNIQUE INDEX uq_gs_pd_centralized_zone_demand_params_hist ON gs_pd.gs_pd_centralized_zone_demand_params USING btree (COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = true);

CREATE UNIQUE INDEX uq_gs_pd_centralized_zone_demand_params_year ON gs_pd.gs_pd_centralized_zone_demand_params USING btree (year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = false);

CREATE UNIQUE INDEX uq_gs_pd_ees_demand_params_hist ON gs_pd.gs_pd_ees_demand_params USING btree (COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = true);

CREATE UNIQUE INDEX uq_gs_pd_ees_demand_params_year ON gs_pd.gs_pd_ees_demand_params USING btree (year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = false);

CREATE UNIQUE INDEX uq_gs_pd_ees_russia_demand_params_hist ON gs_pd.gs_pd_ees_russia_demand_params USING btree (COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = true);

CREATE UNIQUE INDEX uq_gs_pd_ees_russia_demand_params_year ON gs_pd.gs_pd_ees_russia_demand_params USING btree (year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = false);

CREATE UNIQUE INDEX uq_gs_pd_energy_system_type_demand_params_hist ON gs_pd.gs_pd_energy_system_type_demand_params USING btree (id_energy_system_type, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = true);

CREATE UNIQUE INDEX uq_gs_pd_energy_system_type_demand_params_year ON gs_pd.gs_pd_energy_system_type_demand_params USING btree (id_energy_system_type, year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = false);

CREATE UNIQUE INDEX uq_gs_pd_federal_district_demand_params_hist ON gs_pd.gs_pd_federal_district_demand_params USING btree (id_federal_district, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = true);

CREATE UNIQUE INDEX uq_gs_pd_federal_district_demand_params_year ON gs_pd.gs_pd_federal_district_demand_params USING btree (id_federal_district, year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = false);

CREATE UNIQUE INDEX uq_gs_pd_ozp_max_power_params_version_ozp ON gs_pd.gs_pd_ozp_max_power_params USING btree (ozp_end_year, COALESCE(database_version_id, 0));

CREATE UNIQUE INDEX uq_gs_pd_regional_energy_system_demand_params_hist ON gs_pd.gs_pd_regional_energy_system_demand_params USING btree (id_regional_energy_system, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = true);

CREATE UNIQUE INDEX uq_gs_pd_regional_energy_system_demand_params_year ON gs_pd.gs_pd_regional_energy_system_demand_params USING btree (id_regional_energy_system, year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = false);

CREATE UNIQUE INDEX uq_gs_pd_russia_federation_demand_params_hist ON gs_pd.gs_pd_russia_federation_demand_params USING btree (COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = true);

CREATE UNIQUE INDEX uq_gs_pd_russia_federation_demand_params_year ON gs_pd.gs_pd_russia_federation_demand_params USING btree (year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = false);

CREATE UNIQUE INDEX uq_gs_pd_synchronous_area_demand_params_hist ON gs_pd.gs_pd_synchronous_area_demand_params USING btree (id_synchronous_area, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = true);

CREATE UNIQUE INDEX uq_gs_pd_synchronous_area_demand_params_year ON gs_pd.gs_pd_synchronous_area_demand_params USING btree (id_synchronous_area, year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = false);

CREATE UNIQUE INDEX uq_gs_pd_union_energy_system_demand_params_hist ON gs_pd.gs_pd_union_energy_system_demand_params USING btree (id_union_energy_system, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = true);

CREATE UNIQUE INDEX uq_gs_pd_union_energy_system_demand_params_year ON gs_pd.gs_pd_union_energy_system_demand_params USING btree (id_union_energy_system, year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = false);

CREATE UNIQUE INDEX uq_rd_demand_params_hist ON gs_pd.gs_pd_regional_district_demand_params USING btree (id_regional_district, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = true);

CREATE UNIQUE INDEX uq_rd_demand_params_year ON gs_pd.gs_pd_regional_district_demand_params USING btree (id_regional_district, year_number, COALESCE(database_version_id, 0), COALESCE(perimeter_variant_code, ''::character varying)) WHERE (is_historical_maximum = false);

CREATE INDEX ix_gs_rs_gs_rs_calculation_workbooks_database_version_id ON gs_rs.gs_rs_calculation_workbooks USING btree (database_version_id);

CREATE INDEX ix_gs_rs_gs_rs_territory_technologies_database_version_id ON gs_rs.gs_rs_territory_technologies USING btree (database_version_id);

CREATE INDEX ix_gs_rs_gs_rs_territory_technologies_energy_zone_id ON gs_rs.gs_rs_territory_technologies USING btree (energy_zone_id);

CREATE INDEX ix_gs_rs_gs_rs_territory_transfer_sections_database_version_id ON gs_rs.gs_rs_territory_transfer_sections USING btree (database_version_id);

CREATE INDEX ix_rs_equipment_version_machine ON gs_rs.gs_rs_equipment_technical_characteristics USING btree (database_version_id, machine_id);

CREATE INDEX ix_rs_equipment_version_pgu_machine ON gs_rs.gs_rs_equipment_technical_characteristics USING btree (database_version_id, pgu_machine_id);

CREATE INDEX ix_rs_equipment_version_year_type ON gs_rs.gs_rs_equipment_technical_characteristics USING btree (database_version_id, report_year, equipment_type);

CREATE INDEX ix_rs_inspection_codes_machine_id ON gs_rs.gs_rs_technical_inspection_codes USING btree (machine_id);

CREATE INDEX ix_rs_inspection_codes_pgu_machine_id ON gs_rs.gs_rs_technical_inspection_codes USING btree (pgu_machine_id);

CREATE INDEX ix_generation_database_versions_is_active ON gs_sys.gs_sys_database_versions USING btree (is_active);

CREATE INDEX ix_generation_database_versions_parent_version_id ON gs_sys.gs_sys_database_versions USING btree (parent_version_id);

CREATE UNIQUE INDEX ix_generation_database_versions_version_number ON gs_sys.gs_sys_database_versions USING btree (version_number);

CREATE INDEX ix_gs_companies_ref_uuid ON gs_sys.gs_sys_companies USING btree (ref_uuid);

CREATE INDEX ix_gs_condition_types_ref_uuid ON gs_sys.gs_sys_condition_types USING btree (ref_uuid);

CREATE INDEX ix_gs_energy_areas_ref_uuid ON gs_sys.gs_sys_energy_areas USING btree (ref_uuid);

CREATE INDEX ix_gs_energy_system_types_ref_uuid ON gs_sys.gs_sys_energy_system_types USING btree (ref_uuid);

CREATE INDEX ix_gs_energy_units_ref_uuid ON gs_sys.gs_sys_energy_units USING btree (ref_uuid);

CREATE INDEX ix_gs_energy_zones_ref_uuid ON gs_sys.gs_sys_energy_zones USING btree (ref_uuid);

CREATE INDEX ix_gs_equipment_groups_ref_uuid ON gs_sys.gs_sys_equipment_groups USING btree (ref_uuid);

CREATE INDEX ix_gs_federal_districts_ref_uuid ON gs_sys.gs_sys_federal_districts USING btree (ref_uuid);

CREATE INDEX ix_gs_fuel_types_ref_uuid ON gs_sys.gs_sys_fuel_types USING btree (ref_uuid);

CREATE INDEX ix_gs_fuels_ref_uuid ON gs_sys.gs_sys_fuels USING btree (ref_uuid);

CREATE INDEX ix_gs_machine_types_ref_uuid ON gs_sys.gs_sys_machine_types USING btree (ref_uuid);

CREATE INDEX ix_gs_pgu_tes_machine_types_ref_uuid ON gs_sys.gs_sys_pgu_tes_machine_types USING btree (ref_uuid);

CREATE INDEX ix_gs_refdata_entities_database_version_id ON gs_sys.gs_sys_refdata_entities USING btree (database_version_id);

CREATE INDEX ix_gs_refdata_entities_entity_id ON gs_sys.gs_sys_refdata_entities USING btree (entity_id);

CREATE INDEX ix_gs_refdata_entities_entity_type ON gs_sys.gs_sys_refdata_entities USING btree (entity_type);

CREATE INDEX ix_gs_refdata_entities_ref_uuid ON gs_sys.gs_sys_refdata_entities USING btree (ref_uuid);

CREATE INDEX ix_gs_refdata_entity_years_database_version_id ON gs_sys.gs_sys_refdata_entity_years USING btree (database_version_id);

CREATE INDEX ix_gs_refdata_entity_years_refdata_entity_id ON gs_sys.gs_sys_refdata_entity_years USING btree (refdata_entity_id);

CREATE INDEX ix_gs_refdata_entity_years_year ON gs_sys.gs_sys_refdata_entity_years USING btree (year);

CREATE INDEX ix_gs_regional_districts_ref_uuid ON gs_sys.gs_sys_regional_districts USING btree (ref_uuid);

CREATE INDEX ix_gs_regional_energy_systems_ref_uuid ON gs_sys.gs_sys_regional_energy_systems USING btree (ref_uuid);

CREATE INDEX ix_gs_station_types_ref_uuid ON gs_sys.gs_sys_station_types USING btree (ref_uuid);

CREATE INDEX ix_gs_synchronous_areas_ref_uuid ON gs_sys.gs_sys_synchronous_areas USING btree (ref_uuid);

CREATE INDEX ix_gs_sys_economic_activity_types_database_version_id ON gs_sys.gs_sys_economic_activity_types USING btree (database_version_id);

CREATE INDEX ix_gs_sys_economic_activity_types_name ON gs_sys.gs_sys_economic_activity_types USING btree (name);

CREATE INDEX ix_gs_sys_economic_activity_types_ref_uuid ON gs_sys.gs_sys_economic_activity_types USING btree (ref_uuid);

CREATE INDEX ix_gs_sys_electricity_production_cost_types_database_version_id ON gs_sys.gs_sys_electricity_production_cost_types USING btree (database_version_id);

CREATE INDEX ix_gs_sys_electricity_production_cost_types_name ON gs_sys.gs_sys_electricity_production_cost_types USING btree (name);

CREATE INDEX ix_gs_sys_electricity_production_cost_types_ref_uuid ON gs_sys.gs_sys_electricity_production_cost_types USING btree (ref_uuid);

CREATE INDEX ix_gs_sys_foreign_border_countries_database_version_id ON gs_sys.gs_sys_foreign_border_countries USING btree (database_version_id);

CREATE INDEX ix_gs_sys_foreign_border_countries_name ON gs_sys.gs_sys_foreign_border_countries USING btree (name);

CREATE INDEX ix_gs_sys_foreign_border_countries_ref_uuid ON gs_sys.gs_sys_foreign_border_countries USING btree (ref_uuid);

CREATE INDEX ix_gs_sys_fuels_kod ON gs_sys.gs_sys_fuels USING btree (kod);

CREATE INDEX ix_gs_sys_fuels_parent_id ON gs_sys.gs_sys_fuels USING btree (parent_id);

CREATE INDEX ix_gs_sys_gs_year_service_database_version_id ON gs_sys.gs_sys_year_service USING btree (database_version_id);

CREATE INDEX ix_gs_sys_perimeter_variants_code ON gs_sys.gs_sys_perimeter_variants USING btree (code);

CREATE INDEX ix_gs_sys_synchronous_areas_name_full ON gs_sys.gs_sys_synchronous_areas USING btree (name_full);

CREATE INDEX ix_gs_technology_availabilities_ref_uuid ON gs_sys.gs_sys_technology_availabilities USING btree (ref_uuid);

CREATE INDEX ix_gs_technology_types_ref_uuid ON gs_sys.gs_sys_technology_types USING btree (ref_uuid);

CREATE INDEX ix_gs_tes_machine_types_ref_uuid ON gs_sys.gs_sys_tes_machine_types USING btree (ref_uuid);

CREATE INDEX ix_gs_tes_types_ref_uuid ON gs_sys.gs_sys_tes_types USING btree (ref_uuid);

CREATE INDEX ix_gs_union_energy_systems_ref_uuid ON gs_sys.gs_sys_union_energy_systems USING btree (ref_uuid);

CREATE INDEX ix_refdata_gs_companies_name_short ON gs_sys.gs_sys_companies USING btree (name_short);

CREATE UNIQUE INDEX ix_refdata_year_features_name_database_version_id ON gs_sys.gs_sys_year_features USING btree (name, database_version_id);

CREATE INDEX ix_refdata_years_database_version_id ON gs_sys.gs_sys_years USING btree (database_version_id);

CREATE UNIQUE INDEX ix_refdata_years_number_database_version_id ON gs_sys.gs_sys_years USING btree (number, database_version_id);

CREATE INDEX ix_tep_price_conv_coeff_database_version_id ON gs_sys.gs_sys_tep_price_conversion_coefficients USING btree (database_version_id);

CREATE INDEX ix_tep_price_conv_coeff_id_year ON gs_sys.gs_sys_tep_price_conversion_coefficients USING btree (id_year);

CREATE INDEX ix_gs_ter_eu_pt_dbver ON gs_ter.gs_ter_energy_unit_power_transfers USING btree (database_version_id);

CREATE INDEX ix_gs_ter_eu_pt_energy_unit ON gs_ter.gs_ter_energy_unit_power_transfers USING btree (id_energy_unit);

CREATE INDEX ix_gs_ter_eu_pt_regional_district ON gs_ter.gs_ter_energy_unit_power_transfers USING btree (id_regional_district);

CREATE INDEX ix_gs_ter_eu_pt_val_dbver ON gs_ter.gs_ter_energy_unit_power_transfer_values USING btree (database_version_id);

CREATE INDEX ix_gs_ter_eu_pt_val_transfer ON gs_ter.gs_ter_energy_unit_power_transfer_values USING btree (id_energy_unit_power_transfer);

CREATE INDEX ix_gs_ter_eu_pt_val_year ON gs_ter.gs_ter_energy_unit_power_transfer_values USING btree (year_number);

ALTER TABLE ONLY gs_auth.users
    ADD CONSTRAINT fk_users_last_database_version_id FOREIGN KEY (last_database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_auth.user_roles
    ADD CONSTRAINT user_roles_role_id_fkey FOREIGN KEY (role_id) REFERENCES gs_auth.roles(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_auth.user_roles
    ADD CONSTRAINT user_roles_user_id_fkey FOREIGN KEY (user_id) REFERENCES gs_auth.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_auth.users
    ADD CONSTRAINT users_last_database_version_id_fkey FOREIGN KEY (last_database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_bem.gs_bem_ee_balance_station_own_needs_coefficients
    ADD CONSTRAINT fk_ee_bal_own_needs_db_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_bem.gs_bem_ee_balance_station_own_needs_coefficients
    ADD CONSTRAINT fk_ee_bal_own_needs_station FOREIGN KEY (id_station) REFERENCES gs_gen.gs_gen_stations(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_ee_exports
    ADD CONSTRAINT fk_ee_export_db_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_ee_exports
    ADD CONSTRAINT fk_ee_export_from_rd FOREIGN KEY (id_from_regional_district) REFERENCES gs_sys.gs_sys_regional_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_ee_exports
    ADD CONSTRAINT fk_ee_export_from_res FOREIGN KEY (id_from_regional_energy_system) REFERENCES gs_sys.gs_sys_regional_energy_systems(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_ee_exports
    ADD CONSTRAINT fk_ee_export_to_country FOREIGN KEY (id_to_foreign_border_country) REFERENCES gs_sys.gs_sys_foreign_border_countries(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_ee_exports
    ADD CONSTRAINT fk_ee_export_to_eu FOREIGN KEY (id_to_energy_unit) REFERENCES gs_sys.gs_sys_energy_units(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_ee_exports
    ADD CONSTRAINT fk_ee_export_to_rd FOREIGN KEY (id_to_regional_district) REFERENCES gs_sys.gs_sys_regional_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_ee_exports
    ADD CONSTRAINT fk_ee_export_to_res FOREIGN KEY (id_to_regional_energy_system) REFERENCES gs_sys.gs_sys_regional_energy_systems(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_ee_exports
    ADD CONSTRAINT fk_ee_export_ues FOREIGN KEY (id_union_energy_system) REFERENCES gs_sys.gs_sys_union_energy_systems(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_ee_exports
    ADD CONSTRAINT fk_ee_export_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_ee_import_export_oes_values
    ADD CONSTRAINT fk_ee_import_export_oes_country FOREIGN KEY (id_foreign_border_country) REFERENCES gs_sys.gs_sys_foreign_border_countries(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_ee_import_export_oes_values
    ADD CONSTRAINT fk_ee_import_export_oes_db_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_bem.gs_bem_ee_import_export_oes_values
    ADD CONSTRAINT fk_ee_import_export_oes_ues FOREIGN KEY (id_union_energy_system) REFERENCES gs_sys.gs_sys_union_energy_systems(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_ee_import_export_oes_values
    ADD CONSTRAINT fk_ee_import_export_oes_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_ee_receive_transfer_oes_values
    ADD CONSTRAINT fk_ee_receive_transfer_oes_db_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_bem.gs_bem_ee_receive_transfer_oes_values
    ADD CONSTRAINT fk_ee_receive_transfer_oes_source FOREIGN KEY (id_source_union_energy_system) REFERENCES gs_sys.gs_sys_union_energy_systems(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_ee_receive_transfer_oes_values
    ADD CONSTRAINT fk_ee_receive_transfer_oes_target FOREIGN KEY (id_target_union_energy_system) REFERENCES gs_sys.gs_sys_union_energy_systems(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_ee_receive_transfer_oes_values
    ADD CONSTRAINT fk_ee_receive_transfer_oes_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_transfers
    ADD CONSTRAINT fk_ee_transfer_db_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_transfers
    ADD CONSTRAINT fk_ee_transfer_from_rd FOREIGN KEY (id_from_regional_district) REFERENCES gs_sys.gs_sys_regional_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_transfers
    ADD CONSTRAINT fk_ee_transfer_from_res FOREIGN KEY (id_from_regional_energy_system) REFERENCES gs_sys.gs_sys_regional_energy_systems(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_transfers
    ADD CONSTRAINT fk_ee_transfer_to_country FOREIGN KEY (id_to_foreign_border_country) REFERENCES gs_sys.gs_sys_foreign_border_countries(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_transfers
    ADD CONSTRAINT fk_ee_transfer_to_eu FOREIGN KEY (id_to_energy_unit) REFERENCES gs_sys.gs_sys_energy_units(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_transfers
    ADD CONSTRAINT fk_ee_transfer_to_rd FOREIGN KEY (id_to_regional_district) REFERENCES gs_sys.gs_sys_regional_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_transfers
    ADD CONSTRAINT fk_ee_transfer_to_res FOREIGN KEY (id_to_regional_energy_system) REFERENCES gs_sys.gs_sys_regional_energy_systems(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_transfers
    ADD CONSTRAINT fk_ee_transfer_ues FOREIGN KEY (id_union_energy_system) REFERENCES gs_sys.gs_sys_union_energy_systems(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_transfers
    ADD CONSTRAINT fk_ee_transfer_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_em_exports
    ADD CONSTRAINT fk_em_export_db_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_em_exports
    ADD CONSTRAINT fk_em_export_from_rd FOREIGN KEY (id_from_regional_district) REFERENCES gs_sys.gs_sys_regional_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_em_exports
    ADD CONSTRAINT fk_em_export_from_res FOREIGN KEY (id_from_regional_energy_system) REFERENCES gs_sys.gs_sys_regional_energy_systems(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_em_exports
    ADD CONSTRAINT fk_em_export_to_country FOREIGN KEY (id_to_foreign_border_country) REFERENCES gs_sys.gs_sys_foreign_border_countries(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_em_exports
    ADD CONSTRAINT fk_em_export_to_eu FOREIGN KEY (id_to_energy_unit) REFERENCES gs_sys.gs_sys_energy_units(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_em_exports
    ADD CONSTRAINT fk_em_export_to_rd FOREIGN KEY (id_to_regional_district) REFERENCES gs_sys.gs_sys_regional_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_em_exports
    ADD CONSTRAINT fk_em_export_to_res FOREIGN KEY (id_to_regional_energy_system) REFERENCES gs_sys.gs_sys_regional_energy_systems(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_em_exports
    ADD CONSTRAINT fk_em_export_ues FOREIGN KEY (id_union_energy_system) REFERENCES gs_sys.gs_sys_union_energy_systems(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_em_exports
    ADD CONSTRAINT fk_em_export_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_espp_energy_generations
    ADD CONSTRAINT fk_espp_energy_gen_database_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_bem.gs_bem_espp_energy_generations
    ADD CONSTRAINT fk_espp_energy_gen_regional_energy_system FOREIGN KEY (id_regional_energy_system) REFERENCES gs_sys.gs_sys_regional_energy_systems(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_espp_energy_generations
    ADD CONSTRAINT fk_espp_energy_gen_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_ee_balance_custom_flow_rows
    ADD CONSTRAINT fk_gs_bem_eb_cfr_dbver FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_bem.gs_bem_ee_balance_custom_flow_values
    ADD CONSTRAINT fk_gs_bem_eb_cfv_dbver FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_bem.gs_bem_ee_balance_manual_generation_values
    ADD CONSTRAINT fk_gs_bem_eb_mgen_dbver FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_bem.gs_bem_power_balance_custom_flow_rows
    ADD CONSTRAINT fk_gs_bem_pb_cfr_dbver FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_bem.gs_bem_power_balance_custom_flow_values
    ADD CONSTRAINT fk_gs_bem_pb_cfv_dbver FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_bem.gs_bem_power_balance_export_values
    ADD CONSTRAINT fk_gs_bem_pb_exp_dbver FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_energy_generations
    ADD CONSTRAINT fk_res_energy_gen_database_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_energy_generations
    ADD CONSTRAINT fk_res_energy_gen_regional_energy_system FOREIGN KEY (id_regional_energy_system) REFERENCES gs_sys.gs_sys_regional_energy_systems(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_regional_energy_system_energy_generations
    ADD CONSTRAINT fk_res_energy_gen_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_station_energy_generations
    ADD CONSTRAINT fk_station_energy_gen_database_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_bem.gs_bem_station_energy_generations
    ADD CONSTRAINT fk_station_energy_gen_station FOREIGN KEY (id_station) REFERENCES gs_gen.gs_gen_stations(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_station_energy_generations
    ADD CONSTRAINT fk_station_energy_gen_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_bem.gs_bem_ee_balance_custom_flow_values
    ADD CONSTRAINT gs_bem_ee_balance_custom_flow_values_id_row_fkey FOREIGN KEY (id_row) REFERENCES gs_bem.gs_bem_ee_balance_custom_flow_rows(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_bem.gs_bem_ee_balance_station_group_values
    ADD CONSTRAINT gs_bem_ee_balance_station_group_values_id_station_group_fkey FOREIGN KEY (id_station_group) REFERENCES gs_gen.gs_gen_station_groups(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_bem.gs_bem_power_balance_custom_flow_values
    ADD CONSTRAINT gs_bem_power_balance_custom_flow_values_id_row_fkey FOREIGN KEY (id_row) REFERENCES gs_bem.gs_bem_power_balance_custom_flow_rows(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_ec.gs_ec_centralized_zone_consumption_params
    ADD CONSTRAINT gs_ec_centralized_zone_consumption_par_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ec.gs_ec_ees_consumption_params
    ADD CONSTRAINT gs_ec_ees_consumption_params_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ec.gs_ec_ees_russia_consumption_params
    ADD CONSTRAINT gs_ec_ees_russia_consumption_params_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ec.gs_ec_energy_area_consumption_params
    ADD CONSTRAINT gs_ec_energy_area_consumption_params_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ec.gs_ec_energy_area_consumption_params
    ADD CONSTRAINT gs_ec_energy_area_consumption_params_id_energy_area_fkey FOREIGN KEY (id_energy_area) REFERENCES gs_sys.gs_sys_energy_areas(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ec.gs_ec_energy_system_type_consumption_params
    ADD CONSTRAINT gs_ec_energy_system_type_consumption_id_energy_system_type_fkey FOREIGN KEY (id_energy_system_type) REFERENCES gs_sys.gs_sys_energy_system_types(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ec.gs_ec_energy_system_type_consumption_params
    ADD CONSTRAINT gs_ec_energy_system_type_consumption_p_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ec.gs_ec_energy_unit_consumption_params
    ADD CONSTRAINT gs_ec_energy_unit_consumption_params_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ec.gs_ec_energy_unit_consumption_params
    ADD CONSTRAINT gs_ec_energy_unit_consumption_params_id_energy_unit_fkey FOREIGN KEY (id_energy_unit) REFERENCES gs_sys.gs_sys_energy_units(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ec.gs_ec_energy_zone_consumption_params
    ADD CONSTRAINT gs_ec_energy_zone_consumption_params_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ec.gs_ec_energy_zone_consumption_params
    ADD CONSTRAINT gs_ec_energy_zone_consumption_params_id_energy_zone_fkey FOREIGN KEY (id_energy_zone) REFERENCES gs_sys.gs_sys_energy_zones(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ec.gs_ec_federal_district_consumption_params
    ADD CONSTRAINT gs_ec_federal_district_consumption_par_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ec.gs_ec_federal_district_consumption_params
    ADD CONSTRAINT gs_ec_federal_district_consumption_par_id_federal_district_fkey FOREIGN KEY (id_federal_district) REFERENCES gs_sys.gs_sys_federal_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ec.gs_ec_regional_district_consumption_params
    ADD CONSTRAINT gs_ec_regional_district_consumption_p_id_regional_district_fkey FOREIGN KEY (id_regional_district) REFERENCES gs_sys.gs_sys_regional_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ec.gs_ec_regional_district_consumption_params
    ADD CONSTRAINT gs_ec_regional_district_consumption_pa_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ec.gs_ec_regional_energy_system_consumption_params
    ADD CONSTRAINT gs_ec_regional_energy_system_con_id_regional_energy_system_fkey FOREIGN KEY (id_regional_energy_system) REFERENCES gs_sys.gs_sys_regional_energy_systems(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ec.gs_ec_regional_energy_system_consumption_params
    ADD CONSTRAINT gs_ec_regional_energy_system_consumpti_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ec.gs_ec_russia_federation_consumption_params
    ADD CONSTRAINT gs_ec_russia_federation_consumption_pa_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ec.gs_ec_synchronous_area_consumption_params
    ADD CONSTRAINT gs_ec_synchronous_area_consumption_par_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ec.gs_ec_synchronous_area_consumption_params
    ADD CONSTRAINT gs_ec_synchronous_area_consumption_par_id_synchronous_area_fkey FOREIGN KEY (id_synchronous_area) REFERENCES gs_sys.gs_sys_synchronous_areas(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ec.gs_ec_union_energy_system_consumption_params
    ADD CONSTRAINT gs_ec_union_energy_system_consumpti_id_union_energy_system_fkey FOREIGN KEY (id_union_energy_system) REFERENCES gs_sys.gs_sys_union_energy_systems(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ec.gs_ec_union_energy_system_consumption_params
    ADD CONSTRAINT gs_ec_union_energy_system_consumption__database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_eco.gs_eco_analysis_pg_params
    ADD CONSTRAINT fk_eco_analysis_pg_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_eco.gs_eco_analysis_zv_params
    ADD CONSTRAINT fk_eco_analysis_zv_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_eco.gs_eco_new_tes_norms
    ADD CONSTRAINT fk_eco_nt_norm_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_eco.gs_eco_operating_tes_coefficients
    ADD CONSTRAINT fk_eco_ot_coeff_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_eco.gs_eco_operating_tes_fuel_chars
    ADD CONSTRAINT fk_eco_ot_fuel_char_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_eco.gs_eco_operating_tes_inputs
    ADD CONSTRAINT fk_eco_ot_input_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_eco.gs_eco_analysis_pg_params
    ADD CONSTRAINT gs_eco_analysis_pg_params_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_eco.gs_eco_analysis_zv_params
    ADD CONSTRAINT gs_eco_analysis_zv_params_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_eco.gs_eco_fuel_snapshots
    ADD CONSTRAINT gs_eco_fuel_snapshots_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_eco.gs_eco_fuel_submissions
    ADD CONSTRAINT gs_eco_fuel_submissions_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_eco.gs_eco_gis_tek_greenhouse_gas_params
    ADD CONSTRAINT gs_eco_gis_tek_greenhouse_gas_params_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_eco.gs_eco_gis_tek_greenhouse_gas_params
    ADD CONSTRAINT gs_eco_gis_tek_greenhouse_gas_params_equipment_group_id_fkey FOREIGN KEY (equipment_group_id) REFERENCES gs_fue.gs_fue_equipment_groups(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_eco.gs_eco_gis_tek_greenhouse_gas_params
    ADD CONSTRAINT gs_eco_gis_tek_greenhouse_gas_year_number_database_version_fkey FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_eco.gs_eco_gis_tek_pollutant_params
    ADD CONSTRAINT gs_eco_gis_tek_pollutant_para_year_number_database_version_fkey FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_eco.gs_eco_gis_tek_pollutant_params
    ADD CONSTRAINT gs_eco_gis_tek_pollutant_params_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_eco.gs_eco_gis_tek_pollutant_params
    ADD CONSTRAINT gs_eco_gis_tek_pollutant_params_equipment_group_id_fkey FOREIGN KEY (equipment_group_id) REFERENCES gs_fue.gs_fue_equipment_groups(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_eco.gs_eco_new_tes_norms
    ADD CONSTRAINT gs_eco_new_tes_norms_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_eco.gs_eco_operating_tes_coefficients
    ADD CONSTRAINT gs_eco_operating_tes_coefficients_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_eco.gs_eco_operating_tes_fuel_chars
    ADD CONSTRAINT gs_eco_operating_tes_fuel_chars_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_eco.gs_eco_operating_tes_inputs
    ADD CONSTRAINT gs_eco_operating_tes_inputs_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_electrical_intensity_coefficients
    ADD CONSTRAINT fk_ei_fd_ei_c_ved FOREIGN KEY (id_economic_activity_type) REFERENCES gs_sys.gs_sys_economic_activity_types(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_electrical_intensity_year_params
    ADD CONSTRAINT fk_ei_fd_ei_y_ved FOREIGN KEY (id_economic_activity_type) REFERENCES gs_sys.gs_sys_economic_activity_types(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_electrical_intensity_year_params
    ADD CONSTRAINT fk_ei_fd_ei_y_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_population_consumption_year_params
    ADD CONSTRAINT fk_ei_fd_pop_cons_y_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ei.gs_ei_russia_federation_electrical_intensity_year_params
    ADD CONSTRAINT fk_ei_rf_ei_y_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_electrical_intensity_coefficients
    ADD CONSTRAINT gs_ei_federal_district_electrical_int_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_electrical_intensity_coefficients
    ADD CONSTRAINT gs_ei_federal_district_electrical_int_id_federal_district_fkey FOREIGN KEY (id_federal_district) REFERENCES gs_sys.gs_sys_federal_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_electrical_intensity_year_params
    ADD CONSTRAINT gs_ei_federal_district_electrical_inte_database_version_id_fke FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_electrical_intensity_year_params
    ADD CONSTRAINT gs_ei_federal_district_electrical_inte_id_federal_district_fke FOREIGN KEY (id_federal_district) REFERENCES gs_sys.gs_sys_federal_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_fd_total_consumption_coefficients
    ADD CONSTRAINT gs_ei_federal_district_fd_total_consum_database_version_id_fke FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_fd_total_consumption_coefficients
    ADD CONSTRAINT gs_ei_federal_district_fd_total_consum_id_federal_district_fke FOREIGN KEY (id_federal_district) REFERENCES gs_sys.gs_sys_federal_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_population_consumption_year_params
    ADD CONSTRAINT gs_ei_federal_district_population_con_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_population_consumption_year_params
    ADD CONSTRAINT gs_ei_federal_district_population_con_id_federal_district_fkey FOREIGN KEY (id_federal_district) REFERENCES gs_sys.gs_sys_federal_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_population_consumption_coefficients
    ADD CONSTRAINT gs_ei_federal_district_population_cons_database_version_id_fke FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ei.gs_ei_federal_district_population_consumption_coefficients
    ADD CONSTRAINT gs_ei_federal_district_population_cons_id_federal_district_fke FOREIGN KEY (id_federal_district) REFERENCES gs_sys.gs_sys_federal_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ei.gs_ei_russia_federation_electrical_intensity_coefficients
    ADD CONSTRAINT gs_ei_russia_federation_electrical_in_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ei.gs_ei_russia_federation_electrical_intensity_year_params
    ADD CONSTRAINT gs_ei_russia_federation_electrical_int_database_version_id_fke FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params
    ADD CONSTRAINT fk_ekp_fd_afci_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_accum_monetary_income_params
    ADD CONSTRAINT fk_ekp_fd_ami_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_eat_consumption_params
    ADD CONSTRAINT fk_ekp_fd_eat_cons_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_product_output_params
    ADD CONSTRAINT fk_ekp_fd_po_year_spec_out FOREIGN KEY (id_year_specific_product_output) REFERENCES gs_sys.gs_sys_years(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_product_output_params
    ADD CONSTRAINT fk_ekp_fd_po_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_population_params
    ADD CONSTRAINT fk_ekp_fd_pop_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ekp.gs_ekp_russia_federation_accum_fixed_capital_params
    ADD CONSTRAINT fk_ekp_rf_afci_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ekp.gs_ekp_russia_federation_product_output_params
    ADD CONSTRAINT fk_ekp_rf_po_year_spec_out FOREIGN KEY (id_year_specific_product_output) REFERENCES gs_sys.gs_sys_years(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ekp.gs_ekp_russia_federation_product_output_params
    ADD CONSTRAINT fk_ekp_rf_po_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ekp.gs_ekp_russia_federation_consumption_params
    ADD CONSTRAINT fk_ekp_rf_ved_cons_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_accum_monetary_income_params
    ADD CONSTRAINT gs_ekp_federal_district_accum_monetary_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_accum_monetary_income_params
    ADD CONSTRAINT gs_ekp_federal_district_accum_monetary_id_federal_district_fkey FOREIGN KEY (id_federal_district) REFERENCES gs_sys.gs_sys_federal_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_eat_consumption_params
    ADD CONSTRAINT gs_ekp_federal_district_economic__id_economic_activity_type_fke FOREIGN KEY (id_economic_activity_type) REFERENCES gs_sys.gs_sys_economic_activity_types(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params
    ADD CONSTRAINT gs_ekp_federal_district_economic_activ_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_product_output_params
    ADD CONSTRAINT gs_ekp_federal_district_economic_activ_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params
    ADD CONSTRAINT gs_ekp_federal_district_economic_activ_id_federal_district_fkey FOREIGN KEY (id_federal_district) REFERENCES gs_sys.gs_sys_federal_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_product_output_params
    ADD CONSTRAINT gs_ekp_federal_district_economic_activ_id_federal_district_fkey FOREIGN KEY (id_federal_district) REFERENCES gs_sys.gs_sys_federal_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_eat_consumption_params
    ADD CONSTRAINT gs_ekp_federal_district_economic_activi_database_version_id_fke FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_eat_consumption_params
    ADD CONSTRAINT gs_ekp_federal_district_economic_activi_id_federal_district_fke FOREIGN KEY (id_federal_district) REFERENCES gs_sys.gs_sys_federal_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_accum_fixed_capital_params
    ADD CONSTRAINT gs_ekp_federal_district_economic_id_economic_activity_type_fkey FOREIGN KEY (id_economic_activity_type) REFERENCES gs_sys.gs_sys_economic_activity_types(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_product_output_params
    ADD CONSTRAINT gs_ekp_federal_district_economic_id_economic_activity_type_fkey FOREIGN KEY (id_economic_activity_type) REFERENCES gs_sys.gs_sys_economic_activity_types(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_population_params
    ADD CONSTRAINT gs_ekp_federal_district_population_para_database_version_id_fke FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ekp.gs_ekp_federal_district_population_params
    ADD CONSTRAINT gs_ekp_federal_district_population_para_id_federal_district_fke FOREIGN KEY (id_federal_district) REFERENCES gs_sys.gs_sys_federal_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ekp.gs_ekp_russia_federation_accum_fixed_capital_params
    ADD CONSTRAINT gs_ekp_russia_federation_economi_id_economic_activity_type_fkey FOREIGN KEY (id_economic_activity_type) REFERENCES gs_sys.gs_sys_economic_activity_types(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ekp.gs_ekp_russia_federation_product_output_params
    ADD CONSTRAINT gs_ekp_russia_federation_economi_id_economic_activity_type_fkey FOREIGN KEY (id_economic_activity_type) REFERENCES gs_sys.gs_sys_economic_activity_types(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ekp.gs_ekp_russia_federation_accum_fixed_capital_params
    ADD CONSTRAINT gs_ekp_russia_federation_economic_acti_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ekp.gs_ekp_russia_federation_product_output_params
    ADD CONSTRAINT gs_ekp_russia_federation_economic_acti_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ekp.gs_ekp_russia_federation_consumption_params
    ADD CONSTRAINT gs_ekp_russia_federation_economic_activ_database_version_id_fke FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ekp.gs_ekp_russia_federation_consumption_params
    ADD CONSTRAINT gs_ekp_russia_federation_economic_id_economic_activity_type_fke FOREIGN KEY (id_economic_activity_type) REFERENCES gs_sys.gs_sys_economic_activity_types(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_groups
    ADD CONSTRAINT fk_equipment_group_energy_unit FOREIGN KEY (energy_unit_id) REFERENCES gs_sys.gs_sys_energy_units(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_heat_and_tariffs
    ADD CONSTRAINT fk_equipment_group_heat_and_tariffs_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_natural_fuel
    ADD CONSTRAINT fk_equipment_group_natural_fuel_year_ver FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_groups
    ADD CONSTRAINT fk_equipment_group_regional_district FOREIGN KEY (regional_district_id) REFERENCES gs_sys.gs_sys_regional_districts(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_groups
    ADD CONSTRAINT fk_equipment_group_regional_energy_system FOREIGN KEY (regional_energy_system_id) REFERENCES gs_sys.gs_sys_regional_energy_systems(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_distribution_parameters
    ADD CONSTRAINT fk_gs_fue_distribution_parameters_id_base_year FOREIGN KEY (id_base_year) REFERENCES gs_sys.gs_sys_years(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_distribution_parameters
    ADD CONSTRAINT fk_gs_fue_distribution_parameters_id_union_energy_system FOREIGN KEY (id_union_energy_system) REFERENCES gs_sys.gs_sys_union_energy_systems(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_distribution_parameters
    ADD CONSTRAINT fk_gs_fue_distribution_parameters_id_year FOREIGN KEY (id_year) REFERENCES gs_sys.gs_sys_years(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_fue.gs_fue_machine_fuel_param
    ADD CONSTRAINT fk_gs_fue_machine_fuel_param_equipment_group_id FOREIGN KEY (equipment_group_id) REFERENCES gs_fue.gs_fue_equipment_groups(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_allocatable_heat
    ADD CONSTRAINT gs_fue_allocatable_heat_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_distribution_coefficient_summaries
    ADD CONSTRAINT gs_fue_distribution_coefficient__distribution_parameter_id_fkey FOREIGN KEY (distribution_parameter_id) REFERENCES gs_fue.gs_fue_distribution_parameters(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_fue.gs_fue_distribution_coefficient_summaries
    ADD CONSTRAINT gs_fue_distribution_coefficient_summar_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_distribution_parameters
    ADD CONSTRAINT gs_fue_distribution_parameters_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_coefficient_results
    ADD CONSTRAINT gs_fue_equipment_group_coefficie_distribution_parameter_id_fkey FOREIGN KEY (distribution_parameter_id) REFERENCES gs_fue.gs_fue_distribution_parameters(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_coefficient_results
    ADD CONSTRAINT gs_fue_equipment_group_coefficient_res_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_coefficient_results
    ADD CONSTRAINT gs_fue_equipment_group_coefficient_resu_equipment_group_id_fkey FOREIGN KEY (equipment_group_id) REFERENCES gs_fue.gs_fue_equipment_groups(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_electricity_production_cost
    ADD CONSTRAINT gs_fue_equipment_group_electricity_pro_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_electricity_production_cost
    ADD CONSTRAINT gs_fue_equipment_group_electricity_prod_equipment_group_id_fkey FOREIGN KEY (equipment_group_id) REFERENCES gs_fue.gs_fue_equipment_groups(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_extra_fuel_param
    ADD CONSTRAINT gs_fue_equipment_group_extra_fuel_par_database_version_id_fkey1 FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_extra_fuel_param
    ADD CONSTRAINT gs_fue_equipment_group_extra_fuel_para_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_extra_fuel_param
    ADD CONSTRAINT gs_fue_equipment_group_extra_fuel_param_equipment_group_id_fkey FOREIGN KEY (equipment_group_id) REFERENCES gs_fue.gs_fue_equipment_groups(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_fuel_formula
    ADD CONSTRAINT gs_fue_equipment_group_fuel_formula_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_fuel_formula
    ADD CONSTRAINT gs_fue_equipment_group_fuel_formula_equipment_group_id_fkey FOREIGN KEY (equipment_group_id) REFERENCES gs_fue.gs_fue_equipment_groups(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_fuel_param
    ADD CONSTRAINT gs_fue_equipment_group_fuel_param_be_fkey FOREIGN KEY (be) REFERENCES gs_fue_em.gs_fue_em_business_unit(external_id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_fuel_param
    ADD CONSTRAINT gs_fue_equipment_group_fuel_param_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_fuel_param
    ADD CONSTRAINT gs_fue_equipment_group_fuel_param_database_version_id_fkey1 FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_fuel_param
    ADD CONSTRAINT gs_fue_equipment_group_fuel_param_dep_fkey FOREIGN KEY (dep) REFERENCES gs_fue_em.gs_fue_em_department(external_id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_fuel_param
    ADD CONSTRAINT gs_fue_equipment_group_fuel_param_equipment_group_id_fkey FOREIGN KEY (equipment_group_id) REFERENCES gs_fue.gs_fue_equipment_groups(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_fuel_param
    ADD CONSTRAINT gs_fue_equipment_group_fuel_param_er_fkey FOREIGN KEY (er) REFERENCES gs_fue_em.gs_fue_em_economic_region(external_id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_fuel_param
    ADD CONSTRAINT gs_fue_equipment_group_fuel_param_gk_fkey FOREIGN KEY (gk) REFERENCES gs_fue_em.gs_fue_em_gen_company(external_id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_fuel_param
    ADD CONSTRAINT gs_fue_equipment_group_fuel_param_obl_fkey FOREIGN KEY (obl) REFERENCES gs_fue_em.gs_fue_em_territories_energy(external_id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_fuel_param
    ADD CONSTRAINT gs_fue_equipment_group_fuel_param_obor_fkey FOREIGN KEY (obor) REFERENCES gs_fue_em.gs_fue_em_equipment_group(code) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_fuel_param
    ADD CONSTRAINT gs_fue_equipment_group_fuel_param_oes_fkey FOREIGN KEY (oes) REFERENCES gs_fue_em.gs_fue_em_union_energy_system(external_id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_heat_and_tariffs
    ADD CONSTRAINT gs_fue_equipment_group_heat_and_tariff_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_heat_and_tariffs
    ADD CONSTRAINT gs_fue_equipment_group_heat_and_tariffs_equipment_group_id_fkey FOREIGN KEY (equipment_group_id) REFERENCES gs_fue.gs_fue_equipment_groups(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_natural_fuel
    ADD CONSTRAINT gs_fue_equipment_group_natural_fuel_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_natural_fuel
    ADD CONSTRAINT gs_fue_equipment_group_natural_fuel_equipment_group_id_fkey FOREIGN KEY (equipment_group_id) REFERENCES gs_fue.gs_fue_equipment_groups(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_sets
    ADD CONSTRAINT gs_fue_equipment_group_sets_equipment_group_id_fkey FOREIGN KEY (equipment_group_id) REFERENCES gs_fue.gs_fue_equipment_groups(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_sets
    ADD CONSTRAINT gs_fue_equipment_group_sets_equipment_group_set_station_id_fkey FOREIGN KEY (equipment_group_set_station_id) REFERENCES gs_fue.gs_fue_equipment_group_type_stations(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_specific_fuel_cost
    ADD CONSTRAINT gs_fue_equipment_group_specific_fuel__database_version_id_fkey1 FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_specific_fuel_consumption
    ADD CONSTRAINT gs_fue_equipment_group_specific_fuel_c_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_specific_fuel_cost
    ADD CONSTRAINT gs_fue_equipment_group_specific_fuel_c_equipment_group_id_fkey1 FOREIGN KEY (equipment_group_id) REFERENCES gs_fue.gs_fue_equipment_groups(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_specific_fuel_consumption
    ADD CONSTRAINT gs_fue_equipment_group_specific_fuel_co_equipment_group_id_fkey FOREIGN KEY (equipment_group_id) REFERENCES gs_fue.gs_fue_equipment_groups(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_specific_fuel_price
    ADD CONSTRAINT gs_fue_equipment_group_specific_fuel_p_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_specific_fuel_price
    ADD CONSTRAINT gs_fue_equipment_group_specific_fuel_pr_equipment_group_id_fkey FOREIGN KEY (equipment_group_id) REFERENCES gs_fue.gs_fue_equipment_groups(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_type_stations
    ADD CONSTRAINT gs_fue_equipment_group_type_stati_equipment_group_type_id_fkey1 FOREIGN KEY (equipment_group_type_id) REFERENCES gs_sys.gs_sys_equipment_groups(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_type_stations
    ADD CONSTRAINT gs_fue_equipment_group_type_statio_equipment_group_type_id_fkey FOREIGN KEY (equipment_group_type_id) REFERENCES gs_sys.gs_sys_equipment_groups(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_type_stations
    ADD CONSTRAINT gs_fue_equipment_group_type_stations_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_type_stations
    ADD CONSTRAINT gs_fue_equipment_group_type_stations_database_version_id_fkey1 FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_type_stations
    ADD CONSTRAINT gs_fue_equipment_group_type_stations_station_id_fkey FOREIGN KEY (station_id) REFERENCES gs_gen.gs_gen_stations(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_group_type_stations
    ADD CONSTRAINT gs_fue_equipment_group_type_stations_station_id_fkey1 FOREIGN KEY (station_id) REFERENCES gs_gen.gs_gen_stations(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_groups
    ADD CONSTRAINT gs_fue_equipment_groups_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_groups
    ADD CONSTRAINT gs_fue_equipment_groups_database_version_id_fkey1 FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_groups
    ADD CONSTRAINT gs_fue_equipment_groups_regional_district_id_fkey FOREIGN KEY (regional_district_id) REFERENCES gs_sys.gs_sys_regional_districts(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_equipment_groups
    ADD CONSTRAINT gs_fue_equipment_groups_regional_energy_system_id_fkey FOREIGN KEY (regional_energy_system_id) REFERENCES gs_sys.gs_sys_regional_energy_systems(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_fixed_heat
    ADD CONSTRAINT gs_fue_fixed_heat_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_machine_fuel_param
    ADD CONSTRAINT gs_fue_machine_fuel_param_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_machine_fuel_param
    ADD CONSTRAINT gs_fue_machine_fuel_param_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES gs_gen.gs_gen_machines(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_fue.gs_fue_machine_fuel_param
    ADD CONSTRAINT gs_fue_machine_topl_agr_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_fue.gs_fue_machine_fuel_param
    ADD CONSTRAINT gs_fue_machine_topl_agr_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES gs_gen.gs_gen_machines(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_fue.gs_fue_restrictions
    ADD CONSTRAINT gs_fue_restrictions_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_boilers
    ADD CONSTRAINT boilers_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_boilers
    ADD CONSTRAINT boilers_id_station_fkey FOREIGN KEY (id_station) REFERENCES gs_gen.gs_gen_stations(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_documents_kommod
    ADD CONSTRAINT documents_kommod_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_gaes_tep_source_project_indicators
    ADD CONSTRAINT fk_gaes_tep_cap_cost_ges_year FOREIGN KEY (id_year_capital_cost_wo_pir_ges_with_reservoir) REFERENCES gs_sys.gs_sys_years(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_gaes_tep_source_project_indicators
    ADD CONSTRAINT fk_gaes_tep_cap_cost_svm_year FOREIGN KEY (id_year_capital_cost_wo_pir_svm) REFERENCES gs_sys.gs_sys_years(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_gaes_tep_source_project_indicators
    ADD CONSTRAINT fk_gaes_tep_cap_cost_total_year FOREIGN KEY (id_year_capital_cost_wo_pir_total) REFERENCES gs_sys.gs_sys_years(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_gaes_tep_source_project_indicators
    ADD CONSTRAINT fk_gaes_tep_database_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_gaes_tep_source_project_indicators
    ADD CONSTRAINT fk_gaes_tep_prospective_place_type_gaes FOREIGN KEY (id_prospective_place_type_gaes) REFERENCES gs_gen.gs_gen_prospective_place_types_gaes(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_gaes_tep_source_project_indicators
    ADD CONSTRAINT fk_gaes_tep_src_year_spec_capital FOREIGN KEY (id_year_specific_capital_investment) REFERENCES gs_sys.gs_sys_years(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_gaes_tep_source_project_indicators
    ADD CONSTRAINT fk_gaes_tep_src_year_spec_semifixed FOREIGN KEY (id_year_specific_semifixed_operating_costs) REFERENCES gs_sys.gs_sys_years(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_gaes_tep_source_project_indicators
    ADD CONSTRAINT fk_gaes_tep_station_prospective_place_gaes FOREIGN KEY (id_station_prospective_place_gaes) REFERENCES gs_gen.gs_gen_station_prospective_place_gaes(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_gen.gs_gen_ges_tep_source_project_indicators
    ADD CONSTRAINT fk_ges_tep_cap_cost_ges_year FOREIGN KEY (id_year_capital_cost_wo_pir_ges_with_reservoir) REFERENCES gs_sys.gs_sys_years(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_ges_tep_source_project_indicators
    ADD CONSTRAINT fk_ges_tep_cap_cost_svm_year FOREIGN KEY (id_year_capital_cost_wo_pir_svm) REFERENCES gs_sys.gs_sys_years(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_ges_tep_source_project_indicators
    ADD CONSTRAINT fk_ges_tep_cap_cost_total_year FOREIGN KEY (id_year_capital_cost_wo_pir_total) REFERENCES gs_sys.gs_sys_years(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_ges_tep_source_project_indicators
    ADD CONSTRAINT fk_ges_tep_database_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_ges_tep_source_project_indicators
    ADD CONSTRAINT fk_ges_tep_prospective_place_type_ges FOREIGN KEY (id_prospective_place_type_ges) REFERENCES gs_gen.gs_gen_prospective_place_types_ges(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_ges_tep_source_project_indicators
    ADD CONSTRAINT fk_ges_tep_src_year_spec_capital FOREIGN KEY (id_year_specific_capital_investment) REFERENCES gs_sys.gs_sys_years(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_ges_tep_source_project_indicators
    ADD CONSTRAINT fk_ges_tep_src_year_spec_semifixed FOREIGN KEY (id_year_specific_semifixed_operating_costs) REFERENCES gs_sys.gs_sys_years(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_ges_tep_source_project_indicators
    ADD CONSTRAINT fk_ges_tep_station_prospective_place_ges FOREIGN KEY (id_station_prospective_place_ges) REFERENCES gs_gen.gs_gen_station_prospective_place_ges(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_gen.gs_gen_machine_fuels
    ADD CONSTRAINT fk_machine_fuels_year_number_years FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_machine_names
    ADD CONSTRAINT fk_machine_names_year_number_years FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_machine_powers
    ADD CONSTRAINT fk_machine_powers_year_number_years FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_machine_prospective_place_aes
    ADD CONSTRAINT fk_machine_prospective_place_aes_database_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_machine_prospective_place_aes
    ADD CONSTRAINT fk_machine_prospective_place_aes_prospective_place_type FOREIGN KEY (id_prospective_place_type) REFERENCES gs_gen.gs_gen_prospective_place_types(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_machine_prospective_place_aes
    ADD CONSTRAINT fk_machine_prospective_place_aes_station FOREIGN KEY (id_station_prospective_place_aes) REFERENCES gs_gen.gs_gen_station_prospective_place_aes(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_gen.gs_gen_machine_tes_types
    ADD CONSTRAINT fk_machine_tes_types_year_number_years FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_machine_prospective_place_aes
    ADD CONSTRAINT fk_mpp_aes_year_spec_cap FOREIGN KEY (id_year_specific_capital_investment) REFERENCES gs_sys.gs_sys_years(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_machine_prospective_place_aes
    ADD CONSTRAINT fk_mpp_aes_year_spec_decom FOREIGN KEY (id_year_specific_decommissioning) REFERENCES gs_sys.gs_sys_years(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_machine_prospective_place_aes
    ADD CONSTRAINT fk_mpp_aes_year_spec_fixed_op FOREIGN KEY (id_year_specific_fixed_operating_costs) REFERENCES gs_sys.gs_sys_years(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_machine_prospective_place_aes
    ADD CONSTRAINT fk_mpp_aes_year_spec_fuel FOREIGN KEY (id_year_specific_fuel_cost) REFERENCES gs_sys.gs_sys_years(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_pgu_machine_powers
    ADD CONSTRAINT fk_pgu_machine_powers_year_number_years FOREIGN KEY (year_number, database_version_id) REFERENCES gs_sys.gs_sys_years(number, database_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_prospective_place_hydro_energy_forecasts
    ADD CONSTRAINT fk_pp_hydro_forecast_database_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_station_gaes_charge_consumptions
    ADD CONSTRAINT fk_station_gaes_charge_database_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_station_gaes_charge_consumptions
    ADD CONSTRAINT fk_station_gaes_charge_station FOREIGN KEY (id_station) REFERENCES gs_gen.gs_gen_stations(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_station_prospective_place_ges
    ADD CONSTRAINT fk_station_ges_id_prospective_place_type_ges FOREIGN KEY (id_prospective_place_type_ges) REFERENCES gs_gen.gs_gen_prospective_place_types_ges(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_station_owner_energy_generations
    ADD CONSTRAINT fk_station_owner_energy_gen_database_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_station_owner_energy_generations
    ADD CONSTRAINT fk_station_owner_energy_gen_station FOREIGN KEY (id_station) REFERENCES gs_gen.gs_gen_stations(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_station_prospective_place_aes
    ADD CONSTRAINT fk_station_prospective_place_aes_database_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_station_prospective_place_aes
    ADD CONSTRAINT fk_station_prospective_place_aes_regional_district FOREIGN KEY (id_regional_district) REFERENCES gs_sys.gs_sys_regional_districts(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_station_prospective_place_aes
    ADD CONSTRAINT fk_station_prospective_place_aes_regional_energy_system FOREIGN KEY (id_regional_energy_system) REFERENCES gs_sys.gs_sys_regional_energy_systems(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_station_prospective_place_gaes
    ADD CONSTRAINT fk_station_prospective_place_gaes_database_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_station_prospective_place_gaes
    ADD CONSTRAINT fk_station_prospective_place_gaes_prospective_place_type_gaes FOREIGN KEY (id_prospective_place_type_gaes) REFERENCES gs_gen.gs_gen_prospective_place_types_gaes(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_station_prospective_place_gaes
    ADD CONSTRAINT fk_station_prospective_place_gaes_regional_district FOREIGN KEY (id_regional_district) REFERENCES gs_sys.gs_sys_regional_districts(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_station_prospective_place_gaes
    ADD CONSTRAINT fk_station_prospective_place_gaes_regional_energy_system FOREIGN KEY (id_regional_energy_system) REFERENCES gs_sys.gs_sys_regional_energy_systems(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_station_prospective_place_ges
    ADD CONSTRAINT fk_station_prospective_place_ges_database_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_station_prospective_place_ges
    ADD CONSTRAINT fk_station_prospective_place_ges_regional_district FOREIGN KEY (id_regional_district) REFERENCES gs_sys.gs_sys_regional_districts(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_station_prospective_place_ges
    ADD CONSTRAINT fk_station_prospective_place_ges_regional_energy_system FOREIGN KEY (id_regional_energy_system) REFERENCES gs_sys.gs_sys_regional_energy_systems(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_station_snee_efficiencies
    ADD CONSTRAINT fk_station_snee_efficiency_database_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_station_snee_efficiencies
    ADD CONSTRAINT fk_station_snee_efficiency_station FOREIGN KEY (id_station) REFERENCES gs_gen.gs_gen_stations(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_station_snee_energy_consumptions
    ADD CONSTRAINT fk_station_snee_energy_consumption_database_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_station_snee_energy_consumptions
    ADD CONSTRAINT fk_station_snee_energy_consumption_station FOREIGN KEY (id_station) REFERENCES gs_gen.gs_gen_stations(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_stations
    ADD CONSTRAINT fk_stations_regional_energy_system FOREIGN KEY (id_regional_energy_system) REFERENCES gs_sys.gs_sys_regional_energy_systems(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_tep_price_conversion_coefficients
    ADD CONSTRAINT ges_tep_price_conversion_coefficients_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_gen.gs_gen_tep_price_conversion_coefficients
    ADD CONSTRAINT ges_tep_price_conversion_coefficients_id_year_fkey FOREIGN KEY (id_year) REFERENCES gs_sys.gs_sys_years(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_machine_fuels
    ADD CONSTRAINT machine_fuels_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_machine_fuels
    ADD CONSTRAINT machine_fuels_id_fuel_fkey FOREIGN KEY (id_fuel) REFERENCES gs_sys.gs_sys_fuels(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_machine_fuels
    ADD CONSTRAINT machine_fuels_id_machine_fkey FOREIGN KEY (id_machine) REFERENCES gs_gen.gs_gen_machines(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_machine_names
    ADD CONSTRAINT machine_names_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_machine_names
    ADD CONSTRAINT machine_names_database_version_id_fkey1 FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_machine_names
    ADD CONSTRAINT machine_names_id_machine_fkey FOREIGN KEY (id_machine) REFERENCES gs_gen.gs_gen_machines(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_machine_powers
    ADD CONSTRAINT machine_powers_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_machine_powers
    ADD CONSTRAINT machine_powers_id_machine_fkey FOREIGN KEY (id_machine) REFERENCES gs_gen.gs_gen_machines(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_machine_tes_types
    ADD CONSTRAINT machine_tes_types_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_machine_tes_types
    ADD CONSTRAINT machine_tes_types_id_machine_fkey FOREIGN KEY (id_machine) REFERENCES gs_gen.gs_gen_machines(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_machine_tes_types
    ADD CONSTRAINT machine_tes_types_id_tes_type_fkey FOREIGN KEY (id_tes_type) REFERENCES gs_sys.gs_sys_tes_types(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_machines
    ADD CONSTRAINT machines_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_machines
    ADD CONSTRAINT machines_id_condition_type_fkey FOREIGN KEY (id_condition_type) REFERENCES gs_sys.gs_sys_condition_types(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_machines
    ADD CONSTRAINT machines_id_energy_area_fkey FOREIGN KEY (id_energy_area) REFERENCES gs_sys.gs_sys_energy_areas(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_machines
    ADD CONSTRAINT machines_id_equipment_group_fkey FOREIGN KEY (id_equipment_group) REFERENCES gs_sys.gs_sys_equipment_groups(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_machines
    ADD CONSTRAINT machines_id_gen_company_fkey FOREIGN KEY (id_gen_company) REFERENCES gs_sys.gs_sys_companies(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_machines
    ADD CONSTRAINT machines_id_machine_type_fkey FOREIGN KEY (id_machine_type) REFERENCES gs_sys.gs_sys_machine_types(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_machines
    ADD CONSTRAINT machines_id_station_fkey FOREIGN KEY (id_station) REFERENCES gs_gen.gs_gen_stations(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_machines
    ADD CONSTRAINT machines_id_technology_availability_fkey FOREIGN KEY (id_technology_availability) REFERENCES gs_sys.gs_sys_technology_availabilities(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_machines
    ADD CONSTRAINT machines_id_technology_type_fkey FOREIGN KEY (id_technology_type) REFERENCES gs_sys.gs_sys_technology_types(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_machines
    ADD CONSTRAINT machines_id_tes_machine_type_fkey FOREIGN KEY (id_tes_machine_type) REFERENCES gs_sys.gs_sys_tes_machine_types(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_pgu_machine_names
    ADD CONSTRAINT pgu_machine_names_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_pgu_machine_names
    ADD CONSTRAINT pgu_machine_names_id_pgu_machine_fkey FOREIGN KEY (id_pgu_machine) REFERENCES gs_gen.gs_gen_pgu_machines(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_pgu_machine_powers
    ADD CONSTRAINT pgu_machine_powers_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_pgu_machine_powers
    ADD CONSTRAINT pgu_machine_powers_id_pgu_machine_fkey FOREIGN KEY (id_pgu_machine) REFERENCES gs_gen.gs_gen_pgu_machines(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_gen.gs_gen_pgu_machines
    ADD CONSTRAINT pgu_machines_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_pgu_machines
    ADD CONSTRAINT pgu_machines_id_condition_type_fkey FOREIGN KEY (id_condition_type) REFERENCES gs_sys.gs_sys_condition_types(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_pgu_machines
    ADD CONSTRAINT pgu_machines_id_parent_machine_fkey FOREIGN KEY (id_parent_machine) REFERENCES gs_gen.gs_gen_machines(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_gen.gs_gen_pgu_machines
    ADD CONSTRAINT pgu_machines_id_pgu_tes_machine_type_fkey FOREIGN KEY (id_pgu_tes_machine_type) REFERENCES gs_sys.gs_sys_pgu_tes_machine_types(id);

ALTER TABLE ONLY gs_gen.gs_gen_pgu_machines
    ADD CONSTRAINT pgu_machines_id_tes_machine_type_fkey FOREIGN KEY (id_tes_machine_type) REFERENCES gs_sys.gs_sys_tes_machine_types(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_station_groups
    ADD CONSTRAINT station_groups_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_stations
    ADD CONSTRAINT stations_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_gen.gs_gen_stations
    ADD CONSTRAINT stations_id_condition_type_fkey FOREIGN KEY (id_condition_type) REFERENCES gs_sys.gs_sys_condition_types(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_stations
    ADD CONSTRAINT stations_id_energy_unit_fkey FOREIGN KEY (id_energy_unit) REFERENCES gs_sys.gs_sys_energy_units(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_stations
    ADD CONSTRAINT stations_id_regional_district_fkey FOREIGN KEY (id_regional_district) REFERENCES gs_sys.gs_sys_regional_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_stations
    ADD CONSTRAINT stations_id_regional_energy_system_fkey FOREIGN KEY (id_regional_energy_system) REFERENCES gs_sys.gs_sys_regional_energy_systems(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_stations
    ADD CONSTRAINT stations_id_station_group_fkey FOREIGN KEY (id_station_group) REFERENCES gs_gen.gs_gen_station_groups(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_gen.gs_gen_stations
    ADD CONSTRAINT stations_id_station_type_fkey FOREIGN KEY (id_station_type) REFERENCES gs_sys.gs_sys_station_types(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_logs.logs
    ADD CONSTRAINT logs_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_logs.logs
    ADD CONSTRAINT logs_database_version_id_fkey1 FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_pd.gs_pd_centralized_zone_demand_params
    ADD CONSTRAINT gs_centralized_zone_demand_params_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_pd.gs_pd_ees_demand_params
    ADD CONSTRAINT gs_ees_demand_params_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_pd.gs_pd_ees_russia_demand_params
    ADD CONSTRAINT gs_ees_russia_demand_params_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_pd.gs_pd_energy_area_demand_params
    ADD CONSTRAINT gs_energy_area_demand_params_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_pd.gs_pd_energy_area_demand_params
    ADD CONSTRAINT gs_energy_area_demand_params_id_energy_area_fkey FOREIGN KEY (id_energy_area) REFERENCES gs_sys.gs_sys_energy_areas(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_pd.gs_pd_energy_system_type_demand_params
    ADD CONSTRAINT gs_energy_system_type_demand_params_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_pd.gs_pd_energy_system_type_demand_params
    ADD CONSTRAINT gs_energy_system_type_demand_params_id_energy_system_type_fkey FOREIGN KEY (id_energy_system_type) REFERENCES gs_sys.gs_sys_energy_system_types(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_pd.gs_pd_energy_unit_demand_params
    ADD CONSTRAINT gs_energy_unit_demand_params_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_pd.gs_pd_energy_unit_demand_params
    ADD CONSTRAINT gs_energy_unit_demand_params_id_energy_unit_fkey FOREIGN KEY (id_energy_unit) REFERENCES gs_sys.gs_sys_energy_units(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_pd.gs_pd_energy_zone_demand_params
    ADD CONSTRAINT gs_energy_zone_demand_params_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_pd.gs_pd_energy_zone_demand_params
    ADD CONSTRAINT gs_energy_zone_demand_params_id_energy_zone_fkey FOREIGN KEY (id_energy_zone) REFERENCES gs_sys.gs_sys_energy_zones(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_pd.gs_pd_federal_district_demand_params
    ADD CONSTRAINT gs_federal_district_demand_params_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_pd.gs_pd_federal_district_demand_params
    ADD CONSTRAINT gs_federal_district_demand_params_id_federal_district_fkey FOREIGN KEY (id_federal_district) REFERENCES gs_sys.gs_sys_federal_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_pd.gs_pd_ozp_max_power_params
    ADD CONSTRAINT gs_pd_ozp_max_power_params_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_pd.gs_pd_regional_district_demand_params
    ADD CONSTRAINT gs_regional_district_demand_params_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_pd.gs_pd_regional_district_demand_params
    ADD CONSTRAINT gs_regional_district_demand_params_id_regional_district_fkey FOREIGN KEY (id_regional_district) REFERENCES gs_sys.gs_sys_regional_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_pd.gs_pd_regional_energy_system_demand_params
    ADD CONSTRAINT gs_regional_energy_system_demand_id_regional_energy_system_fkey FOREIGN KEY (id_regional_energy_system) REFERENCES gs_sys.gs_sys_regional_energy_systems(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_pd.gs_pd_regional_energy_system_demand_params
    ADD CONSTRAINT gs_regional_energy_system_demand_param_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_pd.gs_pd_russia_federation_demand_params
    ADD CONSTRAINT gs_russia_federation_demand_params_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_pd.gs_pd_synchronous_area_demand_params
    ADD CONSTRAINT gs_synchronous_area_demand_params_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_pd.gs_pd_synchronous_area_demand_params
    ADD CONSTRAINT gs_synchronous_area_demand_params_id_synchronous_area_fkey FOREIGN KEY (id_synchronous_area) REFERENCES gs_sys.gs_sys_synchronous_areas(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_pd.gs_pd_union_energy_system_demand_params
    ADD CONSTRAINT gs_union_energy_system_demand_param_id_union_energy_system_fkey FOREIGN KEY (id_union_energy_system) REFERENCES gs_sys.gs_sys_union_energy_systems(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_pd.gs_pd_union_energy_system_demand_params
    ADD CONSTRAINT gs_union_energy_system_demand_params_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_rs.gs_rs_equipment_technical_characteristics
    ADD CONSTRAINT fk_rs_turbine_machine FOREIGN KEY (machine_id) REFERENCES gs_gen.gs_gen_machines(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_rs.gs_rs_equipment_technical_characteristics
    ADD CONSTRAINT fk_rs_turbine_pgu_machine FOREIGN KEY (pgu_machine_id) REFERENCES gs_gen.gs_gen_pgu_machines(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_rs.gs_rs_calculation_workbooks
    ADD CONSTRAINT gs_rs_calculation_workbooks_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_rs.gs_rs_technical_inspection_codes
    ADD CONSTRAINT gs_rs_technical_inspection_codes_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_rs.gs_rs_technical_inspection_codes
    ADD CONSTRAINT gs_rs_technical_inspection_codes_machine_id_fkey FOREIGN KEY (machine_id) REFERENCES gs_gen.gs_gen_machines(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_rs.gs_rs_technical_inspection_codes
    ADD CONSTRAINT gs_rs_technical_inspection_codes_pgu_machine_id_fkey FOREIGN KEY (pgu_machine_id) REFERENCES gs_gen.gs_gen_pgu_machines(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_rs.gs_rs_territory_discount_rates
    ADD CONSTRAINT gs_rs_territory_discount_rates_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_rs.gs_rs_territory_inputs
    ADD CONSTRAINT gs_rs_territory_inputs_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_rs.gs_rs_territory_inputs
    ADD CONSTRAINT gs_rs_territory_inputs_energy_zone_id_fkey FOREIGN KEY (energy_zone_id) REFERENCES gs_sys.gs_sys_energy_zones(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_rs.gs_rs_territory_technologies
    ADD CONSTRAINT gs_rs_territory_technologies_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_rs.gs_rs_territory_technologies
    ADD CONSTRAINT gs_rs_territory_technologies_energy_zone_id_fkey FOREIGN KEY (energy_zone_id) REFERENCES gs_sys.gs_sys_energy_zones(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_rs.gs_rs_territory_transfer_sections
    ADD CONSTRAINT gs_rs_territory_transfer_sections_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_rs.gs_rs_equipment_technical_characteristics
    ADD CONSTRAINT gs_rs_turbine_technical_characteristic_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_sys.gs_sys_database_versions
    ADD CONSTRAINT fk_database_versions_parent_version_id FOREIGN KEY (parent_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_economic_activity_types
    ADD CONSTRAINT fk_gs_sys_economic_activity_types_database_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_electricity_production_cost_types
    ADD CONSTRAINT fk_gs_sys_electricity_production_cost_types_database_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_entity_perimeter_bindings
    ADD CONSTRAINT fk_gs_sys_entity_perimeter_bindings_database_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_foreign_border_countries
    ADD CONSTRAINT fk_gs_sys_foreign_border_countries_database_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_fuels
    ADD CONSTRAINT fk_gs_sys_fuels_parent_id FOREIGN KEY (parent_id) REFERENCES gs_sys.gs_sys_fuels(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_perimeter_variants
    ADD CONSTRAINT fk_gs_sys_perimeter_variants_database_version FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_years
    ADD CONSTRAINT fk_refdata_years_database_version_id FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_tep_price_conversion_coefficients
    ADD CONSTRAINT ges_tep_price_conversion_coefficients_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_sys.gs_sys_tep_price_conversion_coefficients
    ADD CONSTRAINT ges_tep_price_conversion_coefficients_id_year_fkey FOREIGN KEY (id_year) REFERENCES gs_sys.gs_sys_years(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_sys.gs_sys_business_units
    ADD CONSTRAINT gs_business_units_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_companies
    ADD CONSTRAINT gs_companies_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_condition_types
    ADD CONSTRAINT gs_condition_types_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_departments
    ADD CONSTRAINT gs_departments_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_energy_areas
    ADD CONSTRAINT gs_energy_areas_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_energy_areas
    ADD CONSTRAINT gs_energy_areas_id_regional_district_fkey FOREIGN KEY (id_regional_district) REFERENCES gs_sys.gs_sys_regional_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_sys.gs_sys_energy_system_types
    ADD CONSTRAINT gs_energy_system_types_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_energy_units
    ADD CONSTRAINT gs_energy_units_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_energy_units
    ADD CONSTRAINT gs_energy_units_id_regional_district_fkey FOREIGN KEY (id_regional_district) REFERENCES gs_sys.gs_sys_regional_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_sys.gs_sys_energy_units
    ADD CONSTRAINT gs_energy_units_id_regional_energy_system_fkey FOREIGN KEY (id_regional_energy_system) REFERENCES gs_sys.gs_sys_regional_energy_systems(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_sys.gs_sys_energy_zones
    ADD CONSTRAINT gs_energy_zones_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_equipment_groups
    ADD CONSTRAINT gs_equipment_groups_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_equipment_groups
    ADD CONSTRAINT gs_equipment_groups_id_technology_availability_fkey FOREIGN KEY (id_technology_availability) REFERENCES gs_sys.gs_sys_technology_availabilities(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_equipment_groups
    ADD CONSTRAINT gs_equipment_groups_id_technology_type_fkey FOREIGN KEY (id_technology_type) REFERENCES gs_sys.gs_sys_technology_types(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_federal_districts
    ADD CONSTRAINT gs_federal_districts_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_fuel_types
    ADD CONSTRAINT gs_fuel_types_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_fuels
    ADD CONSTRAINT gs_fuels_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_fuels
    ADD CONSTRAINT gs_fuels_id_fuel_type_fkey FOREIGN KEY (id_fuel_type) REFERENCES gs_sys.gs_sys_fuel_types(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_sys.gs_sys_machine_types
    ADD CONSTRAINT gs_machine_types_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_pgu_tes_machine_types
    ADD CONSTRAINT gs_pgu_tes_machine_types_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_refdata_entities
    ADD CONSTRAINT gs_refdata_entities_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_refdata_entity_years
    ADD CONSTRAINT gs_refdata_entity_years_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_refdata_entity_years
    ADD CONSTRAINT gs_refdata_entity_years_refdata_entity_id_fkey FOREIGN KEY (refdata_entity_id) REFERENCES gs_sys.gs_sys_refdata_entities(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_sys.gs_sys_regional_district_regional_energy_system
    ADD CONSTRAINT gs_regional_district_regional_en_regional_energy_system_id_fkey FOREIGN KEY (regional_energy_system_id) REFERENCES gs_sys.gs_sys_regional_energy_systems(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_sys.gs_sys_regional_district_regional_energy_system
    ADD CONSTRAINT gs_regional_district_regional_energy__regional_district_id_fkey FOREIGN KEY (regional_district_id) REFERENCES gs_sys.gs_sys_regional_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_sys.gs_sys_regional_districts
    ADD CONSTRAINT gs_regional_districts_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_regional_districts
    ADD CONSTRAINT gs_regional_districts_id_energy_zone_fkey FOREIGN KEY (id_energy_zone) REFERENCES gs_sys.gs_sys_energy_zones(id) ON UPDATE CASCADE ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_regional_districts
    ADD CONSTRAINT gs_regional_districts_id_federal_district_fkey FOREIGN KEY (id_federal_district) REFERENCES gs_sys.gs_sys_federal_districts(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_sys.gs_sys_regional_districts
    ADD CONSTRAINT gs_regional_districts_id_synchronous_area_fkey FOREIGN KEY (id_synchronous_area) REFERENCES gs_sys.gs_sys_synchronous_areas(id) ON UPDATE CASCADE ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_regional_energy_systems
    ADD CONSTRAINT gs_regional_energy_systems_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_regional_energy_systems
    ADD CONSTRAINT gs_regional_energy_systems_id_union_energy_system_fkey FOREIGN KEY (id_union_energy_system) REFERENCES gs_sys.gs_sys_union_energy_systems(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_sys.gs_sys_station_types
    ADD CONSTRAINT gs_station_types_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_synchronous_areas
    ADD CONSTRAINT gs_synchronous_areas_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_entity_perimeter_bindings
    ADD CONSTRAINT gs_sys_entity_perimeter_bindings_id_perimeter_variant_fkey FOREIGN KEY (id_perimeter_variant) REFERENCES gs_sys.gs_sys_perimeter_variants(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_sys.gs_sys_technology_availabilities
    ADD CONSTRAINT gs_technology_availabilities_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_technology_types
    ADD CONSTRAINT gs_technology_types_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_tes_machine_types
    ADD CONSTRAINT gs_tes_machine_types_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_tes_types
    ADD CONSTRAINT gs_tes_types_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_union_energy_systems
    ADD CONSTRAINT gs_union_energy_systems_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_union_energy_systems
    ADD CONSTRAINT gs_union_energy_systems_id_energy_system_type_fkey FOREIGN KEY (id_energy_system_type) REFERENCES gs_sys.gs_sys_energy_system_types(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_sys.gs_sys_year_features
    ADD CONSTRAINT gs_year_features_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_year_service
    ADD CONSTRAINT gs_year_service_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_sys.gs_sys_years
    ADD CONSTRAINT gs_years_id_year_feature_fkey FOREIGN KEY (id_year_feature) REFERENCES gs_sys.gs_sys_year_features(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ter.gs_ter_energy_unit_power_transfer_values
    ADD CONSTRAINT gs_ter_energy_unit_power_tran_id_energy_unit_power_transfe_fkey FOREIGN KEY (id_energy_unit_power_transfer) REFERENCES gs_ter.gs_ter_energy_unit_power_transfers(id) ON DELETE CASCADE;

ALTER TABLE ONLY gs_ter.gs_ter_energy_unit_power_transfer_values
    ADD CONSTRAINT gs_ter_energy_unit_power_transfer_valu_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ter.gs_ter_energy_unit_power_transfers
    ADD CONSTRAINT gs_ter_energy_unit_power_transfers_database_version_id_fkey FOREIGN KEY (database_version_id) REFERENCES gs_sys.gs_sys_database_versions(id) ON DELETE SET NULL;

ALTER TABLE ONLY gs_ter.gs_ter_energy_unit_power_transfers
    ADD CONSTRAINT gs_ter_energy_unit_power_transfers_id_energy_unit_fkey FOREIGN KEY (id_energy_unit) REFERENCES gs_sys.gs_sys_energy_units(id) ON DELETE RESTRICT;

ALTER TABLE ONLY gs_ter.gs_ter_energy_unit_power_transfers
    ADD CONSTRAINT gs_ter_energy_unit_power_transfers_id_regional_district_fkey FOREIGN KEY (id_regional_district) REFERENCES gs_sys.gs_sys_regional_districts(id) ON DELETE RESTRICT;
