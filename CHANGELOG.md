# Changelog

## [Unreleased]

### Fixed

- **`gitmem wip` no guardaba nada en Windows**, y llevaba así desde la 1.32.0. La verificación que se añadió para detectar contenido cruzado comparaba los bytes tal cual contra el blob que git guarda **después** de normalizar los finales de línea — cosa que git hace por defecto en Windows. Nunca coincidían, así que el sistema leía cada commit legítimo como sabotaje, lo deshacía, y decía *«otro proceso lo pisó»* sin que hubiera nadie. Ahora se compara contra el blob que git de verdad guardaría para esa ruta.
- **Deshacer un commit corrupto podía llevarse por delante un commit ajeno y legítimo, y mentir sobre lo que había hecho.** El mecanismo comprobaba que el historial no se hubiera movido y **después** ejecutaba `git reset --mixed HEAD~1` — una referencia que git resuelve en el instante de ejecutarse, no en el de la comprobación. Entre las dos cosas cabía un commit de otro proceso (una publicación, un commit a mano), y el reset se lo llevaba mientras el corrupto sobrevivía; el mensaje afirmaba lo contrario en las dos direcciones. Reproducido en vivo tres veces, cada una en un punto distinto.
  Cerrado cambiando de forma, no de cuidado: el deshacer es ahora **un único comando atómico** que lleva la condición dentro (`git update-ref` con el valor esperado) y falla solo si algo se movió. Mirar y actuar dejaron de ser dos momentos. Y el identificador del commit propio ya no se lee con un comando aparte: sale de la salida del propio `git commit`.
- **Un commit podía guardarse con el contenido de otro escritor bajo el mensaje del primero, y decir que todo fue bien.** Es el caso que la deuda tenía descartado desde el 4 de agosto por *«no va a pasar nunca»* — cierto cuando el único que escribía era una persona en una ventana, falso ahora que pueden ser dos agentes a la vez. Se verifica después de commitear y, si lo commiteado no es lo que se preparó, se deshace y se dice.

### Changed

- **Los tests del deshacer fijan la propiedad, no el comando.** Dos de ellos espiaban comandos concretos de git y se rompieron cuando el arreglo bueno los eliminó; se reapuntaron a lo que de verdad importa —que un commit ajeno no se pierde y que el mensaje no miente— y uno se retiró con el motivo escrito, porque el hueco que probaba dejó de poder existir.

## [1.33.0] - 2026-08-08

### Fixed

- **En Windows con Git Bash, la aduana decidía sobre el proyecto equivocado.** Ahí una ruta absoluta se escribe `/c/Users/x/proyecto`, y el hook no la reconocía como tal: ignoraba el `cd` y evaluaba el proyecto de la sesión en vez del de destino. O sea que `cd /c/otro && git commit ...` **podía aprobar un commit que tenía que bloquear**, y al revés. La aduana es lo que decide si un commit pasa, así que era lo más grave que podía fallar ahí. Lo destapó un test escrito a propósito para averiguarlo, que solo corre en Windows.
- **La instalación se saltaba su propio commit en silencio.** Nueve subprocesos leían la salida de sus hijos sin decir en qué codificación: en Windows eso mata el hilo lector y el llamante recibe «nada» en vez del texto. Uno de esos sitios trataba «no hay salida» y «no pude leer la salida» como la misma cosa — que son opuestas — y se saltaba el commit dándolo por hecho. Arreglados los nueve, y los cinco consumidores que podían tragarse ese vacío a ciegas.
- **El arranque escupía una traza de Python la primera vez que se instalaba en Windows**, por la misma causa: el instalador imprime un emoji que la codificación por defecto de esa consola no sabe leer.
- **La búsqueda de memoria distinguía mayúsculas.** `gitmem search windows` decía que no había nada mientras `gitmem search Windows` devolvía dos notas — o sea que preguntarle al sistema podía dar una respuesta falsa. Ahora encuentra lo mismo se escriba como se escriba, y muestra la palabra buscada en minúscula; el texto de las notas sale siempre tal cual se escribió.
- **La suite volvió a correr entera en las dos plataformas.** Venía de 284 errores y ni un test ejecutándose; ahora son 1.007 en verde en Ubuntu y en Windows.

## [1.32.0] - 2026-08-08

### Fixed

- **Un solo commit hecho en huso horario cero borraba la memoria entera del proyecto para quien la leyera con Python 3.10.** Git escribe esa fecha con una `Z` final (`2026-08-08T04:49:21Z`) y `datetime.fromisoformat` no la aceptó hasta Python 3.11 — que es la versión que fija el CI de este repositorio y la que trae Ubuntu 22.04 de serie. Y el huso lo lleva guardado el commit, no lo pone quien lee: basta un contenedor sin zona horaria, una fusión hecha desde la web de GitHub o un bot para envenenar el historial **para todo el mundo y para siempre**. Medido por el camino real: con tres notas y solo la de en medio envenenada, `gitmem search` perdía **las tres** y salía con código 1. En el lector del remoto era peor — se tragaba el error y devolvía «no hay actividad», indistinguible de que de verdad no hubiera nada.
  Arreglado matando la clase entera, no el síntoma: **las fechas se le piden a git en segundos**, un número que no tiene formato que interpretar mal. Un único lector en `timefmt.py` y cinco llamadores; el `except` que se tragaba el error, eliminado. Ya se había decidido así en el sistema anterior y se perdió al reescribirlo — era la segunda vez que este fallo aparecía.
- **La suite de tests no corría en ninguna máquina que no tuviera una identidad de git configurada.** El andamio creaba repositorios de prueba y commiteaba sin decir quién era el autor: en la máquina del propietario funcionaba, en el CI fallaba con 284 errores. Ahora la identidad la pone el propio andamio, así que no depende de cómo esté configurada la máquina que corra los tests.
- **El fichero de tests del scaffold tumbaba el CI entero.** Usaba `tomllib`, que solo existe desde Python 3.11: reventaba al recolectar, así que pytest abortaba y **no se ejecutaba ni uno** de los 1.015 tests. Los dos contratos que necesitan un parser de TOML se saltan ahora en Python 3.10, dicho en voz alta en el motivo del salto.
- **El médico del sistema avisa de una zona sin normalizar** en vez de pasarla en silencio o darla por corrupta, nombrándola y diciendo qué hacer.

### Changed

- **Las nueve fichas de agente, revisadas una por una con su propio agente.** Salieron: instrucciones que usaban una herramienta que el agente no tiene, comprobaciones que daban «limpio» siempre por buscar donde no era, ejemplos atados a un solo lenguaje en fichas que viajan a todos los proyectos, y una frase repetida en las nueve que les hacía concluir «no hay memoria» cuando la búsqueda simplemente no había encontrado esa palabra. Argus gana memoria propia como el resto del crew y pierde una herramienta que contradecía sus propias prohibiciones; Moriarty gana la barrera que le impide tocar código, que hasta ahora se sostenía solo en que no tenía con qué.
- **README reescrito.** Deja de ser un inventario: abre con lo que gana quien lo instala y lo sostiene con cuatro fallos reales que este sistema se encontró a sí mismo, con las cifras y trazables en el historial. Añadida la sección de **atribución** que faltaba — cada skill de terceros con su autor y su licencia.
- **La documentación de publicar decía cómo rescatar una publicación a medias, y la instrucción dejaba dos ficheros con la versión nueva puesta y sin guardar.** Corregida, junto con dos referencias a un script que no existe.

## [1.31.0] - 2026-08-07

### Fixed

- **Las zonas se guardan y se buscan siempre en minúsculas.** Antes se podía crear `Boot` con mayúscula, y luego buscar `boot` no la encontraba: dos sesiones nombrando la misma zona distinto acababan con dos zonas que nunca se cruzaban, y las notas de una eran invisibles desde la otra — sin un solo error por pantalla. Arreglado en los tres puntos: al crear (avisando de la normalización, no en silencio), al resolver, y en la puerta de zonas de una nota. Las zonas ya escritas con mayúscula en otros proyectos se siguen resolviendo, porque también se normaliza al leer. **Solo el nombre de la zona y sus alias**: la descripción, los titulares y cualquier texto libre se guardan tal cual se escribieron.
- **La búsqueda en memoria distinguía mayúsculas.** `gitmem search ultron` devolvía 0 notas vigentes y `gitmem search Ultron` devolvía 10 — los agentes perdían casi toda la memoria real y su ficha les decía que concluyeran que no existía. Corregido en la búsqueda por palabra y por identificador; lo que se muestra sale con su texto original.

### Fixed

- **Las nueve fichas concluían en falso cuando la memoria no devolvía nada.** Todas decían *«nada encontrado: ninguna memoria ha hablado nunca de este fichero»*. Lo único que prueba un cero es que ninguna nota contiene esa palabra literal. Ahora las nueve reintentan con el nombre del módulo y con la palabra que el propio proyecto usa para esa área, y dicen qué palabras probaron.
- **House usaba `git checkout` como forma preferida de limpiar sus marcas de diagnóstico.** A House lo llaman con alguien a medio arreglar el fichero: ese comando no borra sus líneas, devuelve el fichero al último guardado y se lleva por delante el trabajo sin commitear. Ahora las quita a mano, y `checkout`/`restore`/`reset`/`stash` quedan prohibidos ahí con el motivo escrito.
- **House registraba sus marcas en una herramienta que no tiene** (`TodoWrite`), así que la limpieza no tenía registro; y las verificaba con `grep ... src/`, una carpeta que no existe en todos los proyectos — donde no existe, el comprobante salía limpio siempre. Ahora usa su propio marcador y busca desde la raíz del repositorio.
- **House exigía una base de datos** entre sus señales obligatorias y paraba si faltaba. Ahora habla de estado persistente: base de datos, ficheros o el propio historial de git.
- **Argus era el único agente sin memoria propia**, y encima su ficha le decía que no persistiera nada — lo contrario de lo que hace el resto del crew. Ahora la lee al arrancar y tiene escrito qué guardar: sobre todo sus falsos positivos, que repetidos tres auditorías seguidas son peores que no auditar.
- **Argus llevaba `KillShell`** contra su propia prohibición de no tocar un sistema en marcha, y era el único de los nueve. Retirado; gana `Write` para su memoria.
- **Moriarty no podía escribir su memoria**: su cierre se la exigía y no tenía `Edit` ni `Write`. Y su ficha no nombraba los dos tipos de rotura que sí ha encontrado de verdad — la operación correcta contra el destino equivocado, y los tests en verde mientras lo guardado está vacío. Ahora sí.
- **Cerberus y Yoda no prohibían `git stash` ni `git restore`** en sus listas de comandos vetados.
- **Yoda no tenía escrito qué hacer con un alcance sin definir**, y por eso auditó un subproyecto que nadie le había pedido.
- **Ejemplos atados a un lenguaje**, en fichas que viajan a todos los proyectos: Cerberus hablaba de `console.log`, promesas y sintaxis de TypeScript; Dante solo daba integración web; Argus listaba tres gestores de paquetes como si fueran todos.
- **Alexandria tenía la regla de las tres audiencias sin ningún paso ejecutable.** Ahora lleva los tres comandos, y el `CLAUDE.md` raíz pasa a ser objetivo de verificación de sus propias afirmaciones, no solo fuente de verdad para los demás.

## [1.30.4] - 2026-08-06

### Fixed

- **La memoria de callejones sin salida de Bilbo estaba rota por los dos extremos.** La lectura esperaba un bloque inyectado que ya no existe, y la escritura prometía guardarlos como `memo(deadend/<subsystem>)` — un tipo de nota que el sistema no acepta (`deadend` no es zona, y toda nota exige dos zonas reales). Resultado: se escribían cada sesión y no se leía ninguno. Ahora los busca él en el arranque con `gitmem search`, y el orquestador los persiste como nota `M` con las dos zonas del subsistema y `deadend` entre sus claves.
- **La ficha de Bilbo dice ahora qué escribe en su propia memoria de agente**, separando las tres cosas que se confundían: lo que aprende del código, la memoria del proyecto que vive en `gitmem`, y el informe al orquestador.

## [1.30.3] - 2026-08-06

### Fixed

- **Las nueve fichas de agente llamaban a `gitmem` por una ruta larga al caché del plugin**, con un `find` de rescate incluido — justo lo que la skill de memoria prohíbe, porque esa ruta lleva un número de versión dentro y se queda obsoleta el día que el toolkit se actualiza. Ahora todas escriben `gitmem` pelado, que es lo que el instalador pone en el PATH.

## [1.30.2] - 2026-08-06

### Fixed

- **La ficha de Bilbo prometía una inyección de memoria que ya no existe.** Decía que recibía automáticamente un bloque `[PROJECT MEMORY — auto-recalled]` con los callejones sin salida de sesiones anteriores. Ese canal se retiró y ningún hook alimenta el prompt de un agente: el resultado era que Bilbo escribía dead-ends cada sesión y no leía ninguno. Ahora los busca él con `gitmem search`, y su ficha dice explícitamente que lo que no esté en su prompt no le llega.
- **Bilbo pasa a recibir skills del orquestador como el resto del crew.** Su ficha decía "no usa skills de dominio"; su propio Modo C exige leer el protocolo de destilación, y sin él una ronda produjo 43 notas de las que 41 estaban mal.

## [1.30.1] - 2026-08-06

### Fixed

- **`/remember` carga las reglas para Claude, no las imprime al usuario.** El usuario las escribió; no necesita que se las lean de vuelta. Ahora responde con una línea diciendo cuántas quedan cargadas, y solo detalla las que contradicen algo ya dicho o hecho en esa sesión.

## [1.30.0] - 2026-08-06

### Added

- **`/remember` — el primer y único comando de barra del toolkit.** Pone el fichero de reglas del proyecto en pantalla, entero, y a partir de ahí sus líneas son vinculantes en esa sesión. Solo lee: no acepta argumentos y nunca guarda. Guardar una regla sigue siendo trabajo de Claude, en el momento en que el usuario la dice — un usuario que tiene que invocar un comando para almacenar su propia corrección es un usuario cuya corrección se pierde. Estaba declarado como deuda desde el diseño de v2 (`unmassk-toolkit/commands/` no existía como carpeta) y nunca se había construido.
- **`--css-framework` en el scaffolder**, con las opciones que de verdad existen, y error explicativo cuando el tipo de proyecto elegido no las soporta.

### Fixed

- **La aduana decide por el directorio del comando, no por el de la sesión.** `cd /otro/proyecto && git commit ...` se evaluaba contra el proyecto de la sesión — podía dejar pasar un commit que debía bloquear. Y un `cd` posterior al commit (`cd proyecto && git commit && cd ..`, el idioma normal de trabajo) ya no pisa el directorio vigente en el momento del commit.
- **Un commit con un separador pegado sin espacio se saltaba la aduana entera.** `echo hi;git commit -m x` (y lo mismo con `&&`, `||`, `|`) no se reconocía como commit: no pasaba por el rescate, ni resolvía el directorio, ni leía la configuración. Un solo tokenizador en todo el fichero cierra el hueco.
- **El scaffolder ya no genera ficheros rotos en silencio.** `description`/`author`/`name` se interpolaban crudos en TOML y JS escritos a mano: una comilla dejaba el `pyproject.toml` inválido o el `layout.tsx` sin ser JavaScript, y el script imprimía «✅ Created» igualmente. Ahora se escapan con las reglas de cada formato.
- **Opciones del scaffolder que se aceptaban y no hacían nada.** `--orm drizzle/mongoose/tortoise/sequelize` producía exactamente el mismo proyecto que no pedir ORM; las cuatro opciones de CSS ni siquiera tenían flag. Ahora funcionan, o fallan diciendo qué sí vale.
- **El generador de CLI en Python era inalcanzable**: `--language` no existía como opción, así que `--type cli` nunca podía ser Python pese a que el generador estaba completo.
- **Un nombre de proyecto con ruta escribía fuera del directorio destino** sin quejarse, y el mensaje final seguía siendo «✅ Created».
- **El protocolo de proyecto nuevo menciona las zonas.** La detección comprueba si existen, START las crea antes de la fase de definición (sin ellas no se puede guardar ni una respuesta) y SCAN las nombra a partir del propio escaneo, pasándolas por el usuario antes de sembrar.

### Changed

- **Guardar una regla o dar de alta una zona ya no crea un commit propio.** Escriben su fichero y viajan pegados al siguiente commit que haya. Lo que la restricción exigía era que no se perdieran al clonar, no un commit por línea.
- **Retirada la comprobación de coherencia de reglas** (`health.coherence_rules()`): sin commits de regla no hay divergencia que detectar, y mantenerla habría hecho que cada regla nueva saliera como discrepancia falsa en cada arranque, para siempre.

## [1.29.2] - 2026-08-06

### Fixed

- **Los comandos de rescate de un merge o rebase a medias ya no dependen de leer una memoria que puede estar corrupta.** `git merge`/`rebase --abort`/`--continue`/`--skip`/`cherry-pick` se aprueban ANTES de tocar `config.json`/`zones.json` — antes, un `config.json` roto (típico de un merge o rebase a medias) bloqueaba también la única salida real del conflicto, dejando al usuario atascado.
- **Y ese rescate ya no depende de que `shlex` tokenice.** Un apóstrofo sin escapar en el mensaje de un commit encadenado (p.ej. `git commit -m 'WIP: don't lose this' && git rebase --abort`) hacía fallar el tokenizador; el fallback devolvía el rebase sin flags y el `--abort` se perdía. Ahora el fallback busca las tres banderas de rescate directamente en la cadena cruda y prioriza `rebase`/`merge`/`cherry-pick` cuando aparecen.
- **Un `config.json`/`zones.json` ilegible ya no bloquea con el volcado crudo de la excepción.** La aduana explica ahora cómo repararlo (revisar marcadores de conflicto sin resolver) en vez de mostrar la excepción tal cual.
- **`stop-dod-gate.py` avisa por stderr cuando `config.json` existe pero no se puede leer**, en vez de tragarse el fallo en el mismo silencio que el caso "no configurado" (que sigue callado — es opt-in). El docstring de `lib/memory/config.py` aclara que la garantía "nunca en silencio" es solo de su propio `load()`; quien lea el fichero por otra vía decide su propio contrato.
- **`gitmem zones list` y el médico del sistema distinguen "zones.json no existe" de "existe pero vacío"** — antes ambos casos imprimían el mismo "0 zonas". El médico gana además un check de zonas con validación de forma (cada zona debe ser un objeto; `description` texto; `aliases` lista de texto), y `check_project_config` ahora valida tipos, así que un `config.json` con un campo mal tipado (p.ej. `"customs_enabled": "true"`) ya no pasa en verde aunque la aduana lo rechace.

### Changed

