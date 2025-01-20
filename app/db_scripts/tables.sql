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
DROP TABLE IF EXISTS Log;

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

-- Создание таблицы региональных энергосистем (oes)
CREATE TABLE IF NOT EXISTS res (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE,
    id_oes INT,
    CONSTRAINT fk_oes FOREIGN KEY (id_oes) REFERENCES oes(id) 
        ON DELETE SET NULL ON UPDATE CASCADE
);

-- Создание таблицы вхождения субъектов РФ в региональные энергосистемы 
CREATE TABLE res_region (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_res INT NOT NULL,
    id_region INT NOT NULL,
    FOREIGN KEY (id_res) REFERENCES res(id),
    FOREIGN KEY (id_region) REFERENCES region(id)
    ON DELETE CASCADE
);

-- Добавляем записи в таблицу
INSERT INTO res_region (id, id_res, id_region) VALUES
(1, 1, 1),
(2, 2, 2),
(3, 3, 3),
(4, 4, 3),
(5, 4, 36),
(6, 5, 4),
(7, 6, 5),
(8, 7, 6),
(9, 8, 7),
(10, 9, 8),
(11, 10, 9),
(12, 11, 10),
(13, 12, 33),
(14, 13, 33),
(15, 13, 34),
(16, 14, 67),
(17, 15, 67),
(18, 15, 29),
(19, 16, 71),
(20, 17, 11),
(21, 18, 12),
(22, 19, 13),
(23, 20, 14),
(24, 21, 15),
(25, 22, 16),
(26, 23, 17),
(27, 24, 18),
(28, 25, 19),
(29, 26, 20),
(30, 27, 21),
(31, 28, 22),
(32, 29, 23),
(33, 30, 24),
(34, 31, 25),
(35, 32, 25),
(36, 32, 47),
(37, 33, 26),
(38, 34, 26),
(39, 34, 62),
(40, 35, 27),
(41, 36, 28),
(42, 37, 29),
(43, 38, 30),
(44, 39, 31),
(45, 40, 32),
(46, 41, 34),
(47, 42, 35),
(48, 43, 36),
(49, 44, 37),
(50, 45, 38),
(51, 46, 39),
(52, 47, 40),
(53, 48, 41),
(54, 49, 42),
(55, 50, 43),
(56, 51, 44),
(57, 52, 45),
(58, 53, 46),
(59, 54, 47),
(60, 55, 48),
(61, 56, 48),
(62, 56, 1),
(63, 57, 49),
(64, 58, 50),
(65, 59, 51),
(66, 60, 52),
(67, 61, 53),
(68, 62, 54),
(69, 63, 55),
(70, 64, 56),
(71, 65, 56),
(72, 65, 71),
(73, 66, 57),
(74, 67, 58),
(75, 68, 59),
(76, 69, 60),
(77, 70, 61),
(78, 71, 62),
(79, 72, 63),
(80, 73, 64),
(81, 74, 65),
(82, 75, 66),
(83, 76, 68),
(84, 77, 69),
(85, 78, 70),
(86, 79, 72),
(87, 80, 73),
(88, 81, 26),
(89, 82, 74),
(90, 83, 75),
(91, 84, 76),
(92, 85, 77),
(93, 86, 78),
(94, 87, 78),
(95, 87, 82),
(96, 87, 88),
(97, 88, 79),
(98, 89, 80),
(99, 90, 81),
(100, 91, 81),
(101, 91, 12),
(102, 92, 83),
(103, 93, 82),
(104, 94, 84),
(105, 95, 85),
(106, 96, 86),
(107, 97, 87),
(108, 98, 88),
(109, 99, 89);

