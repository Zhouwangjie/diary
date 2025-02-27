create table diary_day
(
    id            int auto_increment
        primary key,
    content       text                                not null,
    time          bigint                              not null,
    created_time  timestamp default CURRENT_TIMESTAMP null,
    modify_time   timestamp default CURRENT_TIMESTAMP null on update CURRENT_TIMESTAMP,
    agent_content text                                not null,
    emotion       int                                 null
);

create table diary_month
(
    id            int auto_increment
        primary key,
    content       text                                null,
    month         int                                 null,
    day           varchar(255)                        null,
    create_time   timestamp default CURRENT_TIMESTAMP null,
    modify_time   timestamp default CURRENT_TIMESTAMP null on update CURRENT_TIMESTAMP,
    month_emotion int                                 null
);


