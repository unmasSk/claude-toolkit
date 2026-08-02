# Textos literales del sistema

Lo que el sistema escupe, palabra por palabra. No descripciones: los textos. Si esto queda a improvisación, cada implementación lo escribe distinto y el rechazo que se lee a las tres de la mañana acaba siendo un volcado ilegible.

**El comando es `gitmem`** — fachada única con subcomandos en inglés sobre los scripts: `note`, `close`, `context`, `work`, `search`, `boot`, `reindex`, `zones`, `rule`, `bench`.

**Emojis** — resueltos. El descarte es 🚫 y no una papelera: la papelera sugiere que se puede borrar, y el descarte es permanente.

```
🧭 D decision     ❓ Q question
📌 M memo         🚫 X discarded
⚠  R restriction  🔥 I incident
⛔ B blocker      ⏩ contexto/avance
🚧 wip            🧠 regla
```

---

## 1. Los rechazos de la aduana

### 1.1 Zona que no existe

```
⛔ NOTA RECHAZADA — la zona «facturacion» no existe

zones.json tiene 34 zonas. Antes de crear una nueva, mira si ya está
con otro nombre. Las más parecidas:

  billing     18 notas   "cobros, pasarela de pago, suscripciones"
  invoices     4 notas   "documentos de factura emitidos al cliente"

Si es una de ellas, relanza con esa:
  gitmem note D --zones product billing "..." --why "..." --description "..."

Si de verdad falta, añádela a .claude/project-memory/zones.json
(nombre en inglés, una línea de descripción, sus alias) y relanza igual.
No pidas permiso: el usuario lo ve en el chat.
```

### 1.2 Zona de la lista negra

```
⛔ NOTA RECHAZADA — «session» no es memoria del proyecto

claude, user, session, project y workflow describen CÓMO trabajamos,
no el producto. Eso va al fichero de reglas, que se lee entero aparte
y no ensucia ninguna búsqueda:

  gitmem rule "..."

Si en realidad hablabas de una parte del producto, dale su zona real:
  gitmem note M --zones <zona1> <zona2> "..." --description "..."
```

### 1.3 La palabra ilegal

```
⛔ NOTA RECHAZADA — «audit» significa dos cosas distintas

Elige cuál:

  registro    (zona2)  el módulo de la aplicación que guarda el rastro
  codeaudit   (zona1)  las auditorías que los agentes pasan al código

Relanza con la que sea:
  gitmem note M --zones product registro "..." --description "..."
  gitmem note M --zones codeaudit <zona2> "..." --description "..."
```

### 1.4 No encaja en ningún tipo

```
⛔ NOTA RECHAZADA — no sé qué tipo es esto

"log rotation strategy and the pending vendor answer" mezcla un hecho
del proyecto con algo que espera de fuera. Una nota, una cosa.

  D  decision     se eligió entre opciones
  M  memo         un hecho estable del proyecto
  R  restriction  una valla: saltarla rompe algo
  Q  question     pregunta abierta, sin respuesta todavía
  X  discarded    se estudió y se descartó
  I  incident     se rompió algo: causa y qué se hizo
  B  blocker      pendiente de fuera; bloquea

Pártela en dos, o elige uno, y relanza:
  gitmem note <TIPO> --zones deploy logging "..." --description "..."

Que no encaje es información: si de verdad no es ninguno de los siete,
dilo en el chat antes de forzarlo.
```

### 1.5 Falta la respuesta a la pregunta del dolor

```
⛔ NOTA RECHAZADA — falta una respuesta

Toda M y toda R contestan lo mismo antes de entrar:

  ¿puede costar datos, horas o producción caída?

  sí  →  es una valla. Entra como R y sale en TODOS los arranques.
  no  →  es un hecho. Entra como M y se lee cuando se busca su zona.

Relanza con la respuesta puesta:
  gitmem note M --zones database backups "..." --description "..." --stops no
  gitmem note R --zones database backups "..." --description "..." --stops yes
```

### 1.6 Pisa a algo ya escrito

