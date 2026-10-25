ALTER TABLE profiles ALTER COLUMN share_wishlist SET DEFAULT TRUE;
UPDATE profiles SET share_wishlist = TRUE;
