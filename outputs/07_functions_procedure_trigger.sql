-- Create or replace a function that counts unresolved requests at one location.
CREATE OR REPLACE FUNCTION count_pending_requests(location_id INTEGER)
RETURNS BIGINT
LANGUAGE SQL
AS $$
    SELECT COUNT(*)
    FROM maintenance_requests AS r
    WHERE r.location_id = $1
      AND r.current_status IN ('Pending', 'In Progress');
$$;

-- Reassign a request while keeping the previous assignment in history.
-- Any active assignment is ended before the new assignment is inserted.
CREATE OR REPLACE PROCEDURE assign_worker(request_id INTEGER, worker_id INTEGER)
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE assignments AS a
    SET ended_at = CURRENT_TIMESTAMP
    WHERE a.request_id = $1
      AND a.ended_at IS NULL;

    INSERT INTO assignments (request_id, worker_id)
    VALUES ($1, $2);
END;
$$;

-- Add the request's initial status to status_history when it is created.
CREATE OR REPLACE FUNCTION record_initial_request_status()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO status_history (request_id, status, changed_at, note)
    VALUES (NEW.request_id, NEW.current_status, CURRENT_TIMESTAMP,
            'Initial request status.');
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_initial_request_status_history
AFTER INSERT ON maintenance_requests
FOR EACH ROW
EXECUTE FUNCTION record_initial_request_status();

-- Add one history row only when current_status actually changes.
CREATE OR REPLACE FUNCTION record_request_status_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO status_history (request_id, status, changed_at, note)
    VALUES (NEW.request_id, NEW.current_status, CURRENT_TIMESTAMP,
            'Status changed from ' || OLD.current_status || ' to ' || NEW.current_status || '.');
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_request_status_history
AFTER UPDATE OF current_status ON maintenance_requests
FOR EACH ROW
WHEN (OLD.current_status IS DISTINCT FROM NEW.current_status)
EXECUTE FUNCTION record_request_status_change();

-- Example function call for Engineering Block, Room 204.
-- This SELECT only reads data.
-- SELECT count_pending_requests(
--     (SELECT location_id
--      FROM campus_locations
--      WHERE building_name = 'Engineering Block'
--        AND area_name = 'Room 204')
-- );

-- Safe procedure example: uncomment and execute the whole block to test,
-- then ROLLBACK restores the original assignment records.
-- BEGIN;
-- CALL assign_worker(
--     (SELECT request_id
--      FROM maintenance_requests
--      WHERE title = 'Ceiling light flickering in lab'),
--     (SELECT worker_id
--      FROM workers
--      WHERE phone = '555-0101')
-- );
-- ROLLBACK;