```
⛔ NOTA RECHAZADA — esto pisa a algo que ya está escrito

Tu nota comparte terreno con estas de [product][auth]. Di qué pasa
con ellas antes de entrar:

  D-030   2026-04-11   login with JWT + Google OAuth
          keys: token, oauth, sso, signin
          Why: sesiones no escalan multi-tenant; Google evita gestionar
               passwords propios

  D-041   2026-06-02   session lifetime raised to 30 days
          keys: token, expiry, refresh
          Why: el equipo de campo se quejó de reloguear cada semana

Tres salidas, y solo tres:

  la sustituye   --replaces D-030    la vieja sale del índice a ARCHIVED
  conviven       --replaces none     las dos siguen vigentes
  es duplicado   no la guardes; si hay que matizar, cierra la vieja:
                 gitmem close D-030 "..."

Relanza:
  gitmem note D --zones product auth "..." --why "..." \
    --description "..." --replaces D-030
```

### 1.7 Destilación sin fuentes

```
⛔ NOTA RECHAZADA — una destilación sin fuentes no es una destilación

Compactar es decir DE QUÉ. Sin Origin no hay forma de volver a lo que
resumiste ni de comprobar si lo resumiste bien.

Pon los hashes v1 de los que sale, separados por comas:
  gitmem note M --zones testing amianto "..." --description "..." \
    --origin 4f2a1bc,9de77a0,c31b8e5

Vale para toda nota de destilación, la escriba quien la escriba.
```

### 1.8 Key marcadora mal escrita — no es rechazo, es aviso al guardar

```
✅ M-062 guardada — con una key corregida

  seguridad  →  security

Las cuatro keys marcadoras tienen una sola forma válida, para que la
búsqueda las encuentre siempre:

  antipattern    (anti-pattern, antipatron, antipatrón)
  security       (seguridad, sec)
  performance    (perf, rendimiento)
  legal          (legales, compliance)

El resto de keys son libres, en inglés. No hay que hacer nada.
```

### 1.9 La issue del acta no existe

```
⛔ ACTA RECHAZADA — la issue #47 no existe en este repo

Esta es la única vez que se comprueba. Si el número está mal, el enlace
decisión → plan queda roto para siempre y nadie lo va a notar.

  gh issue list --limit 20          ver las abiertas
  gh issue create --title "..."     crearla ahora

Relanza con el número bueno:
  gitmem note PLAN --zones product auth "login rollout plan" \
    --origin D-030 --issue 52
```

### 1.10 Cierre de incidencia: ¿sale valla?

```
⛔ CIERRE RETENIDO — I-014 no se cierra sin contestar esto

  ¿de esta cicatriz sale valla?

  I-014  [testing][auth]  seeds wiped the production users table
         causa: el script de seeds coge la BD de una variable de entorno,
         y en el runner de CI esa variable traía producción.

  sí  →  nace una R en esta misma zona y sale en todos los arranques
  no  →  se cierra sin más; nadie vuelve a enterarse

Relanza con la respuesta:

  gitmem close I-014 "..." --restriction no

  gitmem close I-014 "..." --restriction new \
    --restriction-text "seeds never read the DB url from the environment" \
    --why "..."
```

---

## 2. El informe de estado

### 2.1 Zona con contenido

```
════════════════════════════════════════════════════════════════════════
  ZONA auth · 14 vigentes · 6 archivadas            2026-08-01 09:12 UTC
════════════════════════════════════════════════════════════════════════

⚠ RESTRICCIONES (3) — literales

  R-004  [testing][auth]  never run the auth test suite against production
         Why: en marzo un test de login borró 1.200 sesiones reales y se
              tardó cuatro horas en reconstruirlas desde el backup.
         Origin: I-009

  R-011  [api][auth]  refresh tokens are never logged, not even truncated
         Why: un token truncado sigue sirviendo para la mitad de los
              ataques de replay que probamos.
         Keys: security

  R-018  [deploy][auth]  no auth deploy on Friday without a tested rollback
         Why: los dos incidentes de auth de este año fueron viernes por la
              tarde y sin vuelta atrás ensayada.
         Origin: I-014

⛔ BLOQUEANTES (1)

  B-003  [product][auth]  google workspace admin consent still pending
         espera: el cliente (Marta, IT de Omawa)
         Description: sin el consentimiento de administrador no se puede
         probar el alta masiva de usuarios; el flujo individual sí va.

🧭 DECISIONES (2 racimos)

  D-030  login with JWT + Google OAuth                          2026-04-11
         Why: sesiones no escalan multi-tenant; Google evita gestionar
              passwords propios.
    ├─ X-012  server-side sessions                    descartada · Origin D-030
    ├─ X-013  own password login                      descartada · Origin D-030
    ├─ D-041  session lifetime raised to 30 days      vigente   · Origin D-030
    └─ #47    plan-login.md                           acta      · 2026-04-12

  D-052  logout revokes the refresh token server-side           2026-07-03
         Why: el logout de cliente dejaba el refresh vivo 30 días.
    └─ D-036  logout only clears the cookie           archivada · replaced by D-052

📌 MEMOS (4)

  M-021  google returns email_verified=false for workspace aliases
  M-033  the JWT carries tenant_id; the gateway reads it, nobody else
  M-048  password reset links live 15 minutes, not the 60 in the docs
  M-057  Auth0 was never used here, whatever the README said until June

🔥 INCIDENCIAS (2 · 1 abierta)

  I-014  session fixation on the tenant switcher       cerrada 2026-06-20
         → parió R-018
  I-021  login loop on Safari 17 after the cookie change
         ABIERTA desde 2026-07-28

❓ LO QUE ESPERA DE TI (2)

  Q-007  do we support more than one Google Workspace per tenant?
         Bloquea el modelo de datos de invitaciones. Hay que contestarla
         antes de tocar el módulo de equipos.

  Q-015  is the 30-day session lifetime acceptable for the audit?
         Nació de D-041. Sin respuesta desde el 2 de junio.

────────────────────────────────────────────────────────────────────────
  Historia completa, con lo archivado:   gitmem search auth --todo
```

