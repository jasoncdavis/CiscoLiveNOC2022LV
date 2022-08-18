# MySQL Table definitions

CREATE TABLE `WirelessClients` (
  `MACAddress` varchar(17) NOT NULL,
  `APMACAddress` varchar(17) DEFAULT NULL,
  `Channel` varchar(4) DEFAULT NULL,
  `SSID` varchar(64) DEFAULT NULL,
  `RadioType` varchar(32) DEFAULT NULL,
  `RadioPHYType` varchar(32) DEFAULT NULL,
  `SeenCount` int DEFAULT NULL,
  `SeenLastDateTime` datetime DEFAULT NULL,
  `SeenLastPoll` tinyint(1) DEFAULT NULL,
  `Controller` varchar(45) DEFAULT NULL,
  PRIMARY KEY (`MACAddress`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `WirelessAPs` (
  `SerialNumber` varchar(32) NOT NULL,
  `RadioMACAddress` varchar(17) DEFAULT NULL,
  `EthernetMACAddress` varchar(17) DEFAULT NULL,
  `IPAddress` varchar(45) DEFAULT NULL,
  `Name` varchar(48) DEFAULT NULL,
  `Model` varchar(48) DEFAULT NULL,
  `Controller` varchar(45) DEFAULT NULL,
  `DateTimeFirstSeen` datetime DEFAULT NULL,
  `DateTimeLastSeen` datetime DEFAULT NULL,
  PRIMARY KEY (`SerialNumber`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `pingresults` (
  `mgmt_ip_address` varchar(45) NOT NULL,
  `reachable_pct` tinyint DEFAULT NULL,
  `avg_latency` decimal(7,2) DEFAULT NULL,
  `min_latency` decimal(7,2) DEFAULT NULL,
  `max_latency` decimal(7,2) DEFAULT NULL,
  `datetime_lastup` datetime DEFAULT NULL,
  `down_count` int NOT NULL,
  PRIMARY KEY (`mgmt_ip_address`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `inventory` (
  `hostname` varchar(45) DEFAULT NULL,
  `mgmt_ip_address` varchar(45) NOT NULL,
  `serial_number` varchar(30) DEFAULT NULL,
  `device_type` varchar(120) DEFAULT NULL,
  `device_group` varchar(45) DEFAULT NULL,
  `model` varchar(45) DEFAULT NULL,
  `source` varchar(30) DEFAULT NULL,
  `software_version` varchar(30) DEFAULT NULL,
  `location` varchar(60) DEFAULT NULL,
  `contacts` varchar(255) DEFAULT NULL,
  `do_ping` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`mgmt_ip_address`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `interface_metrics` (
  `hostname` varchar(45) NOT NULL,
  `last_crc` int DEFAULT NULL,
  PRIMARY KEY (`hostname`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;