-- Minimal Postgres schema for Depsly telemetry ingestion and aggregation.

create table if not exists telemetry_raw_events (
    id bigserial primary key,
    received_at timestamptz not null default now(),
    event_timestamp timestamptz not null,
    schema_version text not null,
    install_id text not null,
    session_id text not null,
    depsly_version text not null,
    platform text not null,
    python_version text not null,
    command text not null,
    first_use_on_install boolean,
    options jsonb not null,
    result jsonb not null,
    event_json jsonb not null
);

create index if not exists telemetry_raw_events_received_at_idx
    on telemetry_raw_events (received_at);

create index if not exists telemetry_raw_events_event_timestamp_idx
    on telemetry_raw_events (event_timestamp);

create index if not exists telemetry_raw_events_command_idx
    on telemetry_raw_events (command);

create index if not exists telemetry_raw_events_depsly_version_idx
    on telemetry_raw_events (depsly_version);

create index if not exists telemetry_raw_events_platform_idx
    on telemetry_raw_events (platform);


create table if not exists telemetry_daily_command_metrics (
    metric_date date not null,
    command text not null,
    depsly_version text not null,
    platform text not null,
    total_events integer not null,
    success_events integer not null,
    failure_events integer not null,
    first_use_events integer not null,
    primary key (metric_date, command, depsly_version, platform)
);


create table if not exists telemetry_daily_duration_buckets (
    metric_date date not null,
    command text not null,
    depsly_version text not null,
    platform text not null,
    duration_bucket text not null,
    event_count integer not null,
    primary key (metric_date, command, depsly_version, platform, duration_bucket)
);


create table if not exists telemetry_daily_graph_size_buckets (
    metric_date date not null,
    command text not null,
    depsly_version text not null,
    platform text not null,
    graph_size_bucket text not null,
    event_count integer not null,
    primary key (metric_date, command, depsly_version, platform, graph_size_bucket)
);


create table if not exists telemetry_daily_option_usage (
    metric_date date not null,
    command text not null,
    depsly_version text not null,
    platform text not null,
    option_name text not null,
    option_value text not null,
    event_count integer not null,
    primary key (metric_date, command, depsly_version, platform, option_name, option_value)
);


create table if not exists telemetry_daily_failure_categories (
    metric_date date not null,
    command text not null,
    depsly_version text not null,
    platform text not null,
    failure_category text not null,
    event_count integer not null,
    primary key (metric_date, command, depsly_version, platform, failure_category)
);
