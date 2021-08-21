-- isu
ALTER TABLE isu ADD INDEX index_isu_on_jia_isu_uuid(jia_isu_uuid);
ALTER TABLE isu ADD INDEX index_isu_on_jia_user_id(jia_user_id);
ALTER TABLE isu ADD INDEX index_isu_on_jia_isu_uuid_jia_user_id(jia_user_id, jia_isu_uuid);

-- isu_condition
ALTER TABLE isu_condition ADD INDEX index_isu_condition_on_jia_isu_uuid(jia_isu_uuid);

-- user
ALTER TABLE user ADD INDEX index_user_on_jia_user_id(jia_user_id);
