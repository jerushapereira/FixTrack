-- Create tables that do not depend on other FixTrack tables first.
CREATE TABLE campus_users (
    user_id SERIAL PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    user_role VARCHAR(20) NOT NULL
        CHECK (user_role IN ('Student', 'Faculty', 'Staff'))
);

CREATE TABLE campus_locations (
    location_id SERIAL PRIMARY KEY,
    building_name VARCHAR(100) NOT NULL,
    area_name VARCHAR(100) NOT NULL
);

CREATE TABLE workers (
    worker_id SERIAL PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) UNIQUE,
    specialization VARCHAR(60) NOT NULL
);

-- These tables reference the parent tables created above.
CREATE TABLE maintenance_requests (
    request_id SERIAL PRIMARY KEY,
    reporter_id INTEGER NOT NULL REFERENCES campus_users(user_id),
    location_id INTEGER NOT NULL REFERENCES campus_locations(location_id),
    title VARCHAR(120) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(40) NOT NULL,
    priority VARCHAR(20) NOT NULL DEFAULT 'Medium'
        CHECK (priority IN ('Low', 'Medium', 'High')),
    current_status VARCHAR(20) NOT NULL DEFAULT 'Pending'
        CHECK (current_status IN ('Pending', 'In Progress', 'Resolved')),
    reported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE assignments (
    assignment_id SERIAL PRIMARY KEY,
    request_id INTEGER NOT NULL REFERENCES maintenance_requests(request_id),
    worker_id INTEGER NOT NULL REFERENCES workers(worker_id),
    assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    CHECK (ended_at IS NULL OR ended_at >= assigned_at)
);

CREATE TABLE status_history (
    history_id SERIAL PRIMARY KEY,
    request_id INTEGER NOT NULL REFERENCES maintenance_requests(request_id),
    status VARCHAR(20) NOT NULL
        CHECK (status IN ('Pending', 'In Progress', 'Resolved')),
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    note TEXT
);

-- Add the approved rule that a building and area identify one location.
ALTER TABLE campus_locations
ADD CONSTRAINT uq_campus_locations_building_area
UNIQUE (building_name, area_name);