### 2.2 Zona sin ninguna nota

```
════════════════════════════════════════════════════════════════════════
  ZONA payments                                     2026-08-01 09:14 UTC
════════════════════════════════════════════════════════════════════════

              ⚠  C E R O   N O T A S

  La zona existe en zones.json (dada de alta el 2026-07-30) y no tiene
  ni una: ninguna decisión, ninguna valla, ningún hecho, ninguna
  incidencia, ninguna pregunta.

  Es un dato, no un fallo. O el trabajo no ha empezado, o se ha hecho
  sin escribir nada de lo que se decidió.

  Zonas parecidas que sí tienen contenido:

     billing    18 notas       gitmem search billing
     invoices    4 notas       gitmem search invoices

  Si lo que buscabas está en una de ellas, esta zona sobra en zones.json.
════════════════════════════════════════════════════════════════════════
```

### 2.3 Búsqueda por palabra suelta

```
════════════════════════════════════════════════════════════════════════
  PALABRA «stripe» · 3 zonas · 11 vigentes          2026-08-01 09:20 UTC
  ›  marca la línea que casó
════════════════════════════════════════════════════════════════════════

──── [api][billing] · 6 notas ──────────────────────────────────────────

⚠ RESTRICCIONES (1)

› R-029  no Stripe test hits the live key, ever
         Why: en mayo un test de suscripciones cobró 340 € reales a
              catorce clientes; hubo que devolverlo a mano uno por uno.
         Origin: I-011

🧭 DECISIONES

› D-044  billing runs on Stripe Billing, not on our own invoicing
         Why: el IVA por país y las facturas rectificativas ya resueltos
              valen más que el control de tenerlo en casa.
    ├─ X-021  own invoicing engine                    descartada · Origin D-044
    ├─ X-022  Chargebee                               descartada · Origin D-044
    └─ #62    plan-billing.md                         acta      · 2026-05-19

📌 MEMOS (3)

› M-044  webhooks arrive in UTC and out of order; dedup by event id
› M-051  the customer id lives in tenants.stripe_id, nowhere else
  M-055  the tax rate comes from the customer address, not the card

──── [testing][billing] · 3 notas ──────────────────────────────────────

🔥 INCIDENCIAS (1 · cerrada)

› I-011  test suite charged 340 EUR to real customers   cerrada 2026-05-14
         → parió R-029

📌 MEMOS (2)

› M-038  the Stripe test clock is the only way to test renewals
  M-047  webhook fixtures live in tests/fixtures/webhooks, not inline

──── [deploy][infra] · 2 notas ─────────────────────────────────────────

📌 MEMOS (1)

› M-060  the Stripe webhook secret rotates per environment; staging
         and prod never share it

❓ LO QUE ESPERA DE TI (1)

› Q-019  do we move to Stripe Tax before the next fiscal year?
         Nació de D-044. Sin respuesta desde el 19 de mayo.

────────────────────────────────────────────────────────────────────────
  Estado completo de una zona:   gitmem search billing
  Con lo archivado:              gitmem search stripe --todo
```

