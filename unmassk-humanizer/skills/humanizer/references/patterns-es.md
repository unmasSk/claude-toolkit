# Patrones — biblioteca de reglas en español (el suelo)

Catálogo para texto en español. **No es una traducción del catálogo inglés.** El
español tiene tics propios: muletillas de registro periodístico, calcos del inglés,
y giros de traducción automática que no existen en el original. Traducir la lista
inglesa palabra por palabra y aplicarla a ciegas produce falsos positivos y se salta
los tells reales del español.

Orden de operaciones igual que en inglés: **estructura primero** (la señal número 1),
luego vocabulario, luego formato. En un texto con protect-list, la protect-list gana
sobre cualquier regla de aquí. Tiers, no prohibiciones absolutas — ver el aviso de
sobrecorrección al final.

---

## Vocabulario por tiers

- **Tier 1 — reemplazar siempre.** Aparece muchísimo más en texto de IA que en escritura humana.
- **Tier 2 — marcar en racimo.** Bien sueltas; 2+ en un párrafo es señal fuerte.
- **Tier 3 — marcar por densidad.** Palabras normales que la IA sobreusa.

### Tier 1 — reemplazar siempre

| Reemplaza | Por |
|---|---|
| sumergirse / adentrarse en | mirar, entrar en, ver |
| profundizar en | analizar, examinar, ver a fondo |
| desglosar / desgranar | explicar, detallar |
| en el vertiginoso mundo de | (córtalo y ve al grano) |
| en la era digital / en pleno siglo XXI | (córtalo, o sé específico) |
| un abanico de (posibilidades/opciones) | varias, muchas (o di cuántas) |
| el panorama (metáfora) | el campo, el sector, el mundo |
| piedra angular | base, pilar, parte central |
| punto de inflexión | cambio, giro |
| marca un antes y un después | (di qué cambió exactamente) |
| revolucionar | cambiar, transformar |
| potenciar / impulsar | mejorar, reforzar, acelerar |
| fomentar | animar, apoyar, promover |
| aprovechar (metáfora de "leverage") | usar |
| robusto | sólido, fiable, fuerte |
| integral / holístico | completo, entero |
| sinergia / sinergias | (di el efecto combinado real) |
| ecosistema (metáfora) | sistema, red, entorno, mercado |
| vibrante | (di qué lo hace vivo, o córtalo) |
| fascinante / apasionante / emocionante | (gánatelo con el contenido, no lo declares) |
| sin lugar a dudas / indudablemente | (córtalo; deja que el hecho aguante solo) |
| cabe destacar / cabe señalar / cabe mencionar | (córtalo y di la cosa) |
| es importante señalar/destacar/mencionar que | (córtalo y di la cosa) |
| en constante evolución | que cambia, que crece (o di cómo) |
| de la mano de | con, junto a |
| a día de hoy | hoy, ahora |
| en aras de | para |
| en el marco de | en, dentro de |
| de cara a | para, ante |

### Tier 2 — marcar cuando aparecen 2+ en un párrafo

clave, crucial, fundamental, esencial, imprescindible, primordial, sustancial,
significativo, notable, destacado, innovador, dinámico, versátil, óptimo, eficaz,
eficiente, transversal, disruptivo, escalable, sólido, riguroso, exhaustivo,
minucioso, meticuloso, enriquecedor, empoderar, catalizar, materializar,
vertebrar, articular, cimentar.

Reemplaza por la palabra llana. Dos o más en un párrafo → ese párrafo suena generado.

### Tier 3 — marcar solo por densidad

importante, interesante, relevante, útil, valioso, completo, moderno, actual,
avanzado. Palabras normales. Márcalas solo cuando el texto se apoya en ellas en vez
de en cifras, comparaciones o ejemplos.

---

## Calcos del inglés y giros de traducción automática (tell específico del español)

La señal más delatora de texto de IA en español no es una palabra culta: es el
**calco**. La IA piensa en inglés y traduce. Estos giros gritan "traducción de LLM":

