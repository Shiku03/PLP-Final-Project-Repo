CREATE DATABASE GenEd;

CREATE TABLE users(
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(50) NOT NULL,
    password VARCHAR(50)NOT NULL,
    fullname VARCHAR(100) NOT NULL,
    nemis_number VARCHAR(50),
    tsc_number VARCHAR(50)
    phine_number VARCHAR(50)
);


CREATE TABLE accounts(
    account_type NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
    account_status NOT NULL
);


CREATE TABLE downloads(
    video_id INT PRIMARY KEY AUTO_INCREMENT UNIQUE,
    download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