---

## 3. El arranque

### 3.1 Proyecto con contenido

```
╔══════════════════════════════════════════════════════════════════════╗
║  MEMORIA · omawa                                 2026-08-01 09:02 UTC ║
╚══════════════════════════════════════════════════════════════════════╝

⏩ NEXT   implement discussed changes to close-session skill
          Context (cerrado 2026-07-31 19:44 UTC):
          - Revisado el diseño del checkpoint: muere el automático, lo
            hace close-session
          - Punto de inflexión: fuera comodines — toda nota lleva dos
            zonas reales
          - Decidido de palabra: los planes viven en docs/ como plan-*.md
          - Quedó en el aire el alcance de facturación; hablar antes de
            empezar

⛔ BLOQUEANTES (2)

   B-003  [product][auth]   google workspace admin consent still pending
          espera: el cliente (Marta, IT)
   B-007  [deploy][infra]   the .es staging domain is not bought yet
          espera: el usuario

⚠ RESTRICCIONES (5)

   R-004  [testing][auth]     never run the auth test suite against production
          en marzo un test borró 1.200 sesiones reales; cuatro horas de
          reconstrucción desde el backup
   R-011  [api][auth]         refresh tokens are never logged, not even truncated
          un token truncado sigue sirviendo para replay
   R-018  [deploy][auth]      no auth deploy on Friday without a tested rollback
          los dos incidentes de auth del año fueron viernes sin vuelta atrás
   R-022  [database][amianto] never delete a measurement row; mark it void
          las mediciones son prueba legal ante inspección
   R-029  [testing][billing]  no Stripe test hits the live key, ever
          en mayo se cobró 340 € reales a catorce clientes

RECUENTOS
   Q sin resolver ......  6
   issues abiertas .....  4
   I abiertas ..........  1

AVISOS
   ⚠  plan #47: 3 commits sin reflejar en la issue
   ✓  IDs sin duplicados (68 notas)
   ✓  índices coherentes con git (68 líneas / 68 notas)

El mapa está puesto. Dime por dónde: el Next, una pregunta, una issue,
o lo que traigas.
```

### 3.2 Proyecto recién instalado

```
╔══════════════════════════════════════════════════════════════════════╗
║  MEMORIA · monyma                                2026-08-01 09:02 UTC ║
╚══════════════════════════════════════════════════════════════════════╝

⏩ NEXT   ninguno todavía. No hay ningún cierre de sesión escrito.
          El primero lo escribe close-session al terminar hoy.

⛔ BLOQUEANTES ......  C E R O
⚠ RESTRICCIONES ....  C E R O
                      No hay ninguna valla puesta. Nada te va a parar
                      porque nadie ha escrito todavía qué rompe qué.

RECUENTOS
   Q sin resolver ......  0
   issues abiertas .....  0
   I abiertas ..........  0

AVISOS
   ✓  IDs sin duplicados (0 notas)
   ✓  índices coherentes con git (0 líneas / 0 notas)
   ·  los ocho índices existen y están vacíos
   ·  zones.json: 9 zonas de trabajo, 0 zonas de producto
      La primera nota va a pedir una zona2 que no existe. Es lo normal:
      se da de alta ahí mismo, a la vista.

Cero no es silencio: es que todavía no se ha escrito nada. La primera
nota se guarda así:

  gitmem note <TIPO> --zones <zona1> <zona2> "titular en inglés" \
    --description "..." --stops <yes|no>
```

---

## 4. Las líneas de índice

**Regla común:** la línea **es** el titular del commit, sin emoji. Un tipo por fichero, orden por identificador, solo vigentes. Sin fecha: nadie la leería del índice, y un campo que nadie lee no existe.

```
── DECISIONS.md ────────────────────────────────────────────────────────
# DECISIONS — índice. Lo escribe el script. No editar. Si diverge, manda git.

[D-030][product][auth] login with JWT + Google OAuth
[D-041][product][auth] session lifetime raised to 30 days
[D-044][api][billing] billing runs on Stripe Billing, not own invoicing
```

```
── MEMOS.md ────────────────────────────────────────────────────────────
[M-021][api][auth] google returns email_verified=false for aliases
[M-044][api][billing] webhooks arrive out of order; dedup by event id
```

