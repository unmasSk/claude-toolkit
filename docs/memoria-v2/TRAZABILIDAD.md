# Trazabilidad — los 131 requisitos de la especificación, uno a uno

**Para qué sirve este documento:** demostrar que ningún requisito de la especificación se queda sin paso. Si algo no está aquí, no se construye — y eso es exactamente lo que le pasó al v1, donde cinco campos se escribieron miles de veces sin que nadie los leyera y cinco scripts murieron sin que nadie se enterara en meses.

**Cómo se lee:** el número de paso remite a `PLAN-CONSTRUCCION.md`. Un requisito sin paso es un fallo del plan, no del documento.

**Estado de partida:** la auditoría sobre el plan v1.0 encontró **68 cubiertos, 32 ambiguos y 31 huérfanos**. Esta versión asigna paso a los 131.

---

## Principios (P1–P12)

| # | Requisito | §Spec | Paso |
|---|---|---|---|
| 1 | Nada se borra ni se reescribe; toda corrección es un commit nuevo | P1 | 9.1 |
| 2 | Comando de regeneración total de índices desde git | P1, §7 | 3.7 |
| 3 | Si los índices divergen de git, manda git — con ejecutor, no solo aviso | P1, §7 | 3.4 + 3.7 |
| 4 | Ningún campo entra sin su lector construido a la vez | P2 | **1.3 + 1.10** |
| 5 | Validador único: el contrato del que escribe es el vocabulario del que lee | P3 | 1.8 + 6.1 |
| 6 | Nada crítico depende de que el modelo se acuerde: gate o protocolo | P4 | transversal, verificado en TRAZABILIDAD |
| 7 | Rechazo informativo: bloqueo con la pregunta y las opciones dentro | P5 | 1.7 |
| 8 | El comando admite todos los flags en el primer intento | P5 | 2.6 |
| 9 | La skill enseña a traer los flags puestos | P5 | 7.1 |
| 10 | Toda pieza enseña un número al arrancar; el cero es alarma en alto | P6 | 3.5 |
| 11 | Chequeo instalado↔escrito desde fuera de la caché | P7 | 7.14 |
| 12 | Idioma por función: titular y keys en inglés; porqué, descripción y contexto en español | P8 | 1.8 |
| 13 | Se retira todo lo que no tenga caso de uso demostrado | P9 | §5 del plan |
| 14 | Emojis por tipo conservados: ❓ pregunta · 🚫 descarte · 🔥 incidencia | P10 | 0.2 |
| 15 | Estructura visual jerárquica conservada | P10 | 4.4 |
| 16 | Todo timestamp en UTC | P11 | 1.5 |
| 17 | Toda hora mostrada lleva la etiqueta UTC explícita | P11 | 3.5 + 4.4 |
| 18 | Banco adversarial existe | P12 | 6.7 |
| 19 | El banco se ejecuta automáticamente | P12 | 6.8 |
| 20 | El banco enseña su resultado | P12 | 6.8 |

## El formato de nota (§3)

| # | Requisito | Paso |
|---|---|---|
| 21 | Formato del titular con tipo, ID y dos zonas | 1.5 |
| 22 | Titular en inglés | 1.8 |
| 23 | Titular de 60 caracteres como máximo, validado | 1.8 |
| 24 | Contador por tipo, asignado por el script leyendo el índice | 2.3 |
| 25 | Chequeo de IDs duplicados como alarma pasiva | 2.3 + 3.4 |
| 26 | Lista base de zonas de trabajo | 1.4 |
| 27 | Zonas de producto propias de cada proyecto | 1.4 |
| 28 | La regla de los dos segundos, documentada para quien escribe | 7.2 |
| 29 | Dos zonas obligatorias y reales en toda nota | 1.8 |
| 30 | Comodines rechazados | 1.4 |
| 31 | Lista cerrada por proyecto | 1.4 |
| 32 | Alias resueltos | 1.4 |
| 33 | Alta de zona, paso 1: el rechazo que manda buscar equivalentes | 1.4 |
| 34 | Alta de zona, paso 2: se da de alta a la vista y se relanza | **6.6** |
| 35 | Lista negra con el mensaje que manda al fichero de reglas | 1.4 |
| 36 | La palabra ilegal con su disyuntiva | 1.4 |
| 37 | El porqué, obligatorio en las decisiones | 1.2 + 1.8 |
| 38 | Keys: cinco como máximo | **1.8** |
| 39 | Keys: ninguna que ya esté en el titular | **1.8** |
| 40 | Descripción obligatoria | 1.2 + 1.8 |
| 41 | Puntero de origen | 1.5 + 4.1 |
| 42 | Puntero de sustitución | 1.5 + 2.6 |
| 43 | ~~Ficheros tocados: los escribe el script desde el diff~~ | **RETIRADO** — el campo no existe en el v2 (decisión 1). Su función la da git: `git log -- <ruta>` |
| 44 | ~~Ficheros tocados: prohibido a mano~~ | **RETIRADO** — sin campo no hay nada que falsear |
| 45 | La vista por fichero, documentada como mini-sección de la skill con sus dos comandos y qué oficio la usa cuándo | **7.2b** |
| 46 | Rechazo de cualquier campo fuera de los declarados | **1.8** |
| 47 | Las cuatro keys marcadoras con vocabulario controlado | 1.2 |
| 48 | Normalización de las marcadoras | 1.8 |
| 49 | El resto de keys, libres y en inglés | 1.8 |

