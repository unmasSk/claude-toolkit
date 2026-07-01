# PRD — [nombre] · (lector: IA + owner, sin audiencia humana externa)

## 0. META
- project_name: / version: / last_updated: / owner: / status:

## 1. PROBLEMA Y OBJETIVO
- problema: (qué falta hoy, concreto)
- objetivo: (una frase, qué resuelve)
- por_qué: (la razón — para que la IA no re-cuestione la decisión)

## 2. ALCANCE  ← sección crítica para no dispersar
DENTRO:
- 
FUERA / NO-OBJETIVOS (explícito — la IA NO construye nada de aquí):
- 

## 3. REQUISITOS FUNCIONALES
Numerados, sin ambigüedad. Cada uno verificable.
1. 
2. 

## 4. CONTRATO / COMPORTAMIENTO  ← precisión para la IA
Para cada pieza con entrada/salida definida:
- input: / output: / reglas: / formato_error:
(Si la pieza no es una función de datos —una skill, un hook—, describir
 el comportamiento esperado en su lugar, sin forzar JSON.)

## 5. EDGE CASES Y LÍMITES
- input_vacío → / inválido → / ambigüedad →
- límites: (tamaño, tiempo, lo que aplique)

## 6. CRITERIOS DE ÉXITO  (verificables, no "que vaya bien")
- 
- 

## 7. DEPENDENCIAS Y ORDEN
- depende_de:
- orden: (qué va antes que qué)
- bloqueantes_de_producción:

## 8. DECISIONES TOMADAS  ← para que la IA no las re-discuta
- decisión: — razón: — fecha:

## 9. DECISIONES ABIERTAS
- [ ] (lo que falta decidir ANTES de construir)

## 10. REGLAS DE EJECUCIÓN (IA)
- No inferir campos/alcance no especificado. Si falta algo → preguntar, no asumir.
- No expandir el alcance más allá de la sección 2.
- Seguir el orden de la sección 7.
- Determinista sobre creativo.
- Nada entra en "construido" sin cumplir el DoD del proyecto.
