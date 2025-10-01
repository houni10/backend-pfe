CREATE DATABASE IF NOT EXISTS pcba_inspector;
USE pcba_inspector;

--- Supprimer les anciennes tables si elles existent
DROP TABLE IF EXISTS inspections;
DROP TABLE IF EXISTS alerts;
DROP TABLE IF EXISTS operators;
DROP TABLE IF EXISTS stations;

-- Table inspections (alignée avec backend.py)
CREATE TABLE inspections (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pcb_id VARCHAR(50),
    status ENUM('passed','failed') NOT NULL,
    defects JSON,
    operator VARCHAR(100),
    station VARCHAR(100),
    components TEXT,
    microbe_count INT DEFAULT 0,
    image_path VARCHAR(255),
    confidence FLOAT DEFAULT 0.0,
    processing_time FLOAT DEFAULT 0.0,
    timestamp DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Table alerts
CREATE TABLE alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    message TEXT NOT NULL,
    level ENUM('info','warning','critical') DEFAULT 'info',
    ack BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table operators
CREATE TABLE operators (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    shift VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table stations
CREATE TABLE stations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    line VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Quelques données initiales
INSERT INTO operators (name, shift) VALUES
('Alice', 'Morning'),
('Bob', 'Evening'),
('Charlie', 'Night');

INSERT INTO stations (name, line) VALUES
('Station A', 'Line 1'),
('Station B', 'Line 1'),
('Station C', 'Line 2');
