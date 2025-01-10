CREATE SCHEMA `arm-gs` ;

USE `arm-gs`;

-- Создание таблицы ролей (roles)
CREATE TABLE roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
);

INSERT INTO roles (name) VALUES
('super-admin'),
('Администратор ГО'),
('Администратор ЭЭ'),
('Администратор ЭМ/ЭК'),
('Администратор ТОП'),
('Пользователь ГО'),
('Пользователь ЭЭ'),
('Пользователь ЭМ/ЭК'),
('Пользователь ТОП'),
('guest');

-- Создание таблицы пользователей (users)
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(150) NOT NULL UNIQUE,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(250) NOT NULL,
    role_id INTEGER,
    FOREIGN KEY (role_id) REFERENCES roles (id)
);

-- Создание таблицы логов (log)
CREATE TABLE Log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    username VARCHAR(100) NOT NULL,
    action VARCHAR(255) NOT NULL,
    details TEXT
);

-- Создание таблицы федеральных округов (fo)
CREATE TABLE IF NOT EXISTS fo (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE
);

-- Создание таблицы субъектов РФ (region)
CREATE TABLE IF NOT EXISTS region (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE,
    id_fo INT,
    CONSTRAINT fk_id_fo FOREIGN KEY (id_fo) REFERENCES fo(id) 
        ON DELETE SET NULL ON UPDATE CASCADE
);

-- Создание таблицы типов ОЭС (oes_type)
CREATE TABLE IF NOT EXISTS oes_type (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE
);

INSERT INTO oes_type (name) VALUES
('ЕЭС России'),
('ТИТЭС'),
('Децентрализованная зона'),
('Новые территории');

-- Создание таблицы ОЭС (oes)
CREATE TABLE IF NOT EXISTS oes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE,
    id_oes_type INT,
    CONSTRAINT fk_oes_type FOREIGN KEY (id_oes_type) REFERENCES oes_type(id) 
        ON DELETE SET NULL ON UPDATE CASCADE
);