| Calco (mal) | Español natural |
|---|---|
| hacer sentido | tener sentido |
| aplicar (para un puesto/beca) | solicitar, presentarse a |
| remover (quitar) | quitar, eliminar, retirar |
| asumir (suponer) | suponer, dar por hecho |
| eventualmente (finalmente) | finalmente, con el tiempo, a la larga |
| en orden de / con el fin de + inf. inflado | para |
| adicionalmente | además |
| consecuentemente | por eso, así que |
| inicialmente / subsecuentemente | al principio / después, luego |
| jugar un rol | desempeñar un papel, tener un papel |
| tomar acción | actuar, hacer algo |
| basado en (based on, al inicio de frase) | según, a partir de, con base en |
| eres bienvenido a | puedes, si quieres |
| déjame + inf. ("déjame explicarte") | (córtalo y explícalo) |
| soporte (support, no técnico) | apoyo, ayuda |
| librería (library de software mal traducido en prosa) | biblioteca |
| a través de (through, sobreusado) | mediante, con, por |
| eso es todo lo que necesitas saber | (córtalo) |
| gerundio de posterioridad ("cayó, muriendo días después") | ..."y murió días después" |
| gerundio inglés calcado ("siendo esto", "teniendo en cuenta esto", "dicho esto") | reescribe como oración con verbo conjugado |

**Regla:** si una frase suena a doblaje de película, es traducción automática. Léela
en voz alta; el calco chirría antes que el vocabulario.

---

## Patrones de estructura (la señal número 1 — pésalos por encima del vocabulario)

### Contraste binario (la familia fatal)

Reversiones telegrafiadas. Afirma Y directamente. Variantes a cazar:

- "No se trata (solo) de X, sino de Y."
- "No es X, es Y."
- "La cuestión no es X, sino Y."
- "Más allá de X, está Y."
- "No porque X, sino porque Y."

FATAL en un texto cuya voz lo prohíbe: cero, no "máximo uno". Quita la negación;
afirma Y.

### Agencia falsa (cosas inanimadas haciendo verbos humanos)

La IA lo usa para no nombrar al actor. Nombra a la persona, o usa "tú/usted".

| Mal | Realidad |
|---|---|
| "los datos nos dicen" | alguien los leyó y concluyó |
| "la decisión surge" | alguien decide |
| "la cultura cambia" | la gente cambia de conducta |
| "el mercado premia" | los compradores pagan |

### Otros tells de estructura

- **Longitud uniforme (el metrónomo).** Mezcla frases cortas (3–8 palabras) con largas (20+). Algún párrafo de una sola frase. Si un lector de voz automático pudiera leerlo sin que suene raro, es demasiado uniforme.
- **Regla de tres.** Tríadas forzadas para sonar completo ("rápido, sencillo y eficaz"). Usa dos, cuatro, o una frase entera.
- **Estructura espejo.** Dos frases seguidas con la misma forma. Rompe la simetría.
- **Pregunta retórica + respuesta inmediata** como transición ("¿Qué significa esto? Significa que..."). Ve directo a la respuesta.
- **Final con lacito en cada párrafo.** Deja que un tercio terminen sin moraleja.
- **Enumeración negativa.** "No es un X... no es un Y... es un Z." Di Z.
- **Voz pasiva y pasiva refleja de relleno.** "Se cometieron errores." Nombra al actor.
- **Ciclado de sinónimos.** "los desarrolladores... los programadores... los ingenieros..." en un párrafo. Repite la palabra correcta.

---

## Muletillas de transición y de registro periodístico

El español de IA tira de un registro de columna de periódico. Marcar en racimo:

- **Transiciones infladas:** "por otro lado", "en este sentido", "dicho esto", "de este modo", "así pues", "por consiguiente", "en definitiva", "en resumen", "en conclusión", "a modo de cierre". Una suelta vale; apiladas son tell. "En conclusión" + resumir = no anuncies que concluyes, concluye.
- **Arranques de señalización:** "vamos a sumergirnos en", "profundicemos en", "desglosemos esto", "sin más preámbulos", "acompáñame a descubrir". Empieza por el contenido.
- **Autoridad de pega:** "la verdadera pregunta es", "en el fondo", "lo que de verdad importa", "a nivel de" (muletilla real del español, no solo de IA). Suele ser ceremonia sobre algo corriente.
- **Aforismo formulario:** "X es el Y de Z", "X no es una herramienta, es un espejo". Sustituye por la afirmación concreta.