```
── RESTRICTIONS.md ─────────────────────────────────────────────────────
[R-004][testing][auth] never run the auth test suite against production
[R-022][database][amianto] never delete a measurement row; mark it void
```

```
── QUESTIONS.md ────────────────────────────────────────────────────────
[Q-007][product][auth] do we support >1 Google Workspace per tenant?
```

```
── INCIDENTS.md ────────────────────────────────────────────────────────
[I-014][testing][auth] seeds wiped the production users table
```

```
── DISCARDED.md ────────────────────────────────────────────────────────
# Permanente: aquí nada se archiva. Existe para que nadie lo re-proponga.

[X-012][product][auth] server-side sessions
[X-022][api][billing] Chargebee
```

```
── BLOCKED.md ──────────────────────────────────────────────────────────
[B-003][product][auth] google workspace admin consent still pending
```

```
── ARCHIVED.md ─────────────────────────────────────────────────────────
# Todo lo retirado, en orden cronológico. El tipo viaja en la línea; al
# pasado se le pregunta por fecha. Lo escribe el script.

2026-06-02  🧭 [D-036][product][auth] session lifetime is 7 days  →  replaced by D-041
2026-06-20  🔥 [I-014][testing][auth] session fixation on the tenant switcher  →  closed: arreglado en #58 y con valla puesta (R-018)
2026-07-14  📌 [M-019][api][billing] Stripe sends webhooks in local time  →  replaced by M-044
2026-07-22  ❓ [Q-004][product][billing] do we need per-seat pricing?  →  promoted to M-051
2026-07-29  ⛔ [B-002][deploy][infra] the CI runner has no docker socket  →  closed: el proveedor lo habilitó el 28
2026-07-30  ❓ [Q-009][ui][amianto] should the report export to XLSX too?  →  promoted to X-030
```

Los tres destinos, literales: `replaced by <ID>` · `closed: <motivo>` · `promoted to <ID>`.

---

## 5. Los commits, uno por tipo

### Decisión — con sus descartes en el mismo acto

```
🧭 [D-030][product][auth] login with JWT + Google OAuth

Why: sesiones no escalan multi-tenant; Google evita gestionar passwords
 propios y quita de encima el reset y la política de contraseñas.
Keys: token, oauth, sso, signin, credentials
Description: Brainstorm sobre el login con el usuario. Se valoraron
 sesiones de servidor, login propio con contraseña y JWT + OAuth de
 Google. Pesó el multi-tenant (el mismo usuario en varias empresas) y
 que el cliente ya vive en Workspace. Se acepta la deuda de tener que
 resolver la revocación de refresh tokens a mano.
```

```
🚫 [X-012][product][auth] server-side sessions

Why: no escalan multi-tenant sin un almacén compartido que aún no
 tenemos, y obligaría a Redis solo para esto.
Keys: session, cookie, redis, sticky
Description: Alternativa perdedora de D-030. Se descartó por el coste de
 infraestructura, no por el diseño: si algún día hay Redis por otra
 razón, merece releerse.
Origin: D-030
```

### Memo

```
📌 [M-044][api][billing] webhooks arrive out of order; dedup by event id

Keys: webhook, idempotency, ordering, duplicate, retry
Description: Stripe reintenta hasta tres días y no garantiza el orden.
 Llegó un invoice.paid antes que su invoice.created. La tabla
 billing_events guarda el event id con índice único y descarta el
 repetido; el orden se reconstruye por created_at del payload, nunca
 por el momento de llegada.
Replaces: M-019
```

### Restricción

```
⚠ [R-029][testing][billing] no Stripe test hits the live key, ever

Why: en mayo un test de suscripciones cobró 340 € reales a catorce
 clientes y hubo que devolverlo a mano, uno por uno, con disculpa.
Keys: security, sandbox, apikey, charge, live
Description: Los tests solo pueden ver la clave sk_test_. La clave viva
 no está en ningún .env de desarrollo ni en los secrets del runner de
 tests: vive solo en el entorno de producción. Si un test necesita
 renovaciones, se usa el test clock de Stripe, no la clave real.
Origin: I-011
```

### Pregunta abierta

```
❓ [Q-007][product][auth] do we support >1 Google Workspace per tenant?

Why: el modelo de datos de invitaciones cambia entero según la respuesta,
 y ya hay dos módulos escritos encima suponiendo que no.
Keys: workspace, tenant, invite, domain, multi
Description: Un cliente tiene dos dominios de Workspace (la matriz y la
 filial) y quiere un solo espacio en la aplicación. Si se soporta, la
 invitación deja de colgar del dominio y pasa a colgar del tenant, con
 tabla de dominios permitidos. Hay que contestarla antes de tocar el
 módulo de equipos.
```

