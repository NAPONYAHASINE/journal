-- Ajout de la colonne participate au modèle users
ALTER TABLE users ADD COLUMN participate INTEGER DEFAULT 0;