---

## Artefactos de asistente, adulación y relleno

- **Artefactos de chatbot:** "Espero que esto te sea útil", "¡Por supuesto!", "¡Buena pregunta!", "No dudes en preguntar". Elimínalos.
- **Descargos de fecha de corte:** "Hasta mi última actualización", "aunque la información disponible es limitada". Busca el dato o quita el descargo.
- **Adulación:** "Tienes toda la razón", "excelente apreciación". Fuera.
- **Bucles de reconocimiento:** repetir la pregunta antes de responder. Responde.
- **Adverbios de calibración:** "Cabe destacar", "curiosamente", "sorprendentemente", "notablemente". Marcar por densidad.
- **Frases de relleno:** "es importante tener en cuenta que" → dilo. "en este momento" → "ahora". "tiene la capacidad de" → "puede".
- **Cobertura excesiva:** "podría decirse que quizás tal vez" → "puede".
- **Conclusiones positivas genéricas:** "el futuro es prometedor", "un paso en la dirección correcta". Córtalo o concreta.

---

## Estilo y formato

- **Raya / guion largo (—, –) y el sustituto `--`.** La IA los mete donde el español usa coma, punto o paréntesis. Objetivo: cero, títulos incluidos. (Ojo: la raya es válida en español para incisos y diálogo; el tell es el abuso rítmico, no un uso limpio.)
- **Negrita en exceso.** Una frase en negrita por sección como mucho.
- **Listas con encabezado en negrita que se repite.** "Rendimiento: el rendimiento mejoró..." Quita el encabezado o hazlo párrafo.
- **Mayúsculas de título en encabezados.** El español usa mayúscula solo en la primera palabra. "Cómo mejorar tu escritura", no "Cómo Mejorar Tu Escritura".
- **Comillas tipográficas curvas** (solo tell si se apilan con otras).
- **Signos de apertura ausentes** (¿ ¡): su falta delata traducción del inglés; corrígelo.
- **Exceso de viñetas.** Convierte prosa en viñetas a párrafos salvo contenido de verdad enumerable.

---

## Perfiles de contexto

Igual que en inglés, ajusta rigor por superficie: LinkedIn (2 rayas/post, hooks
ok), blog (estricto), blog técnico (relaja tecnicismos legítimos: robusto,
escalable, biblioteca), email a inversores (extra estricto con lo promocional),
docs (relaja formato), informal (solo P0). Autodetecta por señales del texto si no
se pasa perfil.

**Excepciones de blog técnico** (significado técnico legítimo en español): robusto,
escalable, integral (integración), biblioteca, framework. Siguen marcados: sumergirse,
piedra angular, punto de inflexión, revolucionar, un abanico de.

---

## Tiers de gravedad (triaje en modo detect)

- **P0 — matan la credibilidad:** descargos de fecha de corte, artefactos de chatbot, atribuciones vagas, inflación de importancia en hechos rutinarios, calcos flagrantes ("hacer sentido").
- **P1 — olor obvio a IA:** palabras Tier 1, muletillas de columna, arranques de señalización, ciclado de sinónimos, la familia del contraste binario, gerundios calcados.
- **P2 — pulido de estilo:** conclusiones genéricas, regla de tres, párrafos de longitud uniforme, transiciones infladas.

---

## Aviso de sobrecorrección

Aplicar todas las reglas al máximo rigor lija el texto hasta devolverlo al perfil
estadístico uniforme que suena a IA de entrada. Los fragmentos deliberados, un
arranque con "Y" o "Pero", una palabra idiosincrásica, el ritmo desigual — eso es lo
que mantiene humano el texto. El objetivo es sonar a persona, no a prosa impecable.
En la duda con una firma, defiere a la protect-list. En la duda sin firma, prefiere
la edición ligera. Y nunca marques un patrón dentro de una cita, un título, un
nombre propio o un ejemplo donde el giro se está comentando, no usando.