### Descarte

```
🚫 [X-022][api][billing] Chargebee

Why: el IVA por país lo resuelve igual que Stripe, pero añade un
 proveedor más y su propio webhook que mantener.
Keys: chargebee, subscription, vendor, tax
Description: Alternativa perdedora de D-044. Se probó una cuenta de
 prueba durante dos días: la gestión de rectificativas es mejor, pero no
 compensa un segundo sistema de cobro cuando el pago ya pasa por Stripe.
 No re-proponer sin que cambie una de esas dos cosas.
Origin: D-044
```

### Incidencia

```
🔥 [I-014][testing][auth] seeds wiped the production users table

Why: se perdieron 1.200 sesiones y 40 minutos de altas; cuatro horas de
 reconstrucción desde el backup de la noche anterior.
Keys: seeds, database, truncate, env, ci
Description: El script de seeds lee la URL de la base de datos de la
 variable DATABASE_URL y hace TRUNCATE antes de sembrar. En el runner de
 CI esa variable venía del entorno del proyecto, que traía producción.
 Causa raíz: el script confía en el entorno para saber contra qué habla.
 Se arregló exigiendo la URL como argumento explícito y abortando si el
 host no es local. Diagnóstico de House, fix en #58.
```

### Bloqueante

```
⛔ [B-003][product][auth] google workspace admin consent still pending

Awaits: el cliente — Marta, IT de Omawa
Keys: consent, admin, workspace, oauth, scope
Description: El alta masiva de usuarios necesita que un administrador de
 Workspace apruebe el scope admin.directory.user.readonly. Sin eso, el
 flujo de invitación individual funciona pero el importe de plantilla no,
 y la demo del día 12 no puede enseñarlo. Pedido el 24 de julio.
```

### Acta de plan

```
📋 [PLAN][product][auth] login rollout plan

Keys: rollout, milestone, checklist
Description: El plan de ejecución de D-030 vive en docs/plan-login.md;
 la issue #52 aloja el checklist tachable y el DoD. Tres fases: OAuth de
 Google, revocación de refresh, y migración de los usuarios existentes.
Origin: D-030
Issue: #52
```

### Contexto de cierre — sin zonas, sin índice

```
⏩ implement discussed changes to close-session skill

Keys: close-session, checkpoint, plan
Context:
- Revisado el diseño del checkpoint: muere el automático, lo hace close-session
- Punto de inflexión: fuera comodines — toda nota lleva dos zonas reales
- Decidido de palabra: los planes viven en docs/ como plan-*.md
- Quedó en el aire el alcance de facturación; hablar antes de empezar
```

---

## 6. Decisiones que la especificación no cerraba — todas resueltas por el propietario

1. **Los emojis.** ❓ pregunta · 🚫 descarte (no una papelera: el descarte es permanente) · 🔥 incidencia.
2. **El comando es `gitmem`**, fachada única con subcomandos en inglés sobre los scripts.
3. **La key mal escrita no es un rechazo.** Normalizar es escribir, y un hook no escribe. Se ha redactado como el aviso que sale al guardar bien. Si se quiere rechazo de verdad, la mecánica cambia.
4. **El campo del bloqueante es `Awaits:`** — en inglés y capitalizado como el resto, porque todo nombre que ve una máquina va en inglés. En la presentación al usuario se lee «espera:», que es texto y va en español.
5. **Las vallas del arranque salen con una línea de porqué**, no solo el titular. Un titular en inglés a secas no cambia la conducta de nadie a las tres de la mañana.
6. **La línea de índice es el titular literal, sin emoji ni fecha.** El identificador ya viaja dentro. El emoji solo aparece en el archivo, que es el único fichero que mezcla tipos.
7. **El campo de ficheros tocados NO EXISTE en el v2.** Se retiró entero: git ya guarda el diff y no se puede mentir sin él. La vista por fichero usa `git log -- <ruta>` directamente. Las notas tampoco llevan co-autor. Las notas de memoria no tocan ficheros de aplicación; la línea de índice viaja en el mismo commit pero no se declara, para no convertir ese campo en ruido en las siete plantillas.
