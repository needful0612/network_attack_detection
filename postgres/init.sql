CREATE TABLE alerts (
    time        TIMESTAMPTZ       NOT NULL,
    src_ip      TEXT              NOT NULL,
    score       DOUBLE PRECISION  NOT NULL,
    svm_score   DOUBLE PRECISION,
    kitnet_score DOUBLE PRECISION
);

SELECT create_hypertable('alerts', 'time');