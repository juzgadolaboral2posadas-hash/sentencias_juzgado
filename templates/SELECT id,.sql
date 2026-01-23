SELECT id,
       nombre_archivo,
       id_drive,
       link_web,
       anio_carpeta,
       sumario,
       voces,
       fecha_creacion
FROM public.sentencias
LIMIT 1000;