- **`zones_state()` extraída en `lib/memory/health.py`**, reutilizada por `_memory_mounted()` y `gitmem zones list` en vez de que cada uno relea el fichero por su cuenta.
- **El instalador ya no importa `lib/memory` directamente.** `lib/install_apply.py` siembra los índices vía `gitmem rezones` (canal ya autorizado — `rezones.py` llama a `indexes.seed()` como primer paso) en vez de insertar `lib/memory/` en `sys.path`, preservando la garantía de que la memoria v2 se puede borrar entera sin romper la instalación.
- **CI endurecida:** `toolkit-ci.yml` y `plugin-tests.yml` ganan permisos de solo lectura, dependencias de Python fijadas por versión, `actions/checkout`/`setup-python` a `@v6`, caché de pip y `concurrency` con cancelación de ejecuciones en curso.
- **`rule.py::_parse_args` alineado con sus scripts hermanos** — el filtro de "palabras que se leen en vez de escribirse" se mueve de `_parse_args` a `main()`. `health.memory_mounted`/`possible_unconverted_legacy` pasan a privados (`_memory_mounted`/`_possible_unconverted_legacy`).

### Removed

- **`chatroom-ci.yml`** — chatroom es un subproyecto de referencia, no parte del pipeline principal.

## [1.29.1] - 2026-08-06

### Fixed

- **Dos ficheros de configuración decían lo contrario sobre la misma cosa.** `.claude/git-memory-config.json`, del sistema anterior, llevaba dentro un `repo_type` que **nadie leía** —`stop-dod-gate.py` solo saca `test_command` de ahí— y que contradecía al del sistema nuevo. El hook pasa a leer `.claude/project-memory/config.json`, donde viven juntas las tres claves, y el fichero viejo se retira.
- **Cinco ficheros huérfanos fuera de `.claude/.unmassk/`:** el contador de mensajes, el sello del fetch, el estado de contexto, el registro del arranque viejo y la caché del glosario. Ninguno tenía ya quien lo escribiera — sus productores se borraron con el sistema anterior; solo sobrevivían citados en comentarios.

## [1.29.0] - 2026-08-06

### Added

- **Un proyecto se instala solo al abrir sesión.** Si no tiene manifest, el arranque lanza el instalador antes de leer memoria: deja `gitmem` en el PATH, siembra los ocho índices, deduce y escribe `config.json`, y pone el `.gitignore`. Medido de punta a punta: de **nueve pasos manuales —dos de ellos rechazos— a cero**.
- **`gitmem` en el PATH**, con un lanzador en `~/.local/bin/gitmem` que resuelve la versión instalada más nueva en cada ejecución, así que no se queda muerto al actualizar. Si `~/.local/bin` no está en el PATH, la instalación lo dice con la línea exacta para el `~/.zshrc` — nunca edita el perfil del usuario.
- **`config.json` se deduce del repositorio**: una sola rama es `trunk`; varias con `dev`/`develop`, `gitflow`. Nunca pisa una clave existente. Antes **no lo escribía nadie**, y su defecto protegido rechazaba el primer commit de trabajo del día — en **11 de los 14 repositorios del propietario**.
- **El arranque avisa de dos cosas que antes callaba:** que la memoria del proyecto no está montada, diciendo qué falta por su nombre; y que puede haber **memoria del sistema anterior sin destilar** (muchos commits, cero notas reconocidas). Un proyecto con años de decisiones dentro se presentaba como *«todavía no se ha escrito nada»*.
- **El médico del sistema ausculta la memoria**: el lanzador, los ocho índices y la configuración, con su ✅/⚠️/❌ en la fase 5 de la instalación.

### Fixed

- **La instalación guarda en git lo que crea.** Un proyecto recién instalado terminaba el día con **diez ficheros sin guardar**: ruido permanente en `git status`, publicar bloqueado, y al clonar en otra máquina ni configuración ni índices. Pathspec explícito, nunca `git add -A`: el trabajo a medias del usuario no se arrastra dentro de un commit de instalación.
- **Las zonas viajan en git.** `zones.json` era el único fichero de memoria que el sistema escribía y **no commiteaba jamás**. Su nombre se puede deducir de los titulares, pero **su descripción y sus alias no viven en ningún commit** y `rezones` no puede reconstruirlos: al clonar desaparecían, y el arranque lo daba todo en verde.
- **El fichero de reglas viaja en git**, dentro del mismo commit que la regla. Antes se quedaba fuera: en un clon, `gitmem rule` devolvía vacío y el arranque cantaba una discrepancia por cada regla.
- **`gitmem work` sabe guardar un borrado.** Dejar de versionar un fichero era imposible con el sistema puesto: la aduana cierra la puerta de `git commit` y el comando propio no tenía esa operación.
- **`gitmem rule list` guardaba una regla que decía «list»**, y dejaba su commit para siempre. Ahora `list` lee, y una palabra suelta rebota.
- **El arranque decía «manifest al día» en proyectos sin instalar.** Ahora dice que no lo están.
- **La skill de memoria dejó de ofrecer la ruta larga como salida.** Si `gitmem` no se encuentra, eso no es motivo para tirar de la caché: es la señal de que ese proyecto nunca se montó, y tirar de la ruta lo deja a medias para siempre.

## [1.28.2] - 2026-08-05

### Fixed

- **El candado del sistema de memoria se colaba en git, y en todos los proyectos.** `zones.json.lock` vive junto al fichero que protege, no bajo `.claude/.unmassk/`, así que la única línea que el instalador escribía en el `.gitignore` no lo cubría. Es basura de funcionamiento —lo crea un proceso un instante y sobra— y aparecía en `git status` como si fuera trabajo del usuario. Se añade `.claude/project-memory/*.lock` a lo que el instalador ignora, así que se arregla solo en cada proyecto donde se instale, no solo aquí. **Deliberadamente estrecho, nunca un `*.lock` a secas:** `Cargo.lock`, `bun.lock` y `package-lock.json` son dependencias que sí tienen que viajar en git, y dejar de versionarlas rompería las instalaciones reproducibles.

## [1.28.1] - 2026-08-05

### Fixed

- **Nada obligaba a cargar la skill de memoria al abrir sesión, y se comprobó fallando en una sesión real.** La orden vive en el bloque del `CLAUDE.md` desde ayer, pero lo único que la reforzaba era el vigilante de cada mensaje — y ese **nombraba solo `unmassk-core`**, porque se escribió cuando la skill de memoria todavía no existía y nadie volvió a por él. Encima solo hablaba en el primer mensaje de la sesión: en un reinicio, con su fichero-marca ya puesto, no salió ni una vez. Resultado: la sesión arrancó con media tripulación cargada y sin que nada lo dijera.
- **El arranque ahora da la orden ANTES del enlace al informe.** `bin/memory/boot.py` imprime los tres pasos —cargar `unmassk-core`, cargar `unmassk-memory`, leer el informe entero y contar el menú del día— y solo después dice dónde está el fichero. Es el único canal que se escribe entero en cada apertura de sesión, reinicio incluido.
- **Y el vigilante de cada mensaje ya nombra las dos skills**, en el mismo orden y con las mismas palabras que el bloque del `CLAUDE.md`.

## [1.28.0] - 2026-08-05

### Removed

- **El sistema de memoria anterior está borrado del repositorio.** Ya no estaba registrado desde la 1.27.0, pero sus ficheros seguían en disco. Se van dieciocho: el arranque viejo (`session-start-boot.py`), su aduana (`pre-validate-commit-trailers.py`), su vigilante de cierre (`stop-dod-check.py`), su generador de commits (`bin/git-memory-commit.py`), cuatro módulos de `lib/` (`boot_checks`, `boot_git_checks`, `boot_render`, `boot_migrations`) y once ficheros de test — **109 casos** que probaban código que ya no existe.
- **`lib/boot_health.py`, de 333 líneas a 65.** Solo sobrevive lo que consume `cache_sync_check.py`: `CACHE_BASE_DIR`, `_md5_file()` y `_latest_version_dir()`.
- **La documentación de la construcción pasa a `docs/deprecated/`** — la especificación, el plan, la deuda, los contratos de cada pieza y las dos pruebas en seco. Cuenta por qué las cosas son como son y guarda las decisiones del propietario con su fecha, pero no describe el presente. Cómo funciona la memoria hoy se lee en un solo sitio: la skill `unmassk-memory`.

### Fixed

- **Tres avisos del toolkit se habían quedado sin dueño al desenchufar el arranque viejo, y llevaban callados desde el cambio de guardia.** No eran de memoria y por eso no los heredó el arranque nuevo: que la copia instalada del plugin va por detrás del repositorio, la actualización automática de versión, y si el árbol de trabajo tiene cambios sin guardar. Pasan a `session-start-crew.py`, que es el hook del toolkit — no pueden vivir en `lib/memory/`, que tiene prohibido importar nada de fuera. Los tres hablan siempre, también cuando el resultado es cero: un chequeo que solo aparece cuando falla es indistinguible de uno que no se está ejecutando.
- **Y ese traslado trajo su propio fallo, cazado por un test que ya existía:** el chequeo de versión dispara el instalador, el instalador reescribe los bloques del `CLAUDE.md`, y al correr antes que la comprobación de esos bloques el hook acababa diciendo «todo en orden» sobre un fichero que él mismo había reparado un segundo antes. Ahora van después, y siguen siendo incondicionales.

## [1.27.1] - 2026-08-05

### Fixed

- **Un vigilante llevaba ciego y callado desde el renombrado de la skill de memoria.** `lib/hooks_doc.py` apuntaba a la carpeta de la skill vieja; al no encontrarla devolvía «no aplica» y el médico del sistema dejaba de imprimir esa fila **sin decir que había dejado de comprobarla**. La tabla de hooks activos se genera ahora dentro de `unmassk-memory`, y verifica: 7 invocaciones declaradas, 7 documentadas.
- **La aduana y el guardián de fusiones se lanzaban en CADA llamada a herramienta**, no solo en las de consola: al reescribir `hooks.json` se perdieron sus `matcher`. Dos procesos de Python de más por cada lectura, cada búsqueda y cada nota. Repuestos.
- **Cada skill declara su versión.** La de memoria y la de cierre de sesión son **2.0.0** — sustituyen enteras a las anteriores, no las extienden. Las cuatro que dejaron de llamar al sistema retirado suben a 1.1.0.

## [1.27.0] - 2026-08-05

### Changed

- **Cambio de guardia: los hooks del sistema de memoria nuevo entran en servicio.** `boot_launcher.py` sustituye a `session-start-boot.py` en `SessionStart`, y `customs.py` sustituye a `pre-validate-commit-trailers.py` en `PreToolUse`. `stop-dod-check.py` sale del `Stop`: hacía checkpoints automáticos y sugería cerrar, y el cierre ahora se pide. Sobreviven `session-start-crew.py` (mantiene los bloques del `CLAUDE.md`, que no son memoria), `pre-merge-gate.py` (decisión B16), `validate-memory-path.py` y `stop-dod-gate.py`.
- **Ningún fichero del sistema viejo se ha borrado todavía**, a propósito: solo cambia quién está registrado. Si el arranque nuevo falla en una sesión real, volver atrás es cambiar `hooks.json` y nada más. La limpieza va después de comprobarlo.
- **La aduana nueva nace apagada en un proyecto sin notas** y se enciende sola con la primera — así un proyecto recién instalado no se encuentra un guardián el primer día.

## [1.26.0] - 2026-08-05

### Added

- **New project-memory system, replacing the retired `git-memory` toolchain entirely.** Notes are organized into two zones each; nine commands are dispatched through one facade (`unmassk-toolkit/bin/gitmem note|work|wip|remove|next|search|zones|rezones|rule`) that never re-implements the underlying script — each subcommand runs `bin/memory/<name>.py` as a separate process by path, so a rejection from `gitmem note` is byte-for-byte identical to running `note.py` directly. `wip` is new: a checkpoint that writes without asking questions. `boot` is deliberately not a `gitmem` subcommand — `bin/memory/boot.py` fires on its own at session start instead of being invoked by hand. The old `git-memory` bash wrapper and `bin/git-memory-{bootstrap,gc,recall,uninstall,upgrade}.py` are gone, along with the hooks that only served them (`pre-task-recall.py`, `pre-memory-dedup-gate.py`, `precompact-snapshot.py`, `stop-close-session.py`) and the `gitto` agent.
- **Two new library modules**: `lib/memory/remote.py` (the remote-fetch logic the new boot uses) and `lib/memory/timefmt.py` (shared time formatting for notes and the boot report).
- **Alexandria gains a `close` mode** (the documentation half of closing a session — everything since the previous close, found by locating the last `[NEXT]` commit) **and a `foundation` mode** (bring a documentation set into existence where there is none, survey → propose → wait → build, only when asked for by name).

### Changed

- **Session close reworked around a transcript-reading agent instead of the model itself writing the summary.** `unmassk-close-session` now runs: clean up scratch files → record branches/issues/what's uncommitted in the conversation → Alexandria in `close` mode → a `general-purpose` agent, handed `references/close-agent-prompt.md` and a new `scripts/session_transcript.py`, that reads the actual session and writes one commit (Next as headline, context as body, every commit since the last close underneath). Consolidating memory and updating the CHANGELOG are explicitly no longer part of a close — they happen when the underlying event happens, not bundled into a wrap-up.
- **Boot rewritten:** now fetches all remote branches before rendering, and writes its full report to `.claude/.unmassk/boot-latest.txt` instead of injecting it into context — a hook's context budget was truncating exactly the tail that carries the memory-health warnings on any session with a lot to report.
- **`unmassk-flow`, `unmassk-project-lifecycle`, `unmassk-council`, `unmassk-grill` no longer call the retired memory system** — not just renamed references: `unmassk-council` records the real two-zone command with a discard reason per losing option (not just the runner-up); `unmassk-grill` persists what's left unresolved after an interview as an open question that resurfaces at boot instead of a list that died with the session; `unmassk-project-lifecycle` stores phase markers as memos instead of session closes (closes are one-per-session and were overwriting each other, phase C eating phase B); `unmassk-flow` also saves the resolved test command as a memo, since a fact that lives only in a config file isn't one a person can find. `unmassk-audit` needed no changes — confirmed already agnostic to the old system.

### Fixed

- **`unmassk-audit`'s 9 prompt templates no longer contradict the skill's own "stack-agnostic" claim.** Every template hardcoded `backend/src/[MODULE]/`, `npx vitest`, `npx prettier`, and `Zod` — so auditing a non-TypeScript project (this Python toolkit included) produced commands that could not run. Replaced with `[MODULE_PATH]` / `[TEST_CMD]` / `[FORMAT_CMD]` / `[LINT_CMD]` placeholders resolved from the project profile, the same mechanism `unmassk-flow` already uses (`unmassk-flow/SKILL.md` §"Project profile") — no new mechanism invented.
- **`unmassk-flow`'s `linear.md`/`test-first.md` pointed at sections of `standards.md` that don't exist.** Both cited "§7 (backend) and §27 (frontend)" for what to test; `standards.md` has no §27, and its real §7 is async/error-handling, not testing guidance. Repointed to the sections that actually hold this content (§1 tier system, §9's Real-verification checklist, §34 round-trip). Also dropped `test-first.md`'s external-attacker test items (manipulated token, privilege escalation) — out of this toolkit's declared threat model (`CLAUDE.md`: "no external attacker, the system against itself") — replaced with the internal-failure items §9/§4 actually cover.
- **`unmassk-close-session/SKILL.md`'s header promised decision-consolidation and a resume point the skill no longer provides.** Its 5 body steps are pure housekeeping (version/changelog/cleanup/branch hygiene/doc check) since the old memory system's decision-flush step was retired on `feat/memoria-v2`. Rewrote the frontmatter `description` to match the real body, and added an explicit note that the decision/resume-point capability returns at plan step 7.10 once the new memory system exists.
- **Root `README.md` and `.claude-plugin/marketplace.json` named a retired feature and a deleted script.** README's "Calibration" row described a memory-calibration mechanism that no longer exists (no `CALIBRATION.md`, no `unmassk-gitmemory` skill directory on this branch); removed rather than rewritten, since the replacement isn't built yet. The "Key scripts" table listed `git-memory-recall.py` at a path where the file no longer exists (`unmassk-toolkit/bin/`, confirmed via `ls`); removed. `unmassk-close-session`'s one-line description in the same table updated to match the SKILL.md fix above. `marketplace.json`'s `unmassk-toolkit` plugin description dropped the same "memory calibration" claim.
- **`unmassk-audit/prompts/cerberus.md` sent Cerberus to grade against a file that doesn't exist, with numbering and a scoring table that no longer match `unmassk-standards`.** Both templates cited `docs/ENTERPRISE-STANDARDS.md` (never existed in this repo) with old section numbers (§4.5/§4.3/§7/§1/§3/§6/§5/§11) and a `Security x3 / Error handling x3 / Structure x2 / Testing x2 / Maintainability x1` table — none of which match `standards.md`'s real dimensions. Repointed to `unmassk-standards`'s real sections and its real weighted table (Integrity ×3, Silent-failure/Error handling ×3, Structure ×2, Real verification ×2, Maintainability ×1). Also replaced the auth/routing-specific "verify middleware before reporting" rule (assumed a Node/Express route layout that isn't universal, and doesn't apply — this project's standards have no Security dimension) with a stack-agnostic "verify upstream context before reporting" rule. `unmassk-audit/prompts/argus.md`'s "focus areas" (OWASP, auth/authz design, SQL injection surface) carried the same external-attacker framing this toolkit's threat model explicitly excludes (`CLAUDE.md`: "no external attacker, the system against itself") — replaced with the internal-integrity surfaces Argus actually owns per `unmassk-standards/SKILL.md` (memory/persistence integrity, silent failure, concurrency, platform robustness), renamed from "security audit" to "integrity audit" throughout (both files + `SKILL.md`'s own step 4 description, findings-report scoring-dimension list, and standards-reference line, which had drifted to the same stale table and an OWASP claim `standards.md` doesn't back).

## [1.25.0] - 2026-08-01

### Added

- **Incident channel — the toolkit reports its own failures instead of swallowing them** (`lib/incidents.py`, wired at 6 call sites across 4 hooks). When a toolkit script raises, the failure is recorded with the concrete error, the **repo-relative** path (not the plugin-cache path, which is useless for going and fixing it) and the plugin version, to a **global** log at `~/.claude/.unmassk/incidents.jsonl` — global on purpose, because the failures that matter happen in the owner's *other* projects, not in this repo. Deliberately **no counter and no accumulation**: an identical incident is reported once per session and never re-counted, because a batched "you have 7 pending incidents" is exactly the report nobody acts on. Fail-open **at each call site**, not only inside the function, so a failure in the reporter can never take down the hook that called it. Noise counts as an incident too: a warning that repeats and is not actionable is a defect, not information.
- **The Active Hooks documentation is now generated from `hooks.json`, and the doctor fails if it lies** (`lib/hooks_doc.py`, `bin/hooks_doc_sync.py`). The table inside the marker delimiters is rendered from the real hook declarations; `git-memory-doctor.py` **errors** when the documentation names a hook that no longer exists and warns on missing or drifted entries. Replaces a hand-written table that had been describing hooks that were deleted months earlier.
- **Repo vs plugin-cache divergence check** (`lib/cache_sync_check.py`, wired into `bin/git-memory-doctor.py`). Warns when `hooks/`, `lib/` or `bin/` in the working tree differ from what the plugin cache actually executes. Known limitation, documented here rather than hidden: this check can only run once the cache is already in sync — it ships **in** the cache it is meant to police, so it cannot report its own obsolescence. It catches drift introduced *after* an update, not a stale install.