## Los siete tipos (§4)

| # | Requisito | Paso |
|---|---|---|
| 50 | Los siete tipos con sus campos obligatorios | 1.2 |
| 51 | Las alternativas perdedoras nacen como descartes enlazados, cada uno con su commit y su identificador | **2.5** |
| 52 | Mueren las cinco categorías del memo del v1 | 9.1 |
| 53 | Los cinco destinos de las cinco poblaciones, aplicados en la destilación | **8.4** |
| 54 | La pregunta del dolor, literal y en una sola copia | 1.2 + 1.8 |
| 55 | Al nacer una valla se presentan todas las incidencias candidatas | **6.5** |
| 56 | Se elige una, varias o ninguna, con calma | **6.5** |
| 57 | Poda de vallas en el cierre de sesión | 7.10 |
| 58 | Todas las vallas en cada arranque, sin tope | 3.5 |
| 59 | Vallas arriba y literales en el informe | 4.3 |
| 60 | La pregunta abierta caduca por evento, no por fecha | **7.5** |
| 61 | Debe resolverse antes de construir sobre su módulo | **7.5** |
| 62 | Puede parir una issue de investigación | **7.5** |
| 63 | Al cerrarse la issue, asciende o cae | **7.5** |
| 64 | El bloqueante: criterio de calibración en la skill | **7.2** |
| 65 | El bloqueante lleva el campo `Awaits:`, en inglés | 1.2 |
| 66 | Alta de bloqueante en caliente | 2.6 |
| 67 | Alta de bloqueante en el cierre de sesión | 7.10 |

## Ciclo de vida y retiradas (§5)

| # | Requisito | Paso |
|---|---|---|
| 68 | Desaparecen las lápidas del v1 | 9.1 |
| 69 | Detector de parecidas por keys y texto, dentro de la zona | 1.6 |
| 70 | Rechazo con las candidatas completas y las tres salidas | 1.7 + 1.8 |
| 71 | La sustitución retira la línea vieja hacia el archivo | 2.6 |
| 72 | El cierre saca la línea del índice y la archiva con su motivo | 2.6 |

## La aduana (§6)

| # | Requisito | Paso |
|---|---|---|
| 73 | El generador escribe formato y emojis, y propaga los errores reales de git | 2.4 |
| 74 | La aduana es un hook sobre el comando de commit | 6.1 |
| 75 | Intercepta también a los subagentes | 6.1 |
| 76 | Validación 1: zonas, alias, alta en dos pasos, lista negra, palabra ilegal | 1.4 + 6.6 |
| 77 | Validación 2: árbol de tipos que acaba en pregunta | 1.8 |
| 78 | Validación 2: rechazo "no sé clasificar esto" | **1.8** |
| 79 | Validación 3: la pregunta del dolor | 1.8 |
| 80 | Validación 4: sustitución exigida | 1.8 |
| 81 | Validación 5: destilación con fuentes, detectada por tipo de nota | 1.8 |
| 82 | Validación 6: keys marcadoras normalizadas | 1.8 |
| 83 | Validación 7: el `wip` exento de toda pregunta | 6.3 |
| 84 | Validación 8: verificación única de la issue contra GitHub | 7.6 |
| 85 | Validación 8: los commits de trabajo pasan sin consulta | 2.7 |
| 86 | Validación 9: propagación del error real de git | 2.1 |

## Los índices (§7)

| # | Requisito | Paso |
|---|---|---|
| 87 | Exactamente ocho ficheros y nada más | 3.8 |
| 88 | Una línea por nota: identificador y titular | 2.2 |
| 89 | Los escribe solo el script | 2.2 |
| 90 | El arranque comprueba la coherencia y la enseña | 3.4 + 3.5 |
| 91 | Candado de concurrencia para los commits de código | **2.1** (ver §3.3 del plan) |
| 92 | El archivo es un fichero único cronológico con sus tres destinos | 2.2 |
| 93 | No existe índice general ni índice de planes | 3.8 |
| 94 | Los recuentos se calculan al vuelo | 2.2 + 3.5 |
| 95 | La nota y su línea de índice viajan en el mismo commit | 2.4 |
| 96 | Los índices se versionan y se suben con el repo | **2.6** |

