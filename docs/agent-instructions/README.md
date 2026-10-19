# Instrucciones esenciales para la IA

Leer estas reglas antes de planear, crear o modificar cualquier parte del proyecto.
Se aplican a código, pruebas, documentación y configuración.

## Git Flow y responsabilidades

- `main` es la rama de producción y `develop` es la rama de integración del desarrollo y las pruebas. Usar estos nombres en minúsculas.
- La IA trabaja de forma autónoma sobre el desarrollo basado en `develop`. Nunca hacer merge ni push a `main` sin permiso explícito del usuario para esa operación. No interpretar el permiso para trabajar o subir `develop` como permiso para publicar en producción.
- Por cada cambio, crear desde `develop` una subrama local con un prefijo descriptivo: `feat/`, `fix/`, `docs/`, `refactor/`, `test/` o `chore/`, según corresponda. No hacer cambios directamente en `develop` o `main`.
- Hacer commits atómicos: cada commit debe representar un cambio coherente y tener un mensaje descriptivo. No mezclar trabajo ajeno al objetivo.
- Permanecer en la subrama hasta cumplir su objetivo, incluidas las validaciones pertinentes, o hasta que el usuario indique expresamente salir, cancelar o cambiar de tarea. Si hay un bloqueo, informarlo y conservar la subrama; no integrarla como si estuviera terminada.
- Al completar el objetivo, integrar la subrama en `develop` mediante `git merge --no-ff`, con un mensaje que identifique el cambio. Subir `develop` al remoto y verificar el resultado.
- Las subramas son locales: no hacerles push ni crear ramas remotas para ellas. Solo se suben `develop` y `main`; para `main` sigue siendo obligatorio el permiso explícito del usuario.

## Conservar el historial visual

- Conservar siempre los commits y la bifurcación de cada subrama en el grafo de Git. Usar merges con `--no-ff`, incluso cuando Git permita un fast-forward.
- No usar squash, fast-forward ni rebase para integrar una subrama en `develop`, porque eliminarían la bifurcación que se quiere visualizar.
- Después del merge y de verificar el push de `develop`, se puede eliminar la referencia local de la subrama con `git branch -d`. Nunca eliminar commits ni reescribir el historial para ocultarla.
- El commit de merge y sus dos padres conservan la bifurcación para las aplicaciones que muestran el grafo. Al borrar la referencia local, su etiqueta puede desaparecer según la aplicación; el mensaje del merge debe conservar el nombre de la subrama. Git no garantiza que todas las aplicaciones muestren una etiqueta de rama eliminada.
- No hacer force-push ni reescribir historia compartida. Conservar siempre los cambios existentes del usuario.
