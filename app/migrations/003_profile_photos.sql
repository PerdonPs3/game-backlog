ALTER TABLE profiles ADD COLUMN avatar_color TEXT NOT NULL DEFAULT '#64748b' CHECK (avatar_color ~ '^#[0-9a-fA-F]{6}$');
ALTER TABLE profiles ADD COLUMN avatar_image BYTEA CHECK (octet_length(avatar_image) <= 102400);
