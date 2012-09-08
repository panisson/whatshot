
CREATE TABLE `users` (
  `id` int(11) NOT NULL,
  `screen_name` varchar(45) DEFAULT NULL,
  `blocked` varchar(1) NOT NULL DEFAULT 'N',
  `name` varchar(45) DEFAULT NULL,
  `description` varchar(1000) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `friends_count` int(11) DEFAULT NULL,
  `followers_count` int(11) DEFAULT NULL,
  `statuses_count` int(11) DEFAULT NULL,
  `profile_image_url` varchar(255) DEFAULT NULL,
  `lang` varchar(20) DEFAULT NULL,
  `location` varchar(100) DEFAULT NULL,
  `oauth_token` varchar(200) DEFAULT NULL,
  `oauth_token_secret` varchar(200) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;


CREATE TABLE `followers` (
  `source` int(11) NOT NULL,
  `target` int(11) NOT NULL,
  PRIMARY KEY (`source`,`target`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;


