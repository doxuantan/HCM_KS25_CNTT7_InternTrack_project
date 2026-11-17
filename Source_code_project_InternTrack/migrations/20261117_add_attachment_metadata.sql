ALTER TABLE attachments
    ADD COLUMN stored_filename VARCHAR(255) NULL AFTER file_url,
    ADD COLUMN mime_type VARCHAR(127) NULL AFTER stored_filename,
    ADD COLUMN file_size INT NULL AFTER mime_type;