### Fixed

- **The commit gate had been dead for four months over one missing letter** (`hooks/pre-validate-commit-trailers.py:47`). It gated on `CLAUDE_CODE`; the environment variable the harness actually exports is `CLAUDECODE`, with no underscore. Every direct `git commit` / `git log` from Claude had been passing unblocked since `037e0cb`. The 7 test files covering it all passed because `tests/conftest.py` fabricated the variable that production never sets. Blocking of direct `git commit` is restored; blocking of `git log` is deliberately left off behind `BLOCK_DIRECT_GIT_LOG = False`, because the wrapper it would force people onto caps at 100 commits.
- **The doctor no longer checks against a hardcoded list that silently rots** (`bin/git-memory-doctor.py`). `EXPECTED_HOOKS` / `EXPECTED_SKILLS` were literals that drifted from disk; they are now derived at runtime (`expected_hooks()` / `expected_skills()`). When the expectation cannot be resolved, the doctor reports an explicit **"cannot verify" error** instead of the previous silent `0/0 ✅` — a green tick for having checked nothing.
- **The test suite gives the same result in both environments** (`tests/conftest.py`). `run_cmd()` now accepts `None` to *delete* an environment variable rather than only to set one, plus a `claude_env()` helper. The previous behaviour merged `os.environ`, so the same suite passed locally (where `CLAUDECODE=1`) and failed in CI — the mechanism that hid the four-month-dead gate above.

### Changed

- **The boot documentation now says what the boot actually does.** `unmassk-gitmemory/SKILL.md` and `CALIBRATION.md` claimed the boot "injects ALL existing memory"; it is a **budgeted sample** (single digits out of hundreds), and reading it as complete is why sessions concluded "there is no decision about X" without ever searching. Also corrected: per-message memory injection is documented as **removed**, not active; `Stop`/`PreCompact` output is documented as never reaching the model (measured over 8,700 hook executions); Bilbo is documented as **included** in the recall whitelist; and the dead-end freshness loop now names the label and anchor that actually exist (`agents/bilbo.md`).
- **`lib/managed_blocks.py` no longer generates a false claim into every project's `CLAUDE.md`.** The generated block stated that a memory-check hook fires on every user message. It does not — nothing is injected unless it is pulled. **This changes the boot contract text in every project that installs the plugin.**
- **`unmassk-core/SKILL.md`** now lists the real scoring dimensions of `unmassk-standards` (Integrity ×3, Silent-failure ×3, Structure ×2, Real verification ×2, Maintainability ×1) and the real 13 domain plugins instead of 7; **`README.md`** drops 9 claims that did not match the code.

### Removed

- **The channel-measurement probe is retired without having measured anything** (`hooks/_probe_canal.py`, 408 lines, and its 5 declarations across `SessionStart`, `PostToolUse`, `UserPromptSubmit`, `Stop` and `SubagentStop`). It was installed to determine which hook output channel actually reaches the model, and in three days it never recorded a single real invocation — its log file never came into existence. The cause is the same one this release documents: editing the plugin cache's `hooks.json` by hand does not register a hook with the harness. The `TRANSIENT_HOOKS` mechanism it introduced (`lib/hooks_doc.py`) is kept for a future probe; only this probe is removed. The question it was meant to answer — whether `hookSpecificOutput.additionalContext` reaches the model on `Stop` — remains open.

## [1.24.0] - 2026-07-26

### Added

- **`Memo:`/`Remember:` trailer content is now validated at the producer, before the commit exists.** `bin/git-memory-commit.py`'s wrapper checks every trailer's category against the enum (`MEMO_CATEGORIES` / `REMEMBER_CATEGORIES` — the latter promoted from a hook-local literal into `lib/constants.py`, one source of truth for both), enforces the `categoria - descripcion` shape, and rejects an empty description. Validates the same *sanitized* string that actually lands in the commit, not the raw one — a description made only of control bytes collapses to empty after sanitization and is caught, instead of slipping through a raw non-empty check. Fails closed: invalid input exits non-zero and no commit is created. Closes the "invented category → memory recall never retrieves it" silent-loss vector.

### Removed

- **Dead trailer-validation hook layer retired.** `hooks/post-validate-commit-trailers.py` deleted outright — it was 100% dead on the real commit path. `hooks/pre-validate-commit-trailers.py` cut from 233 to 55 lines: the trailer-content/type validation it attempted never actually fired (its commit-message extraction looked for a literal `git commit` invocation, which the wrapper never produces), so it is gone along with the dead hook. `hooks/hooks.json`'s registration for the deleted hook and `bin/git-memory-doctor.py`'s `EXPECTED_HOOKS` list were updated to match. **The one thing that layer did enforce for real — blocking direct `git commit`/`git log` Bash calls to force use of the wrapper scripts — is unchanged and still lives in `pre-validate-commit-trailers.py`.**

## [1.23.0] - 2026-07-25

### Added

- **Dead-end memory loop — Bilbo no longer re-investigates a subsystem from scratch.** New `deadend` category on the `Memo:` trailer (`lib/constants.py`) persists the discardable residue of an exploration — paths already ruled out for a subsystem — append-only, as `memo(deadend/<subsystem>)`, one physical line. `bilbo` joins the `pre-task-recall` injection whitelist (`hooks/pre-task-recall.py`), so it now receives those dead-ends automatically before exploring (deterministic input, not a "remember to check" rule); on the way out it emits a `DEAD-ENDS` block for the orchestrator to collapse into that single line and commit. `gitto` stays excluded on purpose — it IS the memory oracle, so injecting recall into it would be circular. Format and orchestrator responsibility documented in `unmassk-gitmemory` ("Dead-end memory") and `unmassk-core`. The `Memo:` validation error (`hooks/pre-validate-commit-trailers.py`) now lists valid categories generated from `MEMO_CATEGORIES` instead of a hardcoded string, so it can't drift out of sync again the next time a category is added.

### Fixed

- **A newline embedded in a trailer value no longer silently truncates it on the next read (T1).** `bin/git-memory-commit.py`'s wrapper now runs every trailer value through `sanitize_trailer_value()` before writing, collapsing embedded CR/LF/control bytes to a space. Previously, a raw newline inside a value (e.g. free text an agent wrote) split the trailer across multiple physical lines — the read path only ever recognized the first line, silently losing everything after it on every future recall.

## [1.22.1] - 2026-07-25

### Fixed

- **Gitto Mode C tombstones must cite entry TEXT, not commit hash** (`agents/gitto.md`). Boot matches `Resolved-Memo:`/`Resolved-Remember:` tombstones by *normalized entry text* (`lib/boot_memory.py`), but the doc told Gitto to write them "citing all cleared hashes" — so a `Resolved-Remember: <hash>` matched nothing and the entry stayed live as a permanent "ghost" (this was the source of a lingering, already-supposedly-retired `remember(claude)` found this session). The doc now mandates the exact entry text as the trailer value (hash goes in `Why:`), and clarifies it's one tombstone commit per entry (a trailer key appears at most once). Completes the crown-format fix from 1.22.0.

### Changed

- **`unmassk-gitmemory` documents `file_lock()`** for concurrent writers of a shared file, replacing the now-stale "no file lock — last-write-wins, not yet fixed" note (fixed in 1.22.0). The Filesystem Safety Pattern section now points future `.claude/` code at the lock, the `.claude/.unmassk/` lock-path convention, non-reentrancy, and the check-outside-then-lock pattern.

## [1.22.0] - 2026-07-25

### Added

- **Cross-platform `file_lock()` closes the CLAUDE.md lost-update race (T1).** The atomic writer (`mkstemp`+`os.replace`) already prevented a crash from leaving CLAUDE.md empty/partial, but not the *lost update* between two concurrent read-modify-write cycles (two overlapping boots, boot + upgrade, …): each reads the same content, each edits only its own managed block, and whichever `os.replace()` lands last silently discards the other's change. New `file_lock(target_path, lock_path=None)` in `lib/git_helpers.py` (POSIX `fcntl.flock` `LOCK_EX`; Windows `msvcrt.locking` retrying **only** on the contention errno and re-raising any permanent error instead of looping forever; lazy platform imports; always released; documented non-reentrant) plus `claude_md_lock_path()` — a single shared lock path under the already-ignored `.claude/.unmassk/` so it never pollutes `git status`. All 3 managed-block writers (`hooks/session-start-crew.py`, `lib/install_apply.py::_update_claude_md()`, `bin/git-memory-uninstall.py`) now do a cheap read/compare *outside* the lock and only escalate to lock → re-check → write when a write is actually needed — so a no-op boot in a read-only project dir stays a graceful no-op instead of crashing. Reviewed (Cerberus), broken and re-hardened (Moriarty found 2 read-only regressions + 1 Windows infinite-loop deception, all closed); 9 tests with real cross-process subprocesses.

### Changed

- **`REMEMBER_GC_THRESHOLD` 8 → 16** (`lib/boot_render.py`). After moving mis-scoped rules into skills, the surviving `remember(claude)` entries are legitimate, distinct behavior rules — the old threshold fired as a false positive for a mature toolkit, not on real noise. `MEMO_GC_THRESHOLD` unchanged (10).
- **More mis-scoped `remember(claude)` rules moved into their skills** and retired from global memory: "default to the named crew" and the crew/frontmatter delegation scope → `unmassk-core` (with a clarification that the "orchestration files are yours" rule is about the toolkit's *own* layer, not a product's frontmatter). Also fixed a class of ghost entries that a prior consolidation "retired" by citing commit *hashes* instead of the entry text (so the tombstone never matched and the entry stayed live).
- **Gitto Mode C crown-commit format documented exactly** (`agents/gitto.md`). Consolidation was emitting inert crowns (`Crown: Memo:` with a trailing colon, and no `Memo:`/`Remember:` trailer on the crown itself), so crowns never registered. The doc now gives the exact `--trailer` command and the two failure modes to avoid.

## [1.21.1] - 2026-07-25

### Changed

- **Four behavior rules that were mis-scoped as global `remember(claude)` moved into their proper always-loaded skills.** They described toolkit behavior, so they belonged in a skill (a hard, always-loaded instruction), not in global memory that travels to every unrelated project and inflates the `remember(claude)` accumulation warning. `unmassk-core` gains an **"Autonomy under delegation"** section (when the user delegates the decision, execute the best option — including design gray areas — without bouncing it back as a question; confirm only for structural/irreversible/security/unverifiable changes) plus a **"resolve collateral obstacles; finish the ask"** rule. `unmassk-close-session` strengthens step 5 (**the release is part of finishing, not an optional follow-up — don't defer it or ask permission to publish**) and step 2 (**a discard is not done while its front still has live memos/`Next:`** — tombstone them in the same close, and cross-check DECISIONS before re-offering a candidate). The five originating memory entries were retired via `Resolved-Remember` tombstones (`remember(claude)` count 20 → 15, verified against the real boot merge path). Also folds in Gitto consolidation Pass 7 (3 crown entries: delegation, non-atomic CLAUDE.md write T1, #61 reopened).

## [1.21.0] - 2026-07-23

### Removed

- **External-attacker-framed tests retired (~9.6k lines), aligning the suite with the project's signed threat model — "the system against itself," not an external attacker (`CLAUDE.md`, "What security and tests are for in THIS project").** Four attacker-only files deleted outright: `test_control_byte_injection.py`, `test_security_regression.py`, `test_hardlink_reject_guard.py`, `test_manifest_hardlink_reject.py` (~8.5k lines). Six mixed files had only their attacker-framed classes excised, integrity-framed coverage kept (~1k lines): `test_boot_output.py` (symlink-write-protection / control-byte-injection classes gone; boot-section, log-file, surrogate-escape coverage kept), `test_crossplatform_symlink_guard.py` + `test_crossplatform_symlink_guard_hardening.py` (TOCTOU-as-attack classes gone; cross-platform parity/data-loss/fd-leak coverage kept), `test_issue63_manifest_read_hardening.py` (`.claude`-symlink-bypass class gone; `RecursionError` fail-safe kept), `test_hardening_recall.py` (anti-injection framing gone; fail-open/format-robustness kept), `test_stop_dod_gate.py` (metacharacter-as-attack class gone; command/infra-error/JSON-validity coverage kept). No production code was touched by this cut — the guarded functions themselves (`verify_path_within_project()`, `open_no_follow_symlink()`, hard-link rejection, `sanitize_trailer_value()`) remain live; only the attacker narrative around their tests changed. The only code edit was dropping one stale pre-1.0 filename (`git-memory-dashboard.py`) from the `OLD_BIN_FILES` migration lists in `lib/install_inspect.py` and `bin/git-memory-uninstall.py`. Suite: 1373 → 1078 passed, 2 skipped, still green.

### Fixed

- **Two integrity-test gaps the cut had opened were closed in the same pass.** `sanitize_trailer_value()`'s (`lib/parsing.py`) documented control-byte contract (`\x1b`/`\x7f`/`\x1c`-`\x1f`/`\x85` neutralization + `<memory-data>` fence-marker stripping) had lost all unit coverage — restored as `TestSanitizeTrailerValueControlByteContract` in `test_parsing_consolidation.py`. `render_scopes_section()`'s (`lib/boot_git_checks.py`) single-line-render-under-corrupted-input guarantee, previously covered only by a deleted attacker-framed class, is restored as `TestScopesRenderStaysSingleLine` in `test_boot_output.py`, reframed around internal data corruption instead of an external attacker. 15 dead comments across `lib/`, `hooks/`, and `tests/` citing the deleted test files were corrected to describe the real reason the referenced code exists.

### Added

- **`unmassk-standards` §34.6 — "confirmation is an independent read-back, not the command's own echo".** New first-class silent-failure criterion under Pillar 1 (§34, "no truth is asserted against itself"): when code claims an action on an external system took effect, the confirmation must come from reading the resulting state back through a channel *independent of the command*, never from the command's own success/ACK; if it genuinely can't be read back, the outcome is reported *commanded/unverified*, never upgraded to *confirmed* (T1 if faked). Generalizes to runtime what 3d ("never invent a measurement — read the caliper") and electronics ("the device confirms, or it isn't done") already do; scoped so it does not become a blanket read-after-write on every production write (distinct from §34.3).
- **`unmassk-electronics` robotics branch gains a testable sensor gate (`sensor_gate.py`).** The branch was prose-only; it now ships the robotics equivalent of micro's `serial_verify.py` — a pure `evaluate_gate` (before/after vs expected delta within a tolerance band, `increase`/`decrease`/`either`), a median anti-noise helper, a **deferred/pluggable sensor-read layer** (no `smbus`/`RPi.GPIO`/`board`/`adafruit_*` import), a never-crashing CLI, and the honest `commanded/unverified` status when no sensor reading is available. **The gate logic is tested in simulation (69 tests, green); integration with real VL53L0X/HC-SR04/MPU6050 hardware is explicitly marked UNVERIFIED in the module docstring** — a deliberate note, not a hidden gap. Wired into the Plugin Tests CI.
- **`unmassk-frontend` gains AgentBrowser as its browser tool (MCP).** When a frontend task needs to *observe or drive the rendered UI* — validate how it looks on screen, scrape, navigate, fill a form, check a flow, log in — the `frontend-react` skill now routes to AgentBrowser (`agent-browser` — Rust CLI + MCP server, drives Chrome over CDP, accessibility snapshots with compact `@eN` refs), registered **on demand** (`unmassk-frontend/.mcp.json` ships empty; Claude runs `claude mcp add agent-browser` the first time the skill needs it, then the user restarts — see `references/agent-browser.md`) and a scoped rule + router row in the skill. **Visual validation = capture → Read → judge:** screenshot to the scratchpad, `Read` the PNG, evaluate it — a shot nobody reads proves nothing. **Single exception: tests stay on Playwright** (AgentBrowser is not a test framework). Scope is deliberately *observe/drive the running UI*, not "all frontend work" (writing code does not invoke it). Ships a **preflight**: verify `agent-browser --version >= 0.31.2` (the version with the MCP server), else `npm i -g agent-browser@latest && agent-browser install`; if install fails, STOP and report — never fake a check. The skill leans on AgentBrowser's own version-matched `agent-browser skills get core` for command syntax instead of duplicating (and staling) it. Verified on Windows: `open`/`snapshot`/`screenshot`/`close` and the `agent-browser mcp` `initialize` handshake on 0.31.2. New reference: `unmassk-frontend/skills/frontend-react/references/agent-browser.md`. Pressure-tested by a 5-advisor council (found and fixed: over-broad mandate, install/permission deadlock, non-actionable capture-and-judge, and a false CLI-only premise — the published npm latest is 0.31.2 with MCP).

- **New plugin `unmassk-electronics` v1.0.0 — agent-driven electronics for makers.** A multi-branch plugin (core + 3 branch skills) for building, programming, and *verifying real hardware* — never "the code compiled, so it works". One prime directive across all branches: **never report a hardware task done until the device itself confirms it** (a serial assertion, a pin read-back, a sensor read) — the physical-world version of the silent-failure the toolkit exists to prevent. Branches, built micro → Pi → robotics: **electronics-micro** (ESP32/RP2040/STM32 firmware via PlatformIO; the build→flash→serial-assert loop, gated by `pio test`'s structured Unity results or platformio-mcp's `agent_flash_monitor_verify`, plus our own pyserial `serial_verify.py` fallback and an ESP32 crash-triage reference); **electronics-pi** (Raspberry Pi / Linux SBC driven over SSH with gpiozero, gated by an independent `pinctrl` read-back and systemd health checks — records the RPi.GPIO-deprecated / lgpio-kernel-bug gotchas); **electronics-robotics** (motors/servos/sensors on top of the other two, gated by reading a sensor *after* every move — the Adafruit CircuitPython stack spans ESP32 and Pi with one API). The core skill carries the shared method, a **per-device profile** (persisted, re-read each session), and a **START-gated toolset** (nothing installs until a project is actually electronics). Honest throughout: the agent writes and verifies code but nobody wires or solders the hardware, and the young MCP ecosystem is backed with deterministic CLI fallbacks. Original method synthesized from three parallel verified research passes — see `unmassk-electronics/PROVENANCE.md`.
- **`design-gate` — a skill frontmatter collision linter (`unmassk-toolkit/bin/design_gate.py`).** Parses every `SKILL.md`'s YAML frontmatter (`name` + `description`) and flags two classes of routing collision between skills: (1) the same distinctive trigger term or quoted example phrase claimed by 2+ skills' "mentions any of:" / "asks to '...'" clauses, and (2) `Use when NOT` anomalies — a dangling reference to a skill name that doesn't exist, or a mutual contradiction where two skills both defer the same ground to each other while nobody actually claims it. A heuristic, best-effort linter over the existing informal prose convention, not an NLP system. Ships with `unmassk-toolkit/design-gate-allowlist.json` — the 12 baseline collisions found in the real repo (10 keyword, 1 phrase, 1 mutual-contradiction, spanning compliance/db/electronics/design/seo/marketing) are allowlisted with a human-reviewed reason per entry (documenting *why* the overlap is legitimate — e.g. code-scan vs document-drafting for the compliance skills, or a plain acronym homonym for "MRR") in a separate `_reasons` block the parser never reads, so nothing is "green by decree." An allowlisted finding is still printed in every report (tagged `[allowlisted]`, never hidden); a genuinely new collision is tagged `[NEW]` and fails the gate (exit 1). Wired into `toolkit-ci.yml` as its own step, right after the test suite. 68 tests in `unmassk-toolkit/tests/test_design_gate.py`.
- **"Objective profile" pattern — fixed constraints of an external system, persisted as `memo`, not a new file.** New "Objective profiles" section in `unmassk-gitmemory`'s SKILL.md: work against an external system with constraints you must not rediscover every session (a specific device, a deploy target, an unstable third-party API, a client's prod quirks) persists each fixed constraint as a `memo` scoped to the objective (`memo(device/esp32-s3)`, `memo(deploy/prod-eu)`, `memo(api/stripe)`) — no new file, template, or read/write script; the boot's existing re-read and the recall hook surface the scoped memos for free. `unmassk-electronics`'s "per-device profile" (previously prose describing "a persisted file" with no actual mechanism) is now reconnected to this pattern: `memo(device/<id>)`, documented in the core skill plus the 4 places that recorded device constraints (`electronics-pi`'s SKILL.md/`setup.md`/`gpio-gate.md`, `electronics-micro`'s `platformio-patterns.md`). First real instance seeded to prove the pattern isn't just documented: `memo(device/rpi)` (commit `c6a8d9c`) recording the Pi kernel 6.6.45 `lgpio` GPIO read-back bug.
- **New plugin `unmassk-3d` v1.0.0 — reality-first CAD for 3D printing.** One method skill that designs 3D-printable parts (cases, brackets, mounts, holders, enclosures) which *fit real objects*, from real measurements — never invented ones. Prime directive: a fit-critical dimension comes from a **caliper**, overall shape from a **3D scan**, envelope from a **spec** — a guessed millimetre is a part that does not fit (the "system doesn't harm itself" rule applied to the physical world). Pipeline with two hard gates: capture → **scale-calibration gate** (never trust an imported scan's scale) → parametric design as code (CadQuery/OpenSCAD) → **watertight gate** (a broken STL does not pass) → validated STL. Blender is integrated (not a separate skill) and driven live over an MCP bridge (`ahujasid/blender-mcp`, registered **on demand** — `unmassk-3d/.mcp.json` ships empty; Claude runs `claude mcp add blender` the first time the skill needs Blender, then the user restarts — see `references/blender-mcp.md`) for measuring/cleaning scans and organic modelling, with a working-directory guard (self-harm prevention, not attacker-hardening). Ships three scripts — `validate_mesh.py` (the watertight gate, 27-test contract, all green), `setup_cad_env.py` (the START installer for the canonical open-source toolset), and `run_cadquery.py` (the execute→JSON→iterate runner that auto-chains the gate) — plus five references (setup, scan-pipeline, printability, blender-mcp, cad-patterns). Capture is an **iPhone 17 Pro** (Scaniverse) + calipers; printing (slicer) is deferred until a printer exists, so the skill stops at a validated STL. Accuracy limits are stated honestly (no iPhone delivers sub-mm from a scan alone; settle it with an empirical caliper-vs-scan test, not from memory). Method original; stands on open-source tools (CadQuery, build123d, trimesh, manifold3d, Blender, OpenSCAD/BOSL2, admesh) and informed by prior skills (flowful-ai/cad-skill, EdwinjJ1/3d-print-skill, andreahaku/openscad_claude_skill) — see `unmassk-3d/PROVENANCE.md`.

### Changed

- **6 more plugins switch their MCP servers to on-demand registration (`unmassk-electronics`, `unmassk-frontend`, `unmassk-compliance`, `unmassk-marketing`, `unmassk-media`, `unmassk-seo`)** — extending the pattern already validated on `unmassk-3d`. Each plugin's `.mcp.json` is now `{"mcpServers": {}}`: the server no longer connects at every Claude Code boot regardless of whether the skill is used. Instead, the first time a skill actually needs its MCP, Claude registers it itself (`claude mcp add <name> --scope user ...`) and tells the user to restart — restart is the only manual step, and only when told. Covers `platformio` (electronics-micro), `agent-browser` (frontend-react — already in active use, unaffected functionally), `better-i18n` (compliance-i18n), `composio` (marketing), `media-pipeline` (media-image-gen), and all 5 SEO servers (`dataforseo`, `ahrefs`, `semrush`, `google-search-console`, `pagespeed`). Each skill/reference gained an "Activate the MCP" section with the exact registration command, restart step, where to get the API key (none for platformio/agent-browser/media-pipeline's optional keys), and — added after a council review flagged the silent-failure risk — a fail-loud availability check at the top of the flow ("check its `mcp__<server>__*` tools are actually available; if not, register and tell the user to restart — never proceed as if the tool were there") across all 7 blocks (3d, electronics, frontend, compliance, marketing, media, seo), so a skill can never quietly work without its tool instead of registering it. A few stale claims that predated this change were corrected in the same pass: `electronics-micro/references/setup.md` said the `.mcp.json` "already declares" the server; `frontend-react`'s SKILL.md and `agent-browser.md` said the plugin's `.mcp.json` "registers the server"; `unmassk-marketing`'s README said "the plugin configures one MCP server"; `unmassk-seo`'s README said "the plugin configures 5 MCP servers" — all rewritten to describe on-demand registration instead of eager connection.