## La lectura (§8)

| # | Requisito | Paso |
|---|---|---|
| 97 | Buscar devuelve el estado completo de una zona, nunca una lista | 4.8 |
| 98 | Vigente por defecto; historia completa bajo demanda | 4.3 |
| 99 | Racimos por punteros, nunca por similitud ni por keys | 4.1 |
| 100 | El título del racimo es la nota viva más reciente | 4.2 |
| 101 | Entrada por identificador | 4.8 |
| 102 | Entrada por zona | 4.8 |
| 103 | Entrada por palabra, con las líneas que casaron señaladas | 4.6 |
| 104 | Entrada por fichero, bajo demanda | 4.7 |
| 105 | Zona sin notas: cero notas en alto | 4.5 |
| 106 | Momento 1: el contenido viaja dentro del encargo al despachar | 5.3 |
| 107 | Reparto por oficio, los siete | 5.2 + 5.7 |
| 108 | Momento 2: el disparador es el usuario en lenguaje natural | **7.3** |
| 109 | Prohibidos los disparadores léxicos, el juicio espontáneo y la inyección por mensaje | **7.3** |
| 110 | El arranque: el orden exacto de las cinco líneas | 3.5 |
| 111 | El último avance con su contexto debajo | 3.2 + 3.5 |
| 112 | Todos los bloqueantes con quién se espera | 3.5 |
| 113 | Recuento de preguntas sin resolver | 3.5 |
| 114 | Recuento de issues abiertas | 3.5 |
| 115 | Recuento de incidencias abiertas | 3.5 |
| 116 | Aviso de plan con commits sin reflejar | **3.4 + 3.5** |
| 117 | Aviso de identificadores duplicados | 3.4 + 3.5 |
| 118 | Aviso de coherencia de índices | 3.4 + 3.5 |
| 119 | Se comunica el menú en el primer mensaje y el usuario decide el rumbo | **7.4** |
| 120 | Desaparecen los presupuestos de renderizado del v1 | 3.5 |

## El contexto de cierre (§9)

| # | Requisito | Paso |
|---|---|---|
| 121 | El titular es el avance, obligatorio, con su emoji | **3.2** |
| 122 | El cuerpo es el contexto en puntos, sin transcripción | **3.2** |
| 123 | Sus keys, en inglés | **3.2** |
| 124 | Sin zonas, sin índice, sin lápida — y **exento en la aduana** | **3.2 + 6.3** |
| 125 | Cada cierre pisa al anterior; el arranque enseña solo el último | 3.2 |
| 126 | Lo escribe el cierre de sesión | 7.10 |
| 127 | Retirada del alta automática de issues | 9.1 |

## Decisiones y planes (§10)

| # | Requisito | Paso |
|---|---|---|
| 128 | La decisión con su porqué, sus keys y su descripción | 2.6 |
| 129 | El plan se diseña en conversación; la issue la crea Claude, nunca un script | **7.6** |
| 130 | El documento del plan vive en la carpeta de documentación | **7.6** |
| 131 | La issue enlaza al documento y aloja el checklist | **7.6** |
| 132 | El acta enlaza decisión e issue | **7.6** |
| 133 | Cambio de decisión: nueva decisión con su puntero, y la issue se edita | **7.6** |
| 134 | Los commits de trabajo llevan la referencia a la issue | 2.7 |
| 135 | Detección exacta por el patrón del trailer | **3.4** |
| 136 | El cierre de sesión marca los checkboxes y deja comentario | 7.10 |
| 137 | Al fusionar: se comprime. **Lo tocado ya no es un campo**: es el diff nativo contra la base | 2.7 |

## Incidencias (§11)

| # | Requisito | Paso |
|---|---|---|
| 138 | La skill de incidencias existe | 7.13 |
| 139 | Las tres vertientes de investigación | 7.13 |
| 140 | Se guarda la incidencia al volver el diagnóstico; el diagnosticador no escribe en git | 7.13 |
| 141 | El pie estructurado del informe de diagnóstico | 7.8 |
| 142 | Rama del fix, pipeline completa, compresión y cierres | **7.13** |
| 143 | Al cerrar la incidencia se retiene el cierre preguntando si sale valla | **6.4** |
| 144 | Recuento de incidencias abiertas en el arranque | 3.5 |
| 145 | Puerta manual siempre abierta | **7.13** |
| 146 | Los cinco puntos internos se resuelven al redactar la skill | **7.13** |

## Reglas, instalación y destilación (§12, §13)

