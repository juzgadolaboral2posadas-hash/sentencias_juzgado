-- 1. Corregimos el nombre: de 'sumario' a 'texto_completo' (safe)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'sentencias' AND column_name = 'sumario'
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'sentencias' AND column_name = 'texto_completo'
        ) THEN
            EXECUTE 'ALTER TABLE public.sentencias RENAME COLUMN sumario TO texto_completo';
        ELSE
            RAISE NOTICE 'Omitido: columna texto_completo ya existe.';
        END IF;
    ELSE
        RAISE NOTICE 'Omitido: columna sumario no existe.';
    END IF;
END
$$;

-- 2. Agregamos la columna para la inteligencia artificial (vectores)
CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE public.indices_sentencia ADD COLUMN IF NOT EXISTS vector_embedding vector(768);
ALTER TABLE indices_sentencia ADD COLUMN vector_embedding vector(768);