### CI

- **Maker-plugin script suites now run in CI (`plugin-tests.yml`).** The `unmassk-3d` (`validate_mesh`, `run_cadquery`) and `unmassk-electronics` (`serial_verify`) test suites, previously run by hand, now run on every push/PR touching those plugins — a separate ubuntu-only workflow that installs the pip-only deps (numpy/trimesh/manifold3d/pyserial/cadquery), kept out of the core Toolkit CI so its fast pure-Python suite stays fast. Verified green end-to-end (both suites pass on the runner).

### Fixed

- **Boot RESUME no longer resurfaces `Next:` items already superseded by a later `context()`.** `extract_memory()` (`lib/boot_memory.py`) now tracks the timestamp of the most recent `context()` commit in the scan window and drops any `Next:` trailer **without** a linked `#issue` whose commit predates it — a dead Next from an earlier checkpoint could previously sit right next to the current one in the boot briefing, with no way to tell which was live. `Next:` items **with** a `#issue` are untouched here (their closed/open state is still resolved downstream from GitHub, in `lib/boot_render.py`). If no `context()` exists yet in the window, filtering fails open (unchanged prior behavior — nothing is dropped). Also hardened: the `MAX_PENDING` cap is now applied *after* the cutoff filter instead of during collection, so the two constants (`SCAN_DEPTH`/`MAX_PENDING`) can no longer silently let a live Next get capped out behind already-dead ones.
- **Boot TIMELINE now shows the 20 most-recent commits across *all* branches** (was the last 10 on the current branch only). `get_timeline()` (`lib/boot_git_checks.py`) switched from `git log HEAD` to `git log --all` and `BOOT_MAX_TIMELINE` from 10 to 20, so on any machine the briefing surfaces what's being worked on repo-wide, not just the checked-out branch — without changing the current branch. The existing unrelated-upstream guard (`exclude_remote` / `_is_safe_remote_name()`, issue #49) was threaded into the timeline scan so a foreign `refs/remotes/*` upstream can't leak unlabeled commits into the list.
- **Boot now fetches *all* remote branches and lists them in a new `BRANCHES` section.** The startup fetch (`_run_hardened_fetch`, `lib/boot_git_checks.py`) went from a single-branch refspec to `+refs/heads/*:refs/remotes/<remote>/*` **with `--prune`**, so on any machine you see what's being worked on repo-wide — the fetch only downloads refs, it never changes your current branch or touches the working tree. A new `BRANCHES (<remote>):` section in the briefing lists each remote branch with its last commit (sha + relative time), newest first, the current branch marked, capped at 20 with an explicit "(N more…)" line. All fetch hardening (timeout, disabled credential prompting, `--no-tags`, fail-open) is unchanged, and the unrelated-upstream guard (`_is_safe_remote_name()` + `remote_name` nulled upstream) keeps a foreign remote's branches out of the list. `--prune` is load-bearing: without it a branch deleted upstream would linger in the list forever even after a successful fetch (caught in review, pinned by regression test).
- **Memory readers no longer collapse a transient `git` failure into a false "no memory here" result (issue #61).** All 9 production read sites — `recall.py`'s `_scan_commits()`, `boot_memory.py`'s `extract_memory()` and `extract_glossary()`, `boot_git_checks.py`'s `get_timeline()` and `get_last_context_time()`, `git_helpers.py`'s `commits_since_last_consolidation()`, `bootstrap_commits.py`'s `scan_recent_commits()` (both its commit and author scans), and `precompact-snapshot.py`'s `extract_memory_from_log()` — now go through a shared `run_git_read_retrying()` helper (`lib/git_helpers.py`): up to 3 attempts with a short fixed backoff, bounded by a wall-clock deadline that caps every attempt's own timeout to whatever budget remains, so a hanging `git` process can never balloon a single call site past roughly its normal timeout. A genuine empty result (`rc=0`, no output) still returns on the first attempt and is never mistaken for a failure. Where a stderr breadcrumb is logged on failure, it now only fires after retries are exhausted, so a transient that recovers never prints a false alarm. Root-caused by House from the Ubuntu-CI flakiness reported in #61 (`git log` exiting 128 under runner load) — the fix targets the production silent-loss bug the flakiness was exposing, not the test harness. Read-path only; no write-path `run_git()` call was touched. Suite: 1110 passed, 2 skipped.
- **CLAUDE.md's managed blocks are now written atomically — a crash mid-write can no longer leave the file empty or partial.** All 4 writers (`hooks/session-start-crew.py`, `lib/install_apply.py`, `bin/git-memory-uninstall.py`) previously opened CLAUDE.md with plain `open(path, "w")`, which truncates the file the instant it's called, before any new content lands — a kill/crash/full-disk error in that window left CLAUDE.md empty or half-written, silently. Fixed with a new opt-in `atomic=True` flag on `open_no_follow_symlink()` (`lib/git_helpers.py`): content is written to a `tempfile.mkstemp()` temp file in the same directory, then `flush`/`fsync`/`close`/`os.replace()` — the original file is only ever touched by the final atomic rename, and is left untouched on any failure before that point. Preserves the existing file's permission bits across the rewrite (warns to stderr, non-fatal, if the chmod itself fails) and opportunistically sweeps its own abandoned temp files older than 1 hour on each write, so repeated crashes don't accumulate orphaned `.tmp` files. Suite: 1129 passed, 2 skipped (up from 1110).

## [1.2.1] - 2026-07-14

### Fixed

- **`unmassk-design` frontmatter disambiguation — trigger collisions resolved and cross-skill name-routing removed (design follow-up from the v1.2.0 ship).** The 7 skill descriptions poached each other's trigger keywords, so several branches auto-activated for the same request. Each contested token now has a single owner: **GSAP + parallax → `design-scroll`**, **stagger → `design-animation-formats`**, **Framer Motion → `design-motion`**, **particles → `design-3d`**. Every `Use when NOT:` clause that routed to a sibling skill by name (`use design-scroll`, `route to skills/unmassk-design`, …) was rewritten in in-scope-only terms, enforcing the project rule that a skill's frontmatter describes only its own trigger. Validated by a 5-advisor council plus a 20-prompt routing probe (20/20 landed on the intended skill). Also resynced `marketplace.json`'s `unmassk-design` description (was stale single-skill-era text) to the multi-branch reality. Deferred candidate: a `design-gate` collision-linter reusable across the multi-skill plugins.

## [1.2.0] - 2026-07-14

### Changed

- **`unmassk-design` revamped from a single skill into a 7-skill multi-branch plugin.** The core (`unmassk-design` — design systems, color, typography, layout, accessibility, UX writing, agentic UX) is unchanged; 6 new specialist branches were added: `design-motion` (Emil Kowalski craft principles + Apple fluid-interfaces physics + Motion.dev/Framer Motion/React Spring + advanced CSS, from `emilkowalski/skills`, `motion-dev-animations-skill`, `claudedesignskills`, `css-animation-skill` — all MIT/Apache 2.0), `design-3d` (Three.js/R3F/Babylon.js/PlayCanvas/WebXR/PixiJS + Blender/Substance pipeline, from `claudedesignskills`, Apache 2.0), `design-scroll` (GSAP ScrollTrigger/Locomotive Scroll/Barba.js/AOS, from `claudedesignskills`), `design-animation-formats` (Lottie/Rive/Anime.js + Magic UI/React Bits, from `claudedesignskills`), `design-taste` (named aesthetic directions — brutalist/minimalist/high-end, redesign-to-premium, image-to-code, brand-kit generation, from `taste-skill` by leonxlnx, MIT), and `design-flutter` (Flutter UI layout/theming/animation, from `claude-flutter-ui-skills` by Naimehossein77, MIT). Every branch is a condensed, rewritten fusion in this plugin's own voice — none of it is a byte-faithful lift from any single source. Full source mapping in `unmassk-design/PROVENANCE.md` and `unmassk-design/CREDITS.md`.

## [1.20.4] - 2026-07-14

### Fixed

- **Skill-router trigger dict reconciled with the current skill descriptions (CI was red).** `SKILL_TRIGGER_PHRASES` in `lib/skill_router.py` still carried two phrases removed by the #76 frontmatter rewrite (`unmassk-grill` "the request is ambiguous" → "help me define this"; `unmassk-project-lifecycle` "pick up the project" → "pick up where we left off"), so those phrases no longer matched the live descriptions and the router could mis-nudge on them; the description-drift guard test correctly caught it. Also retired 6 obsolete tests in `test_control_byte_injection.py` that exercised the per-message recall push-injection surface removed in #69 (the control-byte threat model CLAUDE.md explicitly retires), and refreshed a drifted `[memory-check]` marker assertion in `test_encoding_contract.py` (the real cp1252 no-crash contract it guards is unchanged). Toolkit CI green again on Windows + Ubuntu.

### Changed

- **Release protocol now requires a `plugin-dev:plugin-validator` PASS before shipping a plugin — mandatory for a brand-new plugin.** Added to both the machine-facing protocol (`unmassk-gitmemory` SKILL → "Releasing a toolkit plugin") and the human walkthrough (`docs/RELEASING.md`, new precondition + checklist items). The validator catches the new-plugin footgun class: a `SKILL.md` citing a `references/*.md` file that was never written, a plugin missing from the root `marketplace.json`/`README.md`, manifest/marketplace version drift, or a malformed frontmatter. Runs as an agent (spawn `plugin-dev:plugin-validator`, or load its definition from the `claude-plugins-official` cache and run a `general-purpose` agent with those instructions).

### Added

- **New plugin `unmassk-humanizer` v1.0.0** — one skill (`humanizer`) that rewrites text so it stops reading as AI, in **English and Spanish**, without flattening the author's own voice. A fusion (not a byte-lift) of three MIT skills — `blader/humanizer` (the Wikipedia *Signs of AI writing* pattern catalog + the false-positives/human-signals brake), `lguz/humanize-writing` (the three-pass process — structure → vocabulary → texture — plus named voices), and `kjmagnan1s/anti-slop` (the three modes rewrite/detect/ingest, the protect-list seam, the living corpus, transition iteration, context profiles) — reorganized into a single method in one voice. Pattern lineage traces to Wikipedia's *Signs of AI writing* (CC BY-SA 4.0); examples rewritten in our own words. The **Spanish catalog (`patterns-es.md`) is original work** — muletillas, calcos del inglés, and machine-translation tells that do not map from English; no source skill covers Spanish, and this is the core reason the plugin exists. Validated by a 5-advisor council; council fixes applied — the em-dash quality gate is now language-aware (a correct Spanish *raya* no longer fails the gate), two worked before→draft→audit→after examples (EN+ES) were added to recover the adversarial self-audit loop, and the protect-list and living corpus ship **empty on purpose** (filled by use, never pre-seeded with invented content). Deferred candidate: routing the living corpus into git-memory for cross-machine, self-growing tells.
- **New plugin `unmassk-pentesting` v1.0.0** — offensive + defensive security engagement toolkit, 30 skills. `pentesting-engagement` is the method spine: an orchestration loop over the crew (source/recon first, three hypotheses per batch, delegated execution, blind validation, coverage-by-confirmed) driven by a per-engagement `SCOPE` contract (an explicit allowlist the operator confirms — discovered assets outside it are never auto-attacked) and a blind-validation step where fresh `general-purpose` agents (a refuter quorum + a reproducer, seeded with role files, never shown the attack theory) must independently confirm a finding before it reaches the report. The other 29 skills are per-domain techniques spanning web, recon, network/system, cloud, specialized surfaces (mobile, blockchain, cryptography, AI/LLM, reverse engineering, social engineering), blue-team/DFIR, CTF/bug-bounty (HackerOne, HackTheBox, CVE PoC/risk-score), and offensive tooling. Technique content is lifted byte-faithful (MIT, per-file attributed) from `communitytools` by Transilience AI, pinned at upstream commit `e659245`; the upstream Python orchestration engine was deliberately not ported — the method is re-expressed as prose over the existing crew. Auto-trigger and blind validation have been verified live against 2 of the 30 skills (recon, injection) on a real target; the full 30-skill trigger sweep is not yet exercised.

## [1.20.2] - 2026-07-13

### Changed

- **Recall switched from push to pull — the per-message memory channel is now a static banner, not an injected memory block (#69).** The `[memoria relevante…]` / `<memory-data>` block that was pushed into *every* user message (imprecise relevance gate — it routinely surfaced decisions/memos unrelated to the message), plus the repeated `[memory-check]` reminder and the per-message `[git-memory] root:` line, are removed from `user-prompt-memory-check.py`. The per-message channel is now a single compact banner that points at on-demand recall (`git-memory-recall.py "<terms>"`) and folds in the save reminder; canonical memory (crowns + active decisions) still loads at boot. Also removed the now-dead injection code (`<memory-data>` framing, per-invocation fence-nonce, the `secrets` import) after confirming `recall.py` stays live for its other four consumers, and deleted 16 stale tests that asserted the removed output.

## [1.20.1] - 2026-07-13

### Changed

- **`unmassk-project-lifecycle` and `unmassk-grill` frontmatter descriptions rewritten so the orchestrator actually reaches for them (#76).** Both skills never fired in practice: their descriptions opened with prose describing *what the skill does* and buried the trigger, so the orchestrator scanned the opening, saw no match to the current situation, and moved on. Rewritten to the shape every auto-triggering skill already uses (`unmassk-flow`, the domain skills) — lead with `Use when the user asks to "…"` concrete trigger phrases, then an explicit **`Also invoke AUTOMATICALLY when <situation> — do not wait to be asked`** clause (the missing piece that makes a skill fire proactively), then what it does last. lifecycle now triggers on *opening work on a project not yet situated this session* (dropping the self-defeating "whenever it's unclear what state the project is in", which is never true when boot hands over full memory); grill on *WHAT to build being under-defined*, with a concrete one-sentence trigger test. Neither description references another skill by name — a frontmatter states only its own trigger.
- **`unmassk-close-session` gained a backlog-reconciliation step.** Step 8 previously closed only issues finished *this* session; it now also sweeps the whole open backlog, cross-references each open issue against the commit history (`git log --grep="#<n>"`) and git-memory, and — after confirmation, citing the evidence commit — closes issues resolved in a *previous* session but never closed (the recurring leak where a fix commit references an issue but no `Resolved-Next` trailer fired, so GitHub stayed open).

## [1.20.0] - 2026-07-13

### Changed

- **`unmassk-project-lifecycle`'s START branch rewritten into a full new-project protocol** — the method for taking a project from an idea to a fully prepared state *before a line of business code*. The lightweight `SKILL.md` now routes to three references: **`start.md`** (the director — six phases: define/grill + PRD → behavior/three-layer walkthroughs → visuals/mockups → foundations decide → build base → close, with a **Phase-0 triage** so trivial/small projects skip the heavy phases), **`foundations.md`** (a **tool-agnostic** enterprise foundations catalog — ~60 foundations *by name* across 12 blocks, Mandatory vs Conditional, opt-out, plus a map of which toolkit skill already delivers each block), and **`walkthroughs.md`** (the three-layer walkthrough method: sees / does / DB × four viewpoints, every error branch, approve-before-next). Fixes a Detection routing bug — *memory-but-no-code* is now "project mid-preparation, resume at last phase", not "rare/ask". Audited by a 5-advisor council; kept intentionally as a **prose checklist (no enforcement gate)**, with calibration, catalog-in-bulk presentation (auto-accept Mandatory, prune Conditionals by shape), and walkthroughs↔mockups reconciliation added from the verdict.

## [1.19.14] - 2026-07-12

### Changed

- **`unmassk-flow`'s Verify sequence rewritten to a single deterministic agent pass** (#70): the old "repeat until clean" loop caused 30+ Cerberus↔Ultron rounds (≈60 total) in a real project. Now every agent runs once, no loops: **Cerberus + Argus in parallel — always** (Argus is no longer gated to "big" features) → **Ultron fixes once** (reviewers don't re-review) → **Dante** writes/hardens tests **against the real dependency** (real DB/seam/files; mock only what genuinely can't run — §34.5) → **Moriarty** (always) tries to break **code AND tests** → **Ultron repairs code + Dante repairs tests** → **Yoda scores once and never re-runs** (below the bar → Ultron fixes his points, no second verdict). The mechanical backstop for a bad fix is the full test suite at Close, not a re-run of reviewers. Added a **Trivial** triage tier: a mechanical 1-file / few-line edit with no logic, security, seam, or new behavior (a doc-text change, a typo, a rename, a constant) goes to Ultron alone with no pipeline. Bilbo's lane row corrected (he investigates the codebase **and** researches the web). Applies identically to linear (Ultron first) and test-first (Dante's acceptance contract first).

## [1.19.13] - 2026-07-12

### Changed

- **`unmassk-flow` reworked so the pipeline survives being run in a non-toolkit project** (#70): the Step 7 pre-merge gate no longer hardcodes `cd backend && npx vitest run` (which broke in any non-Node repo). Flow now resolves the project's own test command — read from the profile, else detected from the repo (`pytest`, `go test`, `cargo test`, a `Makefile` target…), else it stops and asks. Crucially, the resolved command is **written to `.claude/git-memory-config.json` (`test_command`), which the existing `stop-dod-gate` hook runs automatically** — turning "run the tests" from prose into a real gate; `unmassk-project-lifecycle` now records it at project start. Also added: a "who NEVER does what" lane table inside Flow (Ultron never tests, Dante never investigates), a one-feature-in-flight gate expressed as a real `git`/`grep` check rather than a reminder, tightened deviation rules (no speculative "auto-add infrastructure"), a fix to the Quick-triage vs Dante contradiction, and inline glosses for jargon a fresh reader wouldn't know. Reviewed by a 5-advisor council; the design was verified against the actual DoD-gate mechanism before landing.

## [1.19.12] - 2026-07-12

### Changed

- **`unmassk-flow-stack` renamed to `unmassk-scaffolding`.** The skill had nothing to do with the Flow pipeline — it's the new-project scaffolding wizard (pick a stack, generate the project) — but sharing "flow" in the name conflated the two. Renamed the skill directory, its frontmatter `name`, the routing references in `unmassk-core` and `unmassk-project-lifecycle`, the CLAUDE.md protocol-menu generator, and the `skill_router.py` trigger key (which surfaces the name to the orchestrator every message). Git history keeps the old name; recover it from there if needed.

### Fixed

- **File write-paths no longer leak `UnicodeEncodeError` on a lone surrogate** (#54): `open_no_follow_symlink()` and its cross-platform twin hardcoded `errors="strict"`, so a string carrying a lone surrogate (possible from malformed git output) raised `UnicodeEncodeError` instead of honoring the "only `OSError` escapes" contract. The guard helpers gained an `errors=` passthrough (default unchanged), and the one write-path that assembles free-form git-derived text (`write_boot_log`) opts into `errors="backslashreplace"` — always ASCII-safe and re-readable. Defensive/T3; unreachable from real callers today.

## [1.19.11] - 2026-07-12

### Fixed

- **The media plugin no longer litters every project with an empty `generated-images/` folder** (#75): the image-generation MCP server (and its CLI twin) created its output directory eagerly in the `ImageStorage` constructor, so simply starting the server in any project with the toolkit installed left a `generated-images/` folder in that project's root — even when no image was ever generated. The eager `mkdirSync` is removed; the directory is now created lazily, only when an image is actually saved (that write path already ensured its parent directory). Real image generation is unchanged.

## [1.19.10] - 2026-07-12

### Removed

- **The BM25 skill-discovery gate is retired.** `scripts/skill-search.py`, the `catalog.skillcat` files across all domain-skill folders, and the skill-search half of the `pre-task-recall` hook are gone from the working tree (memory-recall injection in that hook is untouched — only the skill-routing half was removed). Reason: with `skillListingBudgetFraction` raised to 0.05, the orchestrator now has every domain skill's frontmatter (name + description) in context at boot and picks the correct one by criterion when it delegates to a crew agent — the BM25 keyword guess is no longer needed and was producing false positives on long, keyword-dense meta prompts. The retired system is archived, not deleted from history: tag `bm25-skill-gate-1.19.9` points to the last commit with it intact.

### Fixed

- **Version-mismatch banner no longer suggests a downgrade** (#64): the boot `STATUS` line compared installed vs plugin version as raw strings, so a project with a *newer* version installed than the plugin code was told to "update" to the older one. It now uses the same numeric semver comparison as the real upgrade oracle (`needs_upgrade`), suggesting an update only when the code is genuinely newer than what's installed.
- **`_semver_key` no longer misorders non-ASCII digit identifiers** (#58): the release-version comparator routed Unicode digit characters (e.g. full-width `１２３`) through its numeric branch via a bare `isdigit()`; it now requires `isascii() and isdigit()`, so those sort as alphanumeric. Defense-in-depth — the external version input was already gated by an ASCII-only regex.

## [1.19.9] - 2026-07-12

### Changed

- **Ultron's agent definition reworked to close the gap the reviewers kept flagging.** Ultron now runs a mandatory pre-flight before writing a line — reads the imports/exports/call-sites of what it will touch, searches for an existing helper to reuse instead of duplicating, traces the real producer↔consumer seam, and declares its surface ("N files, M call-sites, K consumers, reuse"). "Minimal" is redefined as the smallest *surface* that fully meets the standard, never the smallest *effort*. Every line must be production-final on the first pass (no drafts, no `TODO: fix later`). The Exit Gate gained goal-backward wiring checks (every new export has a real call-site, every route is mounted, every import is used) — while the round-trip *test* stays Dante's, never Ultron's. The old "mode" concept, which overloaded one word for two different axes, is split into **Build order** (linear/test-first, set by the orchestrator) and **Work type** (implementation/fix/security/refactor, from the task). A new "Observations for the orchestrator" channel lets Ultron surface improvements it spots but must not build unasked.
- **Ultron never writes tests, in any mode — always Dante.** Previously Ultron added tests itself in linear mode; that path is removed. In linear build order Ultron instead flags in its report when tests are missing so the orchestrator routes Dante, without ever writing them.
- **The Analysis Paralysis Guard no longer counts files.** Its stop condition is now a state of knowledge — Ultron stops reading the moment it knows what the change needs (the imports it will touch and what they derive), not after an arbitrary file count. Required pre-flight reading never trips the guard; only aimless reading past that point does.

### Fixed

- **Skill-injection gate false positives cut down.** The gate that injects a domain skill when the orchestrator delegates to a crew agent was firing on long, keyword-dense meta prompts (reviewing an agent definition, fixing a Python test) that have no real domain. The top match must now clear a higher trigger, and any secondary skill must clear both an absolute floor and a relative margin against the top — so a scattered, flat score distribution (the signature of a false positive) no longer gates. Tests reconciled and mutation-checked.
- **Corrected the skill-loading docs in `unmassk-core` and `unmassk-gitmemory`.** Removed the false claim that crew agents auto-discover domain skills via their own BM25 search on boot; the orchestrator injects them via the gate, and that flow (deny + paste the block, anti-loop marker, fail-open, "expected, not an error") is now documented so a fresh session doesn't misread the `⛔ SKILL GATE` block as a failure.

## [1.19.8] - 2026-07-12

### Added

- **Per-message discipline banner for the orchestrator**: the message hook now prints a small boxed reminder at the top of every user turn — `NOT YAPPING!` (no filler, answer the minimum) and `DON'T ASSUME` (if it's in the conversation, say it; if not 100% sure, verify it in memory/code/web; never make it up). It's context the orchestrator sees each turn, not something shown to the user.

## [1.19.7] - 2026-07-12

### Added

- **Domain skills now reach crew agents automatically, enforced by a gate** (issue #68): when the orchestrator delegates to a crew agent, the `pre-task-recall` hook runs the skill searcher over the task and, if a domain skill matches, **blocks the spawn** and hands the orchestrator a `[DOMAIN SKILL]` block (skill name, path, "read this now") to paste into the agent's prompt before retrying. It's an obligation, not a reminder — the agent cannot be launched without it. An anti-loop marker lets the retry through; low/no match or any searcher failure passes through untouched (fail-open — a broken searcher can never block a spawn). Bilbo and Gitto are excluded, same as memory recall.

### Fixed

- **Subagent memory injection was silently doing nothing** (issue #68): the `pre-task-recall` hook gated on `tool_name == "Task"`, but the real tool name in the hook payload is `"Agent"` — so the hook bailed out on every invocation and never injected the project-memory footer it was supposed to. The check now accepts `Agent`/`Task`, reviving memory injection into crew-agent prompts as a side effect of the skill-gate work.

## [1.19.6] - 2026-07-12

### Added

- **Domain skills are now auto-injected into a crew agent's prompt when it's invoked** (issue #68): the BM25 skill searcher worked but nothing ever ran it, so domain skills (PostgreSQL, Docker, GDPR, etc.) were never actually loaded in practice. The `pre-task-recall` hook — which already fires when the orchestrator launches an agent — now also runs the searcher over the task and, if a skill scores above the confidence threshold, injects a `[DOMAIN SKILL]` block (name + path + an imperative "read this now") into the agent's prompt as its own block, separate from the memory footer. Skill search and memory recall are computed independently, so a brand-new task with no project memory still gets its skill. Fail-open on every error (searcher timeout, malformed output, low score) — the hook never blocks or delays a Task. Same agent exclusion as recall (Bilbo/Gitto never get it). Each outcome leaves a stderr breadcrumb so a future failure is never silent.

## [1.19.5] - 2026-07-11

### Changed

- **Auto-upgrade check moved from every message to once per session start** (issue #63): the check that keeps a project's installed plugin content current used to run on every single message (two file reads, and occasionally a subprocess, per reply); it now runs once when a session starts. Trade-off: running `/plugin update` mid-session is picked up on the *next* session start rather than the very next message.
- **Two boot-time migrations retired** (issue #63): the one-time repairs that moved old `.claude/` runtime files into `.claude/.unmassk/` and untracked legacy generated JSON files only mattered for installs older than ~4 months and no longer run on every boot. The one still needed for very old installs now lives only in the explicit `git memory upgrade` path.
- SessionStart hook timeout raised 30s→45s to give boot enough headroom for the above.
- The `[memory-check]` reminder shown after every message was shortened to about a third of its previous length (same guidance, less text).

### Fixed

- **Auto-upgrade no longer mistakes a fully current install for an outdated one** (issue #63): the check used to look for a literal string inside CLAUDE.md's managed block that never actually appears in real installs — only in test fixtures — so an up-to-date CLAUDE.md still looked outdated and triggered a reinstall. It now compares against the real canonical content instead of a hand-typed marker.
- **Skill-drift warning no longer fires in ordinary user projects** (issue #63): the check compared a project's cached plugin skills against the toolkit's own *source* repo, but in projects that only have the plugin installed from the cache (no source checkout), the path arithmetic accidentally pointed back at the same cache — producing false "drift" warnings with nothing to fix. It now only runs when a real toolkit source checkout is present.
- **CLAUDE.md's self-repair for a corrupted managed block no longer risks deleting nearby user notes** (issue #63): if a managed block's END marker went missing (e.g. from a bad merge), repair now removes only the dangling marker line and reinserts the full block in its place, instead of any heuristic that could reach into surrounding text.
- **A failed install/upgrade no longer marks itself as successful** (issue #63): if any install step fails, the manifest is left as it was (absent or stale) instead of being stamped with the new version — so the next boot still sees the install as incomplete and retries it.

## [1.19.4] - 2026-07-11

### Fixed

- **Transient git failures during memory scans no longer vanish without a trace** (issue #61): the boot/recall/snapshot code paths that shell out to `git log` — `_scan_commits()` in `lib/recall.py`, `extract_memory()`/`extract_glossary()` in `lib/boot_memory.py`, `scan_recent_commits()` in `lib/bootstrap_commits.py`, `commits_since_last_consolidation()` in `lib/git_helpers.py`, and the precompact snapshot hook — used to collapse any transient subprocess failure straight to an empty result (`[]`, `{}`, `None`, `0`), indistinguishable from "no memories exist". These call sites now opt into `run_git()`'s existing stderr-breadcrumb diagnostic, so a real git failure prints a trace instead of presenting as silence. The fail-safe return values themselves are unchanged — diagnostics only, no behavior change.
- **Stabilized the Ubuntu-CI-only flaky test family** (issue #61): the tests in `test_consolidation_trigger.py`, `test_drift.py`, and `test_recall.py` that build large commit-history fixtures (hundreds of commits) were intermittently failing only on `ubuntu-latest` under resource pressure, with opaque assertion messages and no trail back to the cause. They now retry (bounded, anti-vacuity-checked — a genuinely broken result still fails after every attempt) and, on exhaustion, run a raw-git diagnostic to distinguish a transient git subprocess flake from a real logic bug. Local `run_git` test doubles used across these suites now accept `**kwargs` so they stay compatible with future keyword-only additions to the real `run_git()` signature. 16 new tests in `test_issue61_breadcrumbs.py` cover the new stderr breadcrumb behavior directly.

## [1.19.3] - 2026-07-11

### Fixed

- **Boot `MEMORY:` stamp no longer labels fresh memory as a failure** (issue #60): when the boot's background fetch was skipped because memory was already confirmed synced within the last 5 minutes, the banner read `MEMORY: LOCAL — fetch skipped (rate-limit, Ns ago)` — worded as a failure even though memory was genuinely fresh. That state now renders `MEMORY: remote (synced Ns ago)`, grouped with `remote (fetched Ns ago)` as a confirmed-fresh state; `LOCAL` is reserved for real failures (no fetch this boot, no remote, never synced).

### Changed

- **Boot fetch freshness signal moved off `.git/FETCH_HEAD`** (issue #60): the rate-limit gate and the `MEMORY:` stamp used to read `.git/FETCH_HEAD`'s mtime, which a *failed* fetch also refreshes (git truncates it to 0 bytes on failure) and which any unrelated `git fetch` (IDE, mirror) touches too — both could produce a false "synced" claim. The boot now writes its own success stamp (`lib/boot_fetch_stamp.py`, `.claude/.unmassk/boot-fetch-stamp.json`, gitignored, per-machine) immediately after ITS OWN fetch against the resolved memory upstream exits 0, keyed to the remote's real URL (not just its local alias) plus branch and a schema version — a stamp copied between unrelated repos sharing a common `origin`/`main` naming convention (template scaffolding, backups) is never trusted as evidence of a real sync.
- **Toolkit CI gained real Windows coverage for the boot fetch path**: a unified `Popen` interceptor (`tests/_git_intercept.py`) replaces the previous PATH-shim approach, which silently no-opped on Windows because `CreateProcess` only resolves `.exe` and ignores `PATHEXT`. The fetch-gate and freshness-stamp tests now exercise real subprocess behavior on all three CI platforms instead of being skipped on Windows.

## [1.19.2] - 2026-07-10

### Fixed

- **Boot memory fetch now reliably completes** (plugin/boot): `FETCH_TIMEOUT_SECONDS` (`lib/boot_git_checks.py`) raised from 3s to 10s. The old 3s bound let the SessionStart fetch time out under normal network latency, so `origin/<branch>` stayed stale, the boot never detected local was behind, and `resolve_boot_memory()` served a stale *local* briefing instead of reading the fresh one from origin (observed live: a boot showed a 19h-old `Next:` while local was actually 36 commits behind). 10s stays a bounded timeout (boot never hangs) with fail-open unchanged; the "LOCAL — unverified" freshness stamp still fires as the safety net if a fetch genuinely fails. Two hung-fetch tests that used an 8s stall calibrated to beat the old 3s bound were re-derived from the constant so they no longer break silently.

## [1.19.1] - 2026-07-10

### Fixed

- **Carriage-return transport forgery in the git-log→memory pipeline** (issue #59): `run_git()` (`lib/git_helpers.py`) and the independent inline `git log` subprocess in `bin/git-memory-log.py` both decoded with `text=True` universal-newline translation, collapsing any `\r` in a commit body to `\n` before the parser saw it — a raw carriage return in a trailer could forge or erase a memory line. Both now capture raw bytes and decode manually (no newline translation), preserving `\r` literally. Verified end-to-end through a real subprocess round-trip against `git cat-file`.
- **Unclosed `memory-data` marker after control-byte truncation** (issue #59, SEC-LOW-17): `scan_trailers_memory()` (`lib/parsing.py`) truncates a line at the first `\x1c`/`\x1d`/`\x1e`; when that byte fell inside a `</memory-data…>` marker it dropped the closing `>`, leaving a dangling marker the fence stripper could not match. A trailing-remnant sweep now neutralizes it.
- **Quadratic-time input bound on generic-tag stripping** (issue #59): `_strip_generic_tags()` (`lib/bootstrap_commits.py`) is capped to 4096 chars before the tag regex runs, bounding a crafted-long-subject O(n²) case.

### Changed

- **Best-effort framing nonce on the memory-injection markers** (issue #59): the `UserPromptSubmit` recall block and the pre-compact snapshot carry a per-invocation nonce alongside their delimiters. The injection-fence hardening in #59 is intentionally **partial** — the threat requires repo write access (a hostile commit), which is outside the single-user trust model this toolkit targets. The remaining hardening (nonce bound *inside* the delimiter, invisible-Unicode/Cf stripping, disguised-marker regex, and a length bound on the new unclosed-marker sweep) is documented and deferred as risk-accepted.

## [1.19.0] - 2026-07-09

### Security

- **Hard-link bypass of the symlink-safe write guard closed** (issue #53): the two symlink-safe open helpers, `open_no_follow_symlink()` (`lib/git_helpers.py`) and its Windows-path twin `open_no_follow_symlink_fallback()` (`lib/_symlink_safe_open.py`), gain an opt-in `reject_hardlinks=True` parameter. When set, both check `os.fstat(fd).st_nlink` on the already-open file descriptor (TOCTOU-safe — the check runs after the symlink guard has already resolved the real file, not before) and raise `OSError` (`errno.EMLINK`) if the file has more than one link, deferring truncation in write mode so a rejected file's shared inode is never destroyed before the reject fires. Applied to the 5 file categories the toolkit generates and writes to itself — `boot-log-latest.txt` (`hooks/session-start-boot.py`), `glossary-cache.json` read and write (`lib/boot_glossary_cache.py`), `.session-booted` (`hooks/user-prompt-memory-check.py`), `manifest.json` across install/doctor/upgrade (`lib/install_apply.py`, `bin/git-memory-doctor.py`, `bin/git-memory-upgrade.py`), and the upgrade backup (`bin/git-memory-upgrade.py`) — closing SEC-HIGH-001 plus a variant the first pass missed on the upgrade backup path. Deliberately NOT applied to user-owned files (`CLAUDE.md`, `settings.json`, `.gitignore`), where a legitimate hard link between worktrees is valid and should not be rejected. `git-memory-upgrade.py`'s backup caller now wraps `create_backup()` in try/except so a rejected hard link at the backup path fails the upgrade cleanly instead of crashing uncaught. New contract tests: `tests/test_hardlink_reject_guard.py`, `tests/test_manifest_hardlink_reject.py`. Originally deferred out of the v1.16.1 cross-platform fix pending its own dedicated review (decision `51a3c44`); closed here.

## [1.18.0] - 2026-07-09

### Added

- **Toolkit CI on GitHub Actions** (issue #51): `.github/workflows/toolkit-ci.yml` runs the full test suite on both `windows-latest` and `ubuntu-latest` (`fail-fast: false`, so a failure on one OS never hides the other) — there was previously no automated channel to verify Windows results at all. Getting the matrix green surfaced two more real bugs, fixed in the same push: `get_timeline()`/`get_last_context_time()` (`lib/boot_git_checks.py`) used the same fragile `%aI` + `datetime.fromisoformat()` date parsing described below and were unified onto `%at` (unix epoch); 140 sites across 16 test files were missing an explicit `encoding="utf-8"` on subprocess/file reads, which only worked by accident locally under `PYTHONUTF8=1`. A follow-up fix added `errors="replace"` to the subprocess reads that consume externally-produced, locale-dependent output (`git`, `bin/release.py`) — the strict `utf-8` decode from the first pass broke on Windows runners without `PYTHONUTF8` set, since their locale output real accented characters as cp1252 bytes.
- **Deterministic test suite on CI runners** (issue #50): `tests/conftest.py`'s `run_cmd()` now injects a fallback git author/committer identity into every subprocess it spawns, applied only to a repo that has no identity configured anywhere (system, global, or set explicitly by that specific test) — on a runner with no git identity at all (e.g. GitHub Actions with `useConfigOnly = true`), every `git commit` issued by the test helpers previously exited 128 silently (the return code went unchecked), leaving dozens of tests asserting against repos that silently had zero commits. `tests/test_release.py`'s import of `bin.release_helpers` was also made independent of the working directory — it previously only worked by the accident of `pytest` inserting the cwd on `sys.path`, breaking with `ModuleNotFoundError` under a different cwd on Windows/CI.

### Fixed

- **Fragile git-log date parsing unified** (issue #55): `bin/git-memory-gc.py` and `bin/git-memory-doctor.py` each carried a byte-for-byte duplicate of the same `%aI` + `datetime.fromisoformat()` parser, which could silently degrade to `None` (dropping `Last:`/timeline ages) depending on the runner's git version. Both now call a shared `lib/date_parsing.py:parse_date()`, switched to `%at` (unix epoch) for robustness. `lib/bootstrap_commits.py` deliberately keeps `%aI` — its date is only ever displayed, never parsed, so the readable format stays. Hardened through adversarial review (Argus/Moriarty): an explicit type guard for non-`str` input, a length cap ahead of `int()` conversion, and rejection of non-ASCII Unicode digit strings (accepted by `str.isdigit()`, but never emitted by a real `git log %at`). `lib/boot_git_checks.py:time_ago()` picked up the same `OverflowError` guard and Unicode-digit rejection for consistency with the new shared parser. A malformed-date edge case — a hand-crafted commit with an out-of-range (year 10000+) timestamp, invisible to `gc.py`'s and `doctor.py`'s stale-commit heuristics with no trace — is an accepted, documented low-risk residual rather than a fix: it requires repo write access already inside the trust boundary, and the failure direction is always safe (under-reports, never deletes). Suite: 1026 tests green.
- **Windows console encoding crashes** (issue #52): none of the toolkit's 25 entry points (`bin/`, `hooks/`, `scripts/skill-search.py`, the flow-stack scaffold script) forced UTF-8 on stdout/stderr, so any non-ASCII `print()` under a Windows cp1252 console raised an uncaught `UnicodeEncodeError` — a partial install, a memory hook crashing on every prompt, or a commit that reported failure despite succeeding. New `lib/encoding_guard.py`, fail-open, applied at all 25 entry points with `errors="replace"` so a broken console encoding can no longer block the operation itself.

## [1.17.0] - 2026-07-07

### Added

- **Multi-machine boot memory freshness** (issue #49): the `[git-memory-boot]` SessionStart hook now detects when local git-memory is behind another machine's and reacts instead of silently showing stale state.
  - The previous unconditional `git fetch --quiet` (5s timeout) is replaced by a hardened, gated, rate-limited fetch (`fetch_memory_ref()`, `unmassk-toolkit/lib/boot_git_checks.py`): skipped entirely on a repo with no unmassk-toolkit memory installed, skipped again if `.git/FETCH_HEAD` is younger than 5 minutes, bounded to a 3s timeout, and run with `GIT_TERMINAL_PROMPT=0`, a neutralized askpass (POSIX and Windows), `BatchMode=yes`, and every configured credential helper disabled so it can never hang on an interactive prompt. Fail-open on every branch — network down, a missing remote, or a bug in the fetch path never delays or crashes the boot.
  - A `MEMORY:` provenance/freshness stamp now renders near the top of both the short stdout banner and the full boot-log file (`render_memoria_stamp()`): `remote (fetched Ns ago)`, `LOCAL — fetch skipped (rate-limit, Ns ago)`, `LOCAL — last fetch Ns ago, unverified`, `LOCAL — unverified (never synced with origin)`, or `LOCAL — upstream unrelated (no shared history), not shown`.
  - When local is strictly behind its upstream, a `PULL DIRECTIVE:` line proposes `git pull` as the first action of the session — or, if the working tree is dirty, explicitly says not to pull so nothing gets clobbered (`_build_pull_directive_lines()`).
  - `resolve_boot_memory()` (`unmassk-toolkit/lib/boot_memory.py`) now reads Next/Decision/Memo/Remember/Blocker straight from `origin/<branch>` when local is strictly behind (each entry labeled ` [source: remote]`), and from both sides (remote side labeled) when the branches have diverged — never silently merged into one truth. The glossary cache (`boot_glossary_cache.py`) now keys its freshness on both local HEAD's sha and origin's, so a cache built before the remote moved is no longer served as fresh.
  - Repo-identity guards added during hardening: `check_upstream_shares_history()` confirms the resolved upstream actually shares commit ancestry with local HEAD (`git merge-base`) before any of its memory is read or labeled "remote" — an unrelated repo that happens to share a branch name can no longer leak its memory into this project's boot, and the PULL DIRECTIVE is suppressed in that case (git itself would refuse the merge). The live remote name is re-resolved (`git remote get-url`) instead of assuming `origin`, so a renamed remote (`git remote rename origin upstream`) still works. A negative `.git/FETCH_HEAD` age (clock skew across machines) is treated as "not fresh" instead of permanently suppressing future fetches.
  - `git-memory-commit.py` now prints a warn-only (never blocking) notice before a `decision`/`memo`/`remember`/`context` commit if local is behind its upstream, reading the existing `@{u}` tracking ref — no extra fetch is performed for this check.
  - Cross-platform hardening: `run_git()` (`unmassk-toolkit/lib/git_helpers.py`) now kills the whole descendant process tree on a timeout, not just the direct `git` child — POSIX via process groups (`os.killpg`), Windows via `taskkill /F /T /PID`. One residual is documented rather than silently present: a Windows descendant that re-parents itself via Task Scheduler (`schtasks`) or a Windows service escapes `taskkill /T`'s PID-tree walk — accepted as a known limitation (reproduced live by Moriarty), since a process that self-detaches to a system service already implies the invoked `git` binary is fully compromised.

### Fixed

- `time_ago()` (`unmassk-toolkit/lib/boot_git_checks.py`) could raise an uncaught `OverflowError` on an out-of-range or malformed timestamp instead of degrading to `"unknown"` like every other malformed-input case — added to the existing `except` clause alongside `ValueError`/`TypeError`/`OSError`.

## [1.16.1] - 2026-07-06

### Fixed

- **Windows startup crash**: `os.O_NOFOLLOW` is POSIX-only, so on Windows every call into `open_no_follow_symlink()` (the symlink-safe file guard used by the boot hook, `doctor`, and several per-message hooks) raised an `AttributeError` — not `OSError`, so it escaped every existing `except OSError` and crashed instead of failing safe. `open_no_follow_symlink()` and its twin `_symlink_safe_open.open_no_follow_symlink_fallback()` (`unmassk-toolkit/lib/git_helpers.py`, `unmassk-toolkit/lib/_symlink_safe_open.py`) now branch on platform: POSIX keeps the original atomic `O_NOFOLLOW` open; Windows uses a two-step guard instead (`os.path.islink()` pre-check, then an `lstat`/`fstat` identity comparison, with the truncate deferred until after that check passes) that raises `OSError` on the same symlink-escape attempts the POSIX path blocks, never `AttributeError`. Two Windows-only residuals are accepted and documented in the docstring rather than silently present: a brand-new path has no prior identity to compare against (accepted TOCTOU gap), and a hard link to a file outside the repo is undetectable on any platform by either guard (deferred to a dedicated change per decision `51a3c44`). The `0o600` mode-bits docstring claim was also corrected — it only denies group/other access on POSIX; on Windows the file inherits its containing directory's ACL instead.
- **Encoding**: git output, hook subprocess calls, and a JSON file read across `unmassk-toolkit/lib/git_helpers.py` (`run_git`), `version.py`, `boot_health.py`, and four hooks (`session-start-crew.py`, `stop-dod-gate.py`, `user-prompt-memory-check.py`, `validate-memory-path.py`) now pass `encoding="utf-8"` explicitly instead of relying on the OS default — Windows defaults to `cp1252`, which broke or mangled (mojibake) any accented character or emoji in a commit message, and previously only worked by accident under `PYTHONUTF8=1`. `scripts/skill-search.py`'s `SKILL_SEARCH_EXTRA_DIRS` env var now splits on `os.pathsep` instead of a hardcoded `:`, so it works on Windows (`;`-separated paths) as well as POSIX.
- `run_git()` now reports a `UnicodeDecodeError` to stderr with a diagnostic message instead of silently collapsing it into the same generic `(1, "")` result as every other git failure, so a genuine decode failure is distinguishable from "git itself failed" during troubleshooting.

## [1.16.0] - 2026-07-06

### Fixed

- The `[git-memory-boot]` SessionStart hook (`unmassk-toolkit/hooks/session-start-boot.py`) could lose its `Next:` instruction when the full boot briefing was large: the Claude Code harness only previews a small prefix of SessionStart's stdout, so an oversized briefing (commonly caused by one bloated `context()` commit subject) silently cut off exactly the part telling Claude what to do next. There is no safe size threshold, so stdout is now unconditionally a short banner (status, branch, and a pointer) for every repo, regardless of size, while the complete, nothing-shortened briefing is always written to the fixed path `.claude/.unmassk/boot-log-latest.txt` for Claude to read instead. If writing that file fails for any reason, the hook falls back to printing the full content inline rather than pointing at a file that doesn't exist.
- `git-memory-commit.py` now rejects (`exit 1`, no commit created) a `context()` commit whose full subject line (emoji + `type(scope): message`) exceeds 100 characters, telling the caller to shorten the message and move the rest into `--body` — closing off the root cause of the truncation bug above at the source, instead of only mitigating its symptom. Other commit types are unaffected.

### Security

- **Parent-directory symlink escape**: every existing symlink guard in this codebase (`open_no_follow_symlink()`) only protected the final path component being opened — none protected the parent directories. If `.claude` itself (or a subdirectory like `.unmassk`, `agent-memory`, `skills`, `bin`, `hooks`) were a symlink committed in a malicious repo, `os.makedirs()`/`open()` silently followed it, so file operations that looked scoped to the project could actually read or write anywhere on disk — including overwriting the user's real `~/.claude/settings.json` or deleting another plugin's hook registrations. Closed with a single new chokepoint, `verify_path_within_project()` (`unmassk-toolkit/lib/git_helpers.py`), which resolves the full path via `realpath` and rejects it unless it stays inside the project root — mirroring the pattern `hooks/validate-memory-path.py` already used for the same bug class. Applied across every read/write site in `bin/`, `hooks/`, and `lib/` that touches `.claude/` (9 files call it directly), found via a mechanical AST sweep cross-checked independently by Argus.
- **Untrusted commit-derived content reaching Claude's context unsanitized**: text sourced from git commits — controllable by anyone able to commit to the repo — flowed into the boot briefing without going through the existing sanitizer in several places (commit scope labels, branch names, timeline entries, crowned decision/memo text, manifest version strings, and more). Closed by applying `_sanitize_trailer_value()` consistently at every render site in `unmassk-toolkit/lib/boot_render.py` and `boot_memory.py`.
- **Fake log-entry injection via control bytes**: the boot hook parsed `git log` output using `\x1e`/`\x1f` as field/record separators, both forgeable from inside a commit body — a crafted commit could inject bytes that made the parser see fabricated decision/memo/remember entries that never existed. Fixed by switching to `git log -z` (`unmassk-toolkit/lib/boot_memory.py`), which uses a real NUL byte as the record separator — NUL cannot appear in a git commit message, so it can't be forged.

### Changed

- `hooks/session-start-boot.py` split from 1278 lines into a single 330-line entry point plus 6 cohesive modules under `unmassk-toolkit/lib/`: `boot_memory.py` (memory/glossary extraction, further split into `boot_glossary_cache.py`), `boot_render.py` (section rendering), `boot_checks.py` (thin compatibility shim), `boot_health.py` and `boot_git_checks.py` (health/git status checks), and `boot_migrations.py`. `bin/git-memory-bootstrap.py` (936→143 lines) and `bin/git-memory-install.py` (541→252 lines) were split the same way into `lib/bootstrap_*.py` and `lib/install_*.py` modules. `bin/git-memory-doctor.py` (518 lines) and `bin/git-memory-upgrade.py` (537 lines) remain above the usual 500-line convention — both accepted as documented exceptions rather than split further this round.

## [1.15.0] - 2026-07-04

### Added

- Project startup quality floor: `unmassk-project-lifecycle`'s START branch (`unmassk-toolkit/skills/unmassk-project-lifecycle/SKILL.md`) gains a new step, before the first feature commit on a brand-new project, that confirms the scaffold has a working test command (even trivial), a lint/format config, and — if the stack implies secrets — a `.env.example`. Any missing piece is no longer silently skipped: it must be captured as an explicit `decision()` (e.g. "deferred: no test runner yet"). A small, concrete slice of the larger "solid project startup guide" idea, which otherwise stays deliberately frozen in the roadmap pending the memory/consolidator system maturing — a validation council found this specific piece doesn't depend on that maturity, so it shipped now.

### Changed

- Gitto Mode C (Consolidator, `unmassk-toolkit/agents/gitto.md`) now automatically retires superseded `Memo`/`Remember` entries when it crowns a group, instead of relying on the orchestrator to notice a near-duplicate mid-conversation and tombstone it by hand. It reuses the existing, already-tested `Resolved-Memo:`/`Resolved-Remember:` trailer mechanism — still additive, since a tombstone is itself a new commit, nothing is edited or deleted. `Decision` entries remain untouchable, unchanged. A 5-advisor council review closed three real gaps before this shipped: each cited source is checked individually before being tombstoned (a crown can be right on average while one specific source still carries a caveat the crown didn't capture — that source is left alone); the very first time this new tombstoning behavior fires anywhere in the project now requires Bex's approval, separate from the existing first-crown-per-scope gate; and a narrow new rule lets a truly isolated Memo/Remember (one that never grouped with anything, so it could never be crowned) be retired on its own once it's gone 6+ months with zero references, capped at 1-2 per pass.

## [1.14.0] - 2026-07-04

### Added

- Per-message skill-router nudge: the `[memory-check]` hook (`unmassk-toolkit/hooks/user-prompt-memory-check.py`) now checks every user message — not just the first — against a lightweight trigger-phrase table (new `unmassk-toolkit/lib/skill_router.py`) covering all 9 protocol skills, sourced directly from each skill's own frontmatter `description`. On a match it appends an informational `[skill-router] Possibly relevant skill(s): ...` line — purely a nudge, it never blocks or denies. A permanent drift-guard test loads the live SKILL.md descriptions at test time and fails if the trigger table ever falls out of sync with them again.

### Changed

- Protocols menu generator (`unmassk-toolkit/lib/managed_blocks.py`) extended with `unmassk-flow`, `unmassk-audit`, and `unmassk-flow-stack` — previously excluded from the CLAUDE.md Protocols menu under an old "only list installed+referenced skills" policy that no longer applied now that all three are fully shipped and tested; a skill Claude can't see in the one menu it reads every session can't be routed to reliably.

### Fixed

- Frontmatter trigger-phrase collisions between protocol skills — the actual mechanism Claude Code uses to pick which skill to invoke — fixed after a 5-advisor validation council tested 12 adversarial phrases against an earlier pass: `unmassk-grill` vs `unmassk-council` still tied on "two valid interpretations" vs "which option" (`unmassk-grill` is now scoped to ambiguity about WHAT to build, `unmassk-council` to choosing between already-scoped approaches to an already-understood goal); `unmassk-council`'s own description contradicted itself (claimed "nothing decided" while also excluding undefined requirements) — clarified that its idea-generation compares approaches to a goal that's already understood, not defines the goal; `unmassk-project-lifecycle` now defers to `unmassk-grill` when scope is undecided and to `unmassk-flow-stack` when a concrete stack is already named (previously only `unmassk-flow-stack` knew to defer, not the reverse).
- CRLF line endings in `unmassk-audit/SKILL.md` — the only file in the repo affected, likely a leftover from an earlier Windows-compatibility fix — converted to LF; could have broken tooling parsing its frontmatter.
- `test_user_prompt_skill_router.py` took 4+ minutes because most cases spawned a real subprocess and git repo per test; refactored so the majority call the pure `match_skills()` function in-process, reserving subprocess tests for the 6 that genuinely exercise hook wiring — same 85 tests, same coverage, now runs in well under 1 second.

## [1.13.0] - 2026-07-04

### Changed

- `unmassk-grill` extended instead of building a new skill: after researching GitHub's `spec-kit` and running a full pressure-test, the proposed new skill's core mechanism turned out to be identical to what `unmassk-grill` already does. Added a "Vagueness preamble" that scans the request's own wording for unquantified qualifiers, missing actors, missing error states, and ambiguous scope before the interview starts; an "Independently testable slice" check in the interview rules to catch a request that's secretly 2-3 bundled features; and a "Bounded mode" for when grill is invoked automatically by `unmassk-project-lifecycle` or `unmassk-flow` (capped at 5 questions, instead of running unbounded, so it doesn't stall an automated pipeline step).
- `unmassk-flow` (Step 0 Triage, for Standard/Big scope) and `unmassk-project-lifecycle` (START branch, before the requirements cascade) now call `unmassk-grill` explicitly — previously neither skill invoked it at all, using the toolkit's established phrasing ("use the Skill tool with `skill=\"unmassk-grill\"`") instead of the looser "invoke" wording both had. Flow's Step 1 Brainstorm also picks up any open branches logged by grill's bounded pass instead of re-deriving them from scratch.
- Removed the orphaned `unmassk-project-lifecycle/references/prd-template.md` — it was never wired into any live skill; git-memory's decision/memo commits already cover what a static PRD file would.

## [1.12.0] - 2026-07-04

### Added

- Gitto Mode C (Consolidator) installed (`agents/gitto.md`): a periodic memory-consolidation mode that reads all of a project's decision/memo/remember history and writes additive "crown" entries for topics that drifted across many commits, so the canonical version surfaces instead of the reader having to reconcile scattered restatements. Ships with a retraction mechanism — a `Retract-Crown: <hash>` trailer (paired with a required `Why:`, enforced by both commit-trailer validation hooks) that revokes a crown without resurrecting an older, already-superseded one; at boot, `session-start-boot.py` excludes retracted crowns and falls back to the fully un-crowned entry set. `Retract-Crown` added to `VALID_KEYS`/`MEMORY_KEYS` in `lib/constants.py`. 17 new tests (`tests/test_crown_retraction.py`); the existing 21 Crown tests are unaffected.

### Changed

- Commit/push cadence clarified for multi-agent pipelines: the crew (Ultron, Dante, Cerberus, etc.) never commits its own work — each agent returns a summary and the orchestrator records a local `wip:` commit per sub-step without pushing. A pipeline isn't closed until Yoda's verdict and Alexandria's documentation pass are both done; only then does Gitto squash the wips into a clean commit (or a few, with real trailers) and push. Memory commits (`decision`/`memo`/`remember`/`context`) are unaffected and still push immediately. Documented in `unmassk-gitmemory` and `unmassk-flow` SKILL.md, including a repo-type-aware (trunk vs. gitflow) rewrite of Flow's Step 7 Close, which previously assumed gitflow (merge to `dev`) unconditionally.

### Fixed

- Gitto Mode C's own grep pattern for reading memory history (`git log --grep="^\(Decision\|Memo\|Remember\):"`) matched zero commits against this project's real commit format (`<emoji> decision(scope): text`, not `Decision: text`) — caught via a dry-run against the repo's own memory before the feature shipped as done.

## [1.11.1] - 2026-07-03

### Changed

- README "Standards" row corrected to say 34 sections (was still showing 33), matching the §34 Producer↔Consumer Data Integrity addition already shipped in v1.11.0.

### Fixed

- Hardcoded Spanish forced onto every toolkit installer regardless of their own language, across code shared by every install: `lib/managed_blocks.py` (the generic CLAUDE.md communication block literally instructed every installer's Claude to always respond in Spanish — now language-neutral, matches the user's own language instead), `skills/unmassk-standards/references/standards.md` §18 "Language in Code" (was forcing Spanish comments/logs/error messages into the actual code Ultron writes for any installer's project, previously enforced as a T3 finding by Cerberus/Yoda — now follows the project's existing convention, defaults to English if greenfield; "identifiers always English" unchanged), `hooks/pre-task-recall.py` (memory-injection header shown to every subagent), `hooks/session-start-boot.py` (consolidation warning), `skills/unmassk-project-lifecycle/references/prd-template.md` (currently orphaned/unwired, translated anyway), and `bin/git-memory-commit.py` (`--path` argparse help string) — all translated to English. Found via a full Bilbo sweep of the distributed toolkit surface (skills/agents/hooks/lib/bin/README/CHANGELOG) after the first instance surfaced. The maintainer's own Spanish-communication preference is preserved separately as a `remember(user)` entry in git-memory — not lost, just no longer embedded in code shipped to every installer.

## [1.11.0] - 2026-07-02

### Added

- `unmassk-standards` §34 "Producer↔Consumer Data Integrity (Anti-Fixture-Fabrication)": closes a real-world failure class where a downstream project shipped ~2 weeks of undetected bugs because every crew agent validated against the same hand-fabricated mock fixture instead of the real backend. Enforced at four independent checkpoints: Dante (never Ultron) owns building the round-trip check against the real producer; Cerberus flags hand-typed literals used as expected values; Moriarty sabotages the real dependency with realistic corruption (not just connection kill-switches), verified through an independent channel, before declaring a feature resilient; Yoda's new Round-Trip Evidence Rule is fail-closed by default and requires a mechanical artifact he reads himself — never narrated by another agent — before rendering a verdict, with no "approved with conditions" discretion for this gate. `unmassk-flow` Step 0 (Triage) now requires a mandatory seam declaration regardless of feature size. Alexandria gains a new duty: document the real producer↔consumer contract once Yoda approves it, never the fixture.

### Fixed

- Merge gate (`hooks/pre-merge-gate.py`) no longer blocks same-branch catch-up syncs (e.g. `git pull origin main` while on `main`) behind the Cerberus+Alexandria review requirement — that gate now only fires when merging or pulling a genuinely different branch. Fail-closed: any ambiguity in resolving the current branch or the merge/pull target still falls back to requiring review. 12 new tests (`tests/test_pre_merge_gate.py`).

## [1.10.0] - 2026-06-16

### Added

- Crown marker (`Crown: <kind>` trailer): any memory commit (`decision`/`memo`/`remember`) can carry `Crown: Decision|Memo|Remember` to designate itself as the canonical entry for its category. At boot, crowned entries appear first in their section (DECISIONS / MEMOS / REMEMBER) and are prefixed with 👑, outside the normal entry budget so they never displace regular entries. Crown wins tie-breaking by scope even when the entry originates in the glossary. Additive and presentational: the "a Decision is never tombstoned" rule is unchanged. `Crown` added to `VALID_KEYS` and `MEMORY_KEYS` in `lib/constants.py`. 21 tests (`tests/test_crown.py`). This is Phase 1 of the memory consolidator — infrastructure only; the auto-consolidation flow (Gitto writing crown entries) is not yet wired (see below).
- Consolidation trigger (`CONSOLIDATE:` block): at boot, if the number of commits since the last `context(consolidation)` reaches the threshold (default 50, overridable via `GIT_MEMORY_CONSOLIDATION_THRESHOLD`), the boot output emits a `CONSOLIDATE:` block telling the orchestrator to launch Gitto in consolidator mode. Helper `commits_since_last_consolidation()` added to `lib/git_helpers.py`; uses `rev-list --count` for robustness on long histories; returns a high sentinel (9999) when no `context(consolidation)` exists so the first-ever run always triggers; fail-safe to 0 on error. Only the scope `context(consolidation)` resets the counter — ordinary `context()` commits do not. 11 tests (`tests/test_consolidation_trigger.py`). Phase 2 of the consolidator — trigger infrastructure only. The Gitto consolidator prompt is a draft under review (`docs/gitto-consolidador-DRAFT.md`, Phase 4, pending external AI review); automatic consolidation is not yet active.

## [1.9.0] - 2026-06-12

### Fixed

- Boot glossary merge now respects GC tombstones (`hooks/session-start-boot.py`): retired memos/remembers (`Resolved-Memo`/`Resolved-Remember`) no longer reappear at session start. `extract_memory()` now exposes the collected tombstones, and the REMEMBER/MEMOS glossary-merge steps skip any entry whose normalized text is tombstoned (decisions are never tombstoned, by design). Re-applies the fix from stale PR #20 fresh on `main`, with a regression test, without dragging that branch's 3-month-old memory commits. Test-first; full suite green.

#### Multi-agent audit (Bilbo · Argus · Cerberus · Moriarty) — correctness & robustness sweep

- **Three hook crashes that broke the session (fail-open violations):** `post-validate-commit-trailers.py` crashed on a non-numeric `exit_code`; `session-start-crew.py` crashed on a non-UTF-8 `CLAUDE.md`; `pre-validate-commit-trailers.py` blocked legitimate commands (`cat git.log`, `git log-remote`) via an over-broad `git…log` pattern. All three now degrade safely.
- **Memory dedup gate** (`pre-memory-dedup-gate.py`) was silently skipped when trailers used single quotes or no quotes — pattern now matches all three forms.
- **Retired notes reappearing:** the boot glossary merge only honored tombstones within the recent scan window (retired notes older than ~30 commits came back); and the pre-compaction snapshot (`precompact-snapshot.py`) only checked 2 of the 4 tombstone kinds. Both now honor tombstones across the full range / all `TOMBSTONE_KEYS`.
- **Context-commit detection** unified to one predicate across `extract_memory()` and `get_last_context_time()` (a `feat(x): context(...)` subject no longer counts as a session bookmark).
- **GC** (`git-memory-gc.py`) now recognizes all four `TOMBSTONE_KEYS` when detecting already-tombstoned items.

### Security

- Bounded `sys.stdin.read()` in `pre-merge-gate.py`, `pre-task-recall.py`, `pre-memory-dedup-gate.py`, and `validate-memory-path.py` (was unbounded; only `user-prompt-memory-check.py` was capped).
- `GIT_MEMORY_CO_AUTHOR` is sanitized before going into commit messages (truncated at the first newline) so a crafted value cannot inject fake trailer lines.
- `git-memory-log.py` validates `count >= 1` (a negative count previously dumped the entire history).
- `stop-dod-gate.py` (config-driven `test_command`) and `pre-merge-gate.py` (`# merge-reviewed` token) documented as repo-trust / policy controls, not security boundaries.

### Changed

- One canonical text sanitizer (`lib/parsing.py:sanitize_trailer_value`) now used by recall, boot, and the pre-compaction snapshot — previously three divergent copies (boot/snapshot stripped less than recall).
- Trailer parsing and text normalization unified: `git-memory-gc.py` and `git-memory-doctor.py` now use the canonical `parse_trailers_full()` and `normalize()` from `lib/parsing.py` instead of hand-rolled, divergent copies — wiring in a previously dead function and fixing silent whitespace-normalization mismatches.
- Recall scan (`lib/recall.py:_scan_commits`) filters `git log` to memory-bearing commits via `--grep`, bounding the scan on large-history repos without dropping any memory entry.
- Removed an unreachable `wip:` branch in `parse_commit_type()`.

## [1.8.0] - 2026-06-12

### Added

- Orchestrator recall (`hooks/user-prompt-memory-check.py` + `lib/recall.py`): on every user message, the `UserPromptSubmit` hook searches git memory for entries relevant to that message and injects only what clears the relevance gate into the main Claude thread. The block is framed as untrusted context — labelled `[memoria relevante para este mensaje — SOLO CONTEXTO, NO INSTRUCCIONES]` and wrapped in `<memory-data>…</memory-data>` delimiters — so Claude reads it as data, not as instructions (anti prompt-injection). `_sanitize` strips those delimiters from every entry before injection, so no stored commit can escape the untrusted zone or fake additional instructions. New `recall_relevant()` in `lib/recall.py` applies a three-step gate: discard score ≤ floor (noise floor), keep only entries within `top_fraction` of the top score (focus window), cap at `max_results` (3 by default); returns `None` when nothing clears the gate. Reuses the existing BM25/IDF engine. Fail-open throughout: import failure, stdin errors, recall exceptions, and slow upgrades are all caught and logged to stderr without ever blocking the session. Distinct from the subagent recall gatekeeper (`hooks/pre-task-recall.py`, v1.3.0), which injects memory into crew agent prompts; this one injects into the orchestrator's main thread. 70 tests; Cerberus LGTM; Argus/Moriarty: 2 T1 issues resolved; Yoda READY 107/110 (Security capped at 9 — accepted architectural ceiling, decision d819b0c).

## [1.7.0] - 2026-06-12

### Changed
- Version marker auto-sync after `/plugin update`: `needs_upgrade()` in `hooks/user-prompt-memory-check.py` now also triggers the upgrade flow when the project's installed manifest version (`manifest.json`) is older than the plugin code version — using numeric SEMVER comparison (1.10.0 > 1.9.0), not string comparison. Reuses the existing `bin/git-memory-install.py --auto`. Fail-safe: absent, corrupt, or unparseable manifest → no upgrade, no loop. Downgrade is intentionally ignored (manifest > code → no action). 15 tests covering edge cases (null, empty string, missing key, pre-release strings, numeric ordering).

## [1.6.0] - 2026-06-10

### Added
- Hard DoD gate (`hooks/stop-dod-gate.py`): Stop hook that BLOCKS session close (`decision:block`) when the project's configured test command exits non-zero — "done" can no longer be claimed with red tests. Opt-in via `.claude/git-memory-config.json` `test_command`. `shell=False` + `shlex.split(posix=False)` + quote-strip (injection-safe, Windows-compatible); 60s internal timeout (hooks.json 90s). Fail-open on any infra error (missing/unreadable config, missing binary, timeout, shlex `ValueError`, unexpected exception) — a broken gate never traps the user. 23 tests; Cerberus LGTM (0 blocking), both suggestions closed. Foundation for a safe autonomous ("Ralph") mode. Closes roadmap items #2/#3.

### Changed
- `unmassk-core` SKILL.md hardened: removed the "trivial 1-line edit" carve-out that let the orchestrator touch production code/tests. The orchestrator now edits NO code or tests ever (not even one-liners) — production code → Ultron, tests → Dante; "do it yourself" never licenses touching code. Closes a real loophole the orchestrator had exploited (and the matching `remember(claude)` was retired as a duplicate — the rule belongs in the skill, not memory).

## [1.5.0] - 2026-06-10

### Added
- Memory dedup gate (`hooks/pre-memory-dedup-gate.py`): PreToolUse/Bash hook that WARNS (non-blocking, fail-open) when a `memo`/`remember` commit is a lexical near-duplicate of an existing entry of the same type — Jaccard ≥ 0.40 over recall's tokenizer with an extended dedup stoplist, naming the match in `permissionDecisionReason`. Decisions are never compared (sacred). Cheap pre-filter regex so the 99% of Bash commands that are not memory commits skip git entirely. 40 tests; validated against the real corpus (does not fire on the iterated "3 memory systems" memos — those are semantic restatements, not lexical dups). Documented in `unmassk-gitmemory` Active Hooks.

### Changed
- Memory capture reminder (`hooks/user-prompt-memory-check.py`): the per-message `[memory-check]` flipped from "contains memory? → save it" to restraint — save ONLY if durable, non-derivable, and not already captured; on a correction, RETIRE the old entry with a tombstone instead of stacking; systemic/process rules belong in the loaded skill, not memory. Lowers over-saving pressure at the source (the gate is the net; this is the belt).

## [1.4.0] - 2026-06-09

### Added
- Release script (`bin/release.py` + `bin/release_helpers.py`): single command to orchestrate a full plugin release — pre-flight checks (clean tree, semver order, non-empty changelog, upstream configured, not behind remote), version bump, changelog promotion, pathspec commit via `git-memory-commit.py`, push, and post-push verification. Supports `--dry-run` and `--allow-dirty`. Exit codes: 0 = ok, 1 = preflight/execution error, 2 = post-push verify failure.
- `git-memory-commit.py --path` flag: allows callers to commit only specific files by pathspec, used by the release script to stage exactly the three release files without touching the rest of the index.
- `docs/RELEASING.md`: human-readable how-to guide for the release workflow — preconditions, dry-run first, what each step does, flags, version rules, mid-release recovery, and a first-use checklist.
- Documentation coverage: `unmassk-seo` SKILL.md now documents both active hooks (`pre-commit-seo-check.sh` and `validate-schema.py`) with triggers, what they check, and how to interpret their output. `unmassk-ops/ops-observability` routing table corrected to reference `logql-regression-checks.sh` as the LogQL validator. `unmassk-ops/ops-cicd` documents the usage trigger for `azure-step-walker.py` (traversal library, not invoked directly) and `azure-test-regressions.py` (regression suite). `unmassk-media/media-image-edit` now references `.env.example` for `FAL_KEY` configuration.
- Documentation discipline (three-audience rule): every new capability must be documented for humans (`README`/`docs`), the team (roadmap/git-memory), and Claude at load (`SKILL.md`/`CLAUDE.md`) in the same change. Encoded in `unmassk-core`, Flow's Document step, `unmassk-close-session`, and Alexandria's mandate.
- Toolkit discoverability in skills: `unmassk-gitmemory` now documents the `--path` flag, the `git-memory-recall.py` search tool (with ranking internals), the `memo(stack)` category, the release process (`bin/release.py`), and an "Active Hooks" section (merge gate, recall gatekeeper, commit validation, etc.). `unmassk-core` gains a Protocol-skills menu and Gitto Mode B (git ops). `README` gains a Development section and a Protocols row.
- Config for domain plugins: `unmassk-seo/.env.example` (5 MCP credentials), `unmassk-compliance/.mcp.json` + `.env.example` (Better i18n MCP).

### Fixed
- Scope-map path in `unmassk-gitmemory` SKILL.md corrected (`unmassk-crew-bilbo` → `unmassk-toolkit-bilbo`) — was a silent failure whenever Claude looked up the scope map.
- Test isolation bug: `test_migrate_statusline.py` left a stub `git_helpers` (missing `GIT_TIMEOUT`) in `sys.modules` without restoring it, breaking `test_recall.py` in the full suite (58 failures). Now snapshots/restores `sys.modules`. Full suite: 315/315 green.

### Removed
- Dead weight: `!new_skills/` (already integrated in v1.3.0), empty `generated-images/`, and orphaned `.pyc` files under the root `tests/`.

## [1.3.0] - 2026-06-08

### Added
- Recall gatekeeper (`hooks/pre-task-recall.py`): PreToolUse/Task hook that injects relevant project memory (decisions, memos, remembers) into subagent prompts before they execute. Uses `lib/recall.py` for keyword-ranked retrieval. Fail-open: any error lets the spawn through unchanged. Whitelisted to the 8 crew agents (Ultron, Dante, Cerberus, Argus, Moriarty, House, Yoda, Alexandria); Bilbo and Gitto are excluded. 51 tests.
- Build mode (`skills/unmassk-flow/references/linear.md`, `references/test-first.md`): two coding modes selectable per task. Linear for straightforward work; test-first/ATDD for complex features (Dante enters twice — acceptance contract before implementation, exhaustive hardening after). Flow acts as router in Execute Step 4 and delegates to the chosen reference document. Ultron and Dante gain explicit build-mode awareness.
- CLAUDE.md block generator (`lib/managed_blocks.py`): single source of truth for all 5 managed blocks (toolkit, protocols, caveman, communication, build-mode). Idempotent upsert — install, upgrade, and uninstall all import from this module; the blocks can no longer diverge across lifecycle commands. 35 new tests, 0 regressions.
- Protocol skills installed: `close-session`, `grill`, `council`, `project-lifecycle` — all four built, tested, and registered in the CLAUDE.md menu. Previously listed as planned; now live.
- Close-session hook (`hooks/stop-close-session.py`): Stop hook that fires at end of session, prompts the orchestrator to run the close-session skill (decisions dump, versioning if applicable, cleanup). Suppressed when the session had no substantive work. Coexists with the existing `stop-dod-check` hook.
- PRD template saved to `skills/unmassk-project-lifecycle/references/prd-template.md` for use in the START branch of the lifecycle skill.
- Communication block added to CLAUDE.md: rules for how agents report to the orchestrator (results not process, confirm structural changes with exceptions for security/irreversible/unverifiable, one thing at a time).

### Changed
- Flow skill (`skills/unmassk-flow/SKILL.md`) updated: Execute phase now routes to `references/linear.md` or `references/test-first.md` instead of inlining the method. Follows the Standards pattern — one rule, one place.
- Memory calibration tightened (`skills/unmassk-gitmemory/CALIBRATION.md`, `SKILL.md`): three root-cause fixes for over-saving — scope test (project rules belong in project memory, not global remember), stable-done filter (only save what is finished and confirmed, not in-progress reasoning), and timing-not-volume (urgency of a commit is determined by when the signal fires, not how many signals accumulated). `"never commit to main"` rule reframed by repo type: gitflow repos keep the rule; trunk-based repos commit to main by design.
- `unmassk-audit` skill aligned with session decisions: steps 0 and 13 now inherit `repo_type` from `unmassk-gitmemory` (gitflow → branch from dev + merge; trunk → main directly) instead of always assuming `dev`. The 97% coverage gate is documented as a deliberate audit exception that supersedes the pipeline's "coverage does not block merge" override. Scoring/tiers/weights now reference `unmassk-standards` rather than duplicating them.
- Core skill clarified: Ultron = production code only (not skills, agent prompts, or docs). Orchestrator loads standards on-demand; it does not load them at boot.

### Fixed
- Boot hook (`hooks/session-start-boot.py`): removed redundant full-text dump of `unmassk-core`, `unmassk-gitmemory`, and `CALIBRATION.md` from the boot output. These were being injected twice (once by the hook, once by the explicit Skill calls in CLAUDE.md), inflating the session start to ~57 KB that the harness truncated. Explicit Skill calls remain; the duplicate inline dump is gone.
- Flow-stack scaffold path corrected: `scaffold.py` was referenced as `flow-stack-selection` (does not exist) — fixed to `unmassk-flow-stack/scripts/scaffold.py` in two places, unblocking the lifecycle START branch.

## [1.2.0] - 2026-06-05

### Added
- Memory recall engine: `lib/recall.py` + CLI `bin/git-memory-recall.py`. Searches all decision/memo/remember commits by keyword with IDF ranking (rare terms score high, common terms sink), 1.5x bonus for scope matches, alphanumeric tokenization (finds `BM25`, `v2`, `RS256`), deduplication, and full history scan with no commit cap. Robust against context-injection attempts (sanitizes Unicode terminators) and enforces a query length cap.

### Changed
- `git_helpers.run_git` now accepts a `cwd` parameter, making it usable from any working directory.
- `TOMBSTONE_KEYS` and `RECALL_KEYS` constants extracted to `lib/constants.py` — shared between the recall engine and the boot hook (eliminates duplication).

### Removed
- Context-tracking subsystem removed entirely: `bin/context-writer.py`, the statusline wrapper it installed, context percentage warnings in `hooks/user-prompt-memory-check.py`, and all associated install/uninstall/upgrade lifecycle code. The subsystem was designed for the 200k-token context window; with 1M tokens it was noise.

### Fixed
- Upgrade self-heal: if a user's existing Claude settings still pointed the statusline at the deleted `context-writer.py`, the boot hook now detects this and restores the original statusline value (or removes the key), preventing a broken statusline after upgrading from any older version.

### Security
- `shell=True` in `context-writer.py` (issue #48, T1) is eliminated as a side-effect of removing the file entirely.

## [1.1.2] - 2026-03-24

### Fixed
- Boot migration `_migrate_untrack_generated_jsons()`: added `-r` flag to `git rm --cached` for `.unmassk/` directory — was failing silently (exit 128) without it.
- Upgrade tests: replaced stale `"Git Memory Active"` string literals with `"unmassk-toolkit Active"` to match current managed block content.

## [1.1.1] - 2026-03-24

### Fixed
- All 10 agent prompts: replaced routing language (`flag to X`, `route to X`, `@mention`) with scope declarations (`X's scope`). Agents outside chatroom cannot invoke each other — they only report back to the orchestrator.
- Ultron: added missing "The Team" table, removed leftover v1-to-v2 meta sections ("Things Cut From v1", "Summary of Changes").
- Cerberus: completed "The Team" table (was missing House, Bilbo, Alexandria, Gitto).
- Removed chatroom V2 reference files (`chatroom/*-system-prompt-v2.md`) — V2 is now canonical only in plugin source (`unmassk-toolkit/agents/`).

## [1.1.0] - 2026-03-24

### Added
- `compliance-legal-docs` skill: SKILL.md created with 42-reference routing table organized by category (contract review, GDPR/privacy, risk assessment, litigation, French employment law, vendor due diligence, document processing, legal ops)
- V2 system prompts for all 10 agents (alexandria, argus, bilbo, cerberus, dante, gitto, house, moriarty, ultron, yoda): universal format with The Team table, EXHAUSTION PROTOCOL, plain agent names (no @mentions), and no chatroom references — prompts work in any Claude Code context. Each agent self-reviewed their V2 draft and restored load-bearing V1 content that the initial rewrite lost.
- 5-phase agent pipeline: `PIPELINE_GENERIC` and `AGENT_PIPELINE_POSITION` rewritten. Each agent has an explicit chain position entry covering role, when to act, and when to skip.

### Fixed
- Boot hook now skips tombstoned entries when merging glossary remembers and memos into the session summary — `Resolved-Remember:` and `Resolved-Memo:` tombstones are respected on the glossary merge path, not just on the recent-commits path.

## [1.6.0] - 2026-03-16 (unmassk-crew)

### Added
- Cerberus commit-review mode: diff-only review pass with three severity tiers — Issue (blocks merge), Suggestion (recommended, non-blocking), Nitpick (never blocks). Includes a nitpick checklist covering naming conventions, natural language, import type consistency, `as const` usage, magic numbers, stray `console.log`, and similar low-stakes hygiene items. Inspired by CodeRabbit's review model.
- Alexandria merge mode: fast pre-merge documentation gate. Reads only the branch commits vs target branch, updates CHANGELOG under `[Unreleased]`, and checks affected CLAUDE.md files for staleness. No new files created, no memory writes — designed for speed at the merge boundary.
- `pre-merge-gate.py` PreToolUse hook: blocks `git merge` and `git pull` (non-rebase) commands until Cerberus and Alexandria have both passed. Detects `git.exe` on Windows, uses case-insensitive command matching, guards against `eval`/`bash -c`/`sh -c` indirection, and normalizes null bytes. Bypass by adding `# merge-reviewed` comment after both agents pass.

### Changed
- Orchestrator rules in `session-start-crew.py` updated with merge gate awareness: orchestrator must not call merge commands without a prior Cerberus + Alexandria pass, and proactive agent launch guidance is now explicit in the managed block.
- Crew table descriptions updated: Cerberus now documents both enterprise-audit mode and commit-review mode; Alexandria now documents both standard mode and merge mode.

## [1.5.0] - 2026-03-16 (unmassk-crew)

### Added
- `validate-memory-path.py` PreToolUse hook blocks agent-memory writes outside the git root — prevents agents from creating `.claude/agent-memory/` directories in wrong locations after `cd` operations. Fail-closed design with Windows case-insensitive path handling and symlink resolution via `realpath`.
- Orchestrator rules added to the `session-start-crew.py` managed block: orchestrator must not write code (delegate to Ultron), must launch Cerberus+Argus after any new code lands, decides what and who — not how.

### Changed
- Agent boot prompts hardened in 6 agents (cerberus, dante, ultron, alexandria, bilbo, house): `GIT_ROOT` is now resolved once as an absolute path with `|| exit 1` fallback, and the memory section enforces absolute paths anchored to `GIT_ROOT`.
- `hooks.json` updated with PreToolUse matcher for `Write|Edit` pointing to `validate-memory-path.py`.

### Fixed
- `compliance-legal-docs` references: removed broken `/mnt/skills/public/docx/SKILL.md` paths in 3 GDPR files (gdpr-privacy-notice-eu, dpia-sentinel, gdpr-breach-sentinel) — now points to `legal-docx-processing-anthropic`
- `compliance-legal-docs` references: removed broken sub-file references in both assignation-en-référé files (workflow-informations.md, structure-assignation.md, workflow-collecte.md, variantes-cas-particuliers.md, conseils-strategie.md) — workflows now self-contained in the reference files
- `compliance-legal-docs` references: removed broken `assets/` template path in politique-confidentialite-malik-taiar
- `compliance-legal-docs` references: removed `scripts/office/unpack.py`, `scripts/comment.py`, `scripts/accept_changes.py`, `scripts/recalc.py` references — replaced with standard system commands (unzip, LibreOffice, zip)
- `compliance-legal-docs` references: removed `editing.md`, `pptxgenjs.md`, `scripts/thumbnail.py` references from pptx-processing — replaced with inline instructions
- `compliance-legal-docs` references: removed `REFERENCE.md`, `FORMS.md` references from pdf-processing
- `compliance-legal-docs` references: replaced `AskUserQuestion`/`Task` tool calls in tabular-review with plain prose instructions; updated pdf/docx/xlsx "skill" references to reference file names

- `unmassk-ops` plugin: 5 skills covering the full ops domain (iac, containers, cicd, observability, scripting)
- `ops-iac` skill: SKILL.md + 14 references rewritten (Terraform, Ansible, Helm, Pulumi, OpenTofu)
- `ops-containers` skill: SKILL.md + 19 references rewritten (Kubernetes, Docker, Helm, container security)
- `ops-observability` skill: SKILL.md + 9 references rewritten (Prometheus, Grafana, alerting, logging)
- `ops-scripting` skill: SKILL.md + 21 references rewritten (Bash, Makefile)
- `ops-cicd` skill: SKILL.md + 30 references rewritten (GitHub Actions, GitLab CI, Azure Pipelines, Jenkins)

## [3.7.0] - 2026-03-13

### Added
- Boot auto-detects missing `git-memory-scopes.json` and instructs Claude to generate it via Explore agent
- Next cleanup in boot: checks GitHub issue status for pending Next items — closed issues are filtered out, items older than 7 days without an issue ref are marked `[stale]`
- Cross-repo guard prevents false positives when Next items reference issues in other repositories
- GC tombstone support for `Resolved-Next:` trailers — resolved pending items are hidden from future boot output
- Context warnings now use debounce: same-level warnings suppressed for 5 messages (shows `[CTX: N%]` instead), severity escalation (warning to critical) bypasses debounce
- Advisory language for context warnings — informs the agent instead of commanding it
- Test coverage for `context-writer.py` statusline wrapper (7 tests)
- `CO_AUTHOR` is now configurable via `GIT_MEMORY_CO_AUTHOR` environment variable

### Changed
- Scout agent removed — scope scanning now handled by an Explore agent prompt during boot
- Context percentage is now always shown in the UserPromptSubmit hook output (previously only displayed at 60%+ usage)
- Removed `Refs:` trailer key from valid keys — was unused dead code
- Replaced remaining scout terminology in bootstrap script and tests

### Fixed
- Boot and commit script hardening from code review feedback
- Debounce oscillation bug: context bouncing between 59-61% caused stale debounce state to suppress warnings incorrectly — state now resets when context drops back to info level
- `.context-status.json` and `.context-warn-state.json` added to `.gitignore` (were being tracked as noise)

## [3.6.0] - 2026-03-13

### Added
- Boot briefing v2: SessionStart hook produces structured output with zero redundant bash calls
- Automatic conversion of `Next:` trailers to GitHub issues during boot

### Changed
- Version is now centralized in `lib/version.py` as single source of truth, read from `plugin.json`
- CLAUDE.md boot instructions corrected and simplified

## [3.5.1] - 2026-03-13

### Added
- Context warnings now fire mid-session via UserPromptSubmit hook, not just at boot
- Slim hook output after boot — flag file prevents repeated instructions

### Fixed
- Quote all paths in hook output to prevent Windows path mangling
- UserPromptSubmit hook now uses wrapper scripts consistently

## [3.4.0] - 2026-03-12

### Added
- New `git-memory-issues` skill — GitHub issues and milestones as shared team memory
- Safety improvements: confirmation protocol, `--no-ff` merges, pre-merge checklist, immediate back-merge
- Scout agent onboarding integration
- Alexandria documentation agent design

### Fixed
- Belt regex now catches `git -C` and other flags before `log`/`commit` interception
- Narrowed issue skill trigger to avoid false activations on generic words

## [3.3.0] - 2026-03-12

### Added
- `remember()` commit type for explicit long-term memory capture
- Hierarchical scopes with scope-scout agent for automatic scope grouping in glossary
- Mandatory rule: agents always launch in background
- Hardened stop hook — `context()` commit is now mandatory when closing a session

### Changed
- Skill refactored to consolidate all rules (CLAUDE.md managed block minimized)
- Scope-scout agent renamed to "scout"

## [3.2.0] - 2026-03-12

### Added
- Pretty ANSI output for commit and log wrapper scripts
- PreToolUse hook blocks direct `git commit`/`git log` — forces wrapper scripts
- Boot glossary: session start extracts all decisions and memos from full git history

## [3.1.0] - 2026-03-12

### Added
- Frictionless capture: auto-detect decisions, memos, and context from conversation — commit without asking

### Changed
- CLAUDE.md managed block reduced to minimal pointer; all rules moved into the skill file

## [3.0.0] - 2026-03-11

### Changed
- Complete plugin audit: dead code removed, skills merged into single coherent file
- Dashboard archived (superseded by CLI tools)
- Boot now fetches latest git history before building snapshot
- All version references synced across plugin.json, marketplace.json, and code

### Fixed
- Restored `.claude-plugin/` files accidentally deleted during cleanup
- Install script no longer deletes source files when running inside the plugin's own repository

## [2.2.0] - 2026-03-11

### Added
- Context-aware stop hook with statusline wrapper showing session summary
- Gitto memory oracle agent for querying project memory conversationally
- Silent WIP strategy — WIP commits happen without noisy output

### Fixed
- Stale hooks cleaned during zero-copy migration
- Statusline backup hardened against missing files
- Doctor command now detects stale hook configurations

## [2.1.0] - 2026-03-08

### Added
- Automatic context checkpoint commits at natural pause points
- Auto-upgrade of outdated CLAUDE.md managed blocks on session start

### Changed
- Zero-copy install model: plugin runs directly from Claude Code cache, no files copied to project root
- Upgrade script rewritten for zero-copy model with full test coverage

## [2.0.0] - 2026-03-07

### Added
- SessionStart and UserPromptSubmit hooks for automatic memory boot
- Circuit breaker in Stop hook to prevent infinite loops
- Bootstrap detection in UserPromptSubmit hook for first-run guidance
- Incomplete install detection when `lib/` or `bin/` is missing
- Comprehensive type hints with mypy strict mode
- Monorepo detection refined with Rush/Moon support and scope mapping

### Changed
- Extracted shared `lib/` module: constants, git_helpers, parsing, colors (DRY refactor)
- All CLI scripts migrated from ad-hoc argument parsing to argparse
- Migrated 5 test suites to pytest with shared fixtures (old test files removed)
- Plugin aligned with official Claude Code plugin spec
- All code translated to English (docstrings, comments, headers)
- Marketplace.json added for self-hosting distribution
- Skills updated to use local paths instead of `$CLAUDE_PLUGIN_ROOT`

### Fixed
- Security audit round 2: complete manifest, symlink safety, MEMO_CATEGORIES validation, exit codes, imports
- Security audit round 3: XSS in dashboard, atomic writes, shell injection prevention, tombstone normalization
- Hook settings.json format corrected (flatten nesting, string matchers)
- Dashboard date parsing fixed (all dates were null)
- Stop hook now ignores git-memory runtime files

## [1.1.0-gitmemory] - 2026-03-06

### Added
- Static HTML dashboard for visualizing git memory (`git memory dashboard`)
- Lifecycle scripts: doctor, install, repair, uninstall
- Bootstrap scout: detects project stack, monorepos, and commitlint configuration
- Safe upgrade system with backup, diff review, and migrations
- Integration test matrix covering 10 end-to-end scenarios

### Changed
- Restructured project as Claude Code plugin (v2 architecture)

### Fixed
- Security audit: symlink traversal, uninstall orphans, exit code handling, manifest validation

## [1.0.0] - 2026-03-05

### Added
- Core git-memory system: persistent memory via git commit trailers
- Commit types: `context()`, `decision()`, `memo()` with emoji prefixes
- Memory search protocol with `git fetch` + deep grep before asking the user
- Conversational memory detection from natural language triggers
- Contradiction detection for conflicting decisions and memos
- Drift test validating search relevance and dedup under stress (200 commits, 6 scopes)
- CLI for manual memory queries (`git memory search`, `git memory log`)
- Garbage collector for pruning stale memory entries (`git memory gc`)
- Git hooks: pre-validate and post-validate commit trailers, precompact snapshot

### Changed
- Hooks hardened with restored drift test coverage

### Fixed
- Post-hook safety for delimiter collisions and nested prefix handling
- Partial date validation in form components