| # | Requisito | Paso |
|---|---|---|
| 147 | Alta de regla: se detecta y se añade al fichero organizado | **3.3** |
| 148 | El fichero de reglas existe — es el destino del mensaje de la lista negra | **3.3** |
| 149 | Las reglas no aparecen en búsquedas ni informes, y no las lee ningún agente | **3.3** |
| 150 | El comando entrega el fichero entero | **3.3** |
| 151 | Las reglas no pasan por la aduana de zonas | **3.3** |
| 152 | El interruptor: la aduana nace apagada | 6.2 |
| 153 | Fecha de corte por proyecto | 8.1 |
| 154 | Muere la consolidación periódica | 7.7 |
| 155 | Destilación por pasadas con tope | **8.3** |
| 156 | En la duda, se propone al usuario | **8.5** |
| 157 | Destilación con las fuentes citadas | 8.3 |
| 158 | El oráculo pierde el consolidador y gana el adaptador | 7.7 |
| 159 | Instalación y publicación del plugin nuevo | **7.14** |

## Validación y puntos abiertos (§15, §16)

| # | Requisito | Paso |
|---|---|---|
| 160 | La prueba: una semana, un solo rol | 5.5 + 5.6 |
| 161 | El implementador declara si una valla le cambió lo que iba a hacer | 5.5 |
| 162 | El juicio final es del propietario; sin métricas numéricas | — (declarado, no construible) |
| 163 | El explorador: zoom-out obligatorio | 7.9 |
| 164 | El papel del documentador | §6.2 del plan (abierto) |
| 165 | Listas de zonas definitivas | §6.3 del plan (tuyo) |
| 166 | Dedup semántico de reglas | §6.4 del plan (abierto) |
| 167 | Carril de ensayo operativo | §6.1 del plan (abierto) |
| 168 | Leer los resultados de la sonda pendiente | **9.4** |

---

## Los 31 huérfanos de la auditoría, y dónde han caído

| Huérfano | Ahora en |
|---|---|
| Las reglas, enteras | 3.3 |
| La skill de memoria | 7.1 – 7.4 |
| El contexto de cierre como pieza escribible | 3.2 |
| Su exención en la aduana | 6.3 |
| El commit de trabajo (con su referencia a issue; sin campo de ficheros tocados) | 2.7 |
| Los descartes automáticos | 2.5 |
| La oferta de valla al cerrar una incidencia | 6.4 |
| Las incidencias candidatas al nacer una valla | 6.5 |
| Alta de zona, paso 2 | 6.6 |
| Keys: tope, ausencia en el titular, idioma | 1.8 |
| Rechazo de campos inexistentes | 1.8 |
| Rechazo "no sé clasificar esto" | 1.8 |
| Protección de escritura de los índices | 2.2 |
| Timestamps en UTC y su etiqueta | 1.5, 3.5, 4.4 |
| Chequeo instalado↔escrito | 7.14 |
| Idioma por función, validado | 1.8 |
| Un campo sin lector no existe | 1.3 + 1.10 |
| Jerarquía visual heredada | 4.4 |
| Instalación del plugin | 7.14 |
| Subida de los índices | 2.6 |
| El candado de concurrencia | 2.1 |
| Aviso de plan sin reflejar | 3.4 + 3.5 |
| El ciclo de vida de la pregunta abierta | 7.5 |
| Los planes como documento e issue | 7.6 |
| Pasos 3-4 del protocolo de incidencias | 7.13 |
| Los cinco puntos internos de ese protocolo | 7.13 |
| La sonda pendiente del v1 | 9.4 |
| El momento 2 de lectura y sus prohibiciones | 7.3 |
| Comunicar el menú del día | 7.4 |
| Detección por el patrón del trailer de issue | 3.4 |
| La compresión al fusionar | 2.7 (sin campo: diff nativo) |

**Ninguno queda fuera.** Los que dependen de una de las siete decisiones de `PLAN-CONSTRUCCION.md` §1 están marcados en su paso.


---

## Nota sobre el campo de ficheros tocados

Los requisitos 43 y 44 quedan **retirados por decisión del propietario**: el campo no existe en el v2. Era un duplicado de lo que git ya guarda, y en el v1 se escribió 605 veces sin que nadie lo leyera nunca.

**La función se conserva entera sin él.** La vista por fichero usa `git log -- <ruta>` y la capa se deduce del diff nativo. Se documenta como mini-sección propia dentro de la skill de memoria (paso 7.2b), con sus dos comandos y con qué oficio la usa cuándo — y **los prompts de los agentes solo la referencian**, para que el contenido viva una sola vez y no acabe habiendo cinco versiones distintas en tres meses.

Es el único requisito de la especificación que se retira, y se retira con el dato delante.
