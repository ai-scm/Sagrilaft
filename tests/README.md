# Estado de las Pruebas — Formulario SAGRILAFT
Función única: catálogo de cobertura frontend. Seguimiento de mejoras en [P19](../docs/produccion/PENDIENTES_PRODUCCION.md#p19).

---

## ¿De qué trata esto?

El formulario SAGRILAFT es la aplicación web que usan las contrapartes para diligenciar su información de vinculación. Durante estas sesiones de trabajo se construyó una **batería de pruebas** — un conjunto de verificaciones automáticas que comprueban que el sistema se comporta correctamente en cada situación posible, sin necesidad de hacerlo a mano cada vez.

El resultado son **74 pruebas automáticas, todas pasando**, distribuidas en dos niveles: pruebas de lógica interna y pruebas del flujo completo de usuario.

---

## Lo que se cubrió

### Nivel 1 — Pruebas de lógica interna (60 pruebas ✅)

Estas pruebas verifican que cada parte del formulario funciona bien por separado, simulando situaciones sin necesidad de abrir un navegador.

---

#### 🔐 Pantalla de Acceso (`PantallaIngreso`)

| Lo que se verificó |
|---|
| La pantalla muestra el formulario de acceso correctamente cuando no hay ningún borrador previo |
| Cuando hay un borrador guardado, muestra la fecha real de cuándo se guardó (no un texto genérico), pre-llena el código de petición, y **no** auto-completa el PIN por seguridad |
| Al hacer clic en "Ingresar" con los campos vacíos, el sistema no hace ninguna llamada — simplemente no pasa nada |
| Al presionar ENTER con campos vacíos, tampoco se envía nada |
| Al enviar, el sistema limpia los espacios en blanco y pone el código en mayúsculas automáticamente |
| Cuando el sistema está verificando las credenciales, se muestra el indicador de carga y el formulario queda bloqueado |
| Si las credenciales son incorrectas, aparece el mensaje de error correspondiente |
| Al hacer clic en el campo de código o PIN, el borde cambia de color (feedback visual); al salir del campo, vuelve al color normal |

---

#### 🔑 Control de Sesión (`DiligenciamientoContext`)

Esta parte gestiona si el usuario tiene acceso activo o no al formulario.

| Lo que se verificó |
|---|
| Cuando un usuario accede con un enlace especial (token por correo), el sistema carga su formulario correctamente |
| Si ese enlace ya venía con datos extraídos por la IA (de una sesión anterior), esos datos se preservan |
| Cuando el usuario entra con código + PIN y los datos son correctos, se abre el formulario |
| Si el código o el PIN son incorrectos, aparece el mensaje "Código de petición o PIN incorrecto" |
| Si el formulario ya había sido enviado, aparece el mensaje de que no se puede recuperar |
| Si el enlace venció, aparece el mensaje de acceso expirado |
| Si el servidor no responde por problemas de red, aparece un mensaje genérico de error |
| El botón "Cerrar sesión" funciona correctamente y regresa a la pantalla de acceso con el mensaje correspondiente |
| El botón "Descartar borrador" elimina el borrador guardado y limpia el estado |

---

#### 📋 Lógica del Formulario (`useFormulario`)

Esta es la parte más crítica: controla todo lo que pasa mientras el usuario llena el formulario paso a paso.

| Lo que se verificó |
|---|
| El formulario inicia correctamente en el Paso 1 con todos los campos en blanco |
| **Persona Natural vs Persona Jurídica:** Al cambiar el tipo de persona, los campos que no aplican se limpian automáticamente. Si es Natural, los campos de empresa se borran. Si es Jurídica, los campos personales se borran |
| **Paso 4 exclusivo de Jurídica:** Las tablas de Junta Directiva, Accionistas y Beneficiarios se vacían cuando se cambia a Persona Natural |
| El sistema no deja avanzar de paso si hay campos obligatorios sin llenar |
| Cuando no hay errores, el botón "Siguiente" lleva al paso correcto |
| **Moneda extranjera:** Si el usuario marca "No" en operaciones en moneda extranjera, los campos relacionados se limpian solos |
| **Tipo de documento:** Cuando el usuario cambia el tipo de identificación (cédula, NIT, pasaporte), el número de documento se borra para evitar datos inconsistentes |
| Las filas vacías en las tablas de Referencias y Datos Bancarios se eliminan automáticamente antes de guardar |
| Cuando se sube un documento y la IA extrae datos (razón social, NIT, nombre del representante), esos datos se mezclan en el formulario automáticamente |
| Cuando se elimina un documento, los datos que la IA había extraído de ese documento también se eliminan del formulario |
| Si el usuario intenta radicar con errores en varios pasos, el formulario lo lleva automáticamente al paso con el primer error |
| **Radicación exitosa:** Al enviar el formulario al servidor y obtener respuesta positiva, el sistema muestra la pantalla de éxito |
| **Radicación con credenciales vencidas:** Si el token de sesión expiró durante el diligenciamiento, aparece el aviso para que el usuario vuelva a ingresar |
| **Radicación con enlace vencido:** Si el enlace de acceso ya no es válido, aparece el mensaje correspondiente |
| Si hay cualquier otro error al radicar, aparece un mensaje genérico de error |

---

#### 📎 Carga de Documentos (`FileUploadField`)

El área donde el usuario arrastra o selecciona archivos para adjuntar.

| Lo que se verificó |
|---|
| Muestra la zona de carga cuando no hay ningún archivo |
| Muestra el indicador de "Analizando con IA..." mientras el sistema procesa el documento |
| Cuando el archivo está cargado, muestra el nombre y el peso del archivo con el ícono de confirmación |
| El botón de eliminar funciona y llama a la función correcta |
| Mientras se está eliminando, el botón queda deshabilitado para evitar clics dobles |
| Si hay un error en la carga, muestra el mensaje de error debajo del campo |
| Si hay una nota de ayuda (por ejemplo "No mayor a 30 días"), la muestra junto al campo |
| Al hacer clic en la zona, abre el selector de archivos del sistema operativo |
| Se puede arrastrar y soltar un archivo directamente sobre la zona |
| Si el usuario arrastra un archivo pero lo suelta sin soltarlo encima de la zona, no pasa nada |

---

#### ✍️ Firma del Representante Legal (`FirmaRepresentanteLegal`)

La sección donde el representante confirma fecha y ciudad de firma.

| Lo que se verificó |
|---|
| Muestra el formulario de firma correctamente con los campos vacíos |
| Trae la fecha del servidor automáticamente y llena los campos de día, mes y año |
| El botón "Limpiar fecha" borra los campos de fecha |
| Muestra los mensajes de error cuando los campos están mal |
| El texto narrativo de la declaración se actualiza en tiempo real con los valores que el usuario ingresa |

---

#### 🖥️ Pantalla principal del formulario (`FormularioSagrilaft`)

La pantalla que contiene todos los pasos del formulario.

| Lo que se verificó |
|---|
| Muestra el encabezado y el Paso 1 (Documentos) al cargar |
| Muestra el Paso 2 (Información Básica) cuando corresponde |
| Cuando el formulario ya fue enviado, muestra la pantalla de confirmación de radicación |
| En el último paso, el botón "Radicar" está bloqueado si el usuario no ha marcado el checkbox de aceptación |
| Cuando el checkbox está marcado, el botón "Radicar" se habilita |
| Mientras la IA está analizando un documento, el botón "Siguiente" permanece bloqueado para evitar que el usuario avance sin que el proceso termine |

---

### Nivel 2 — Pruebas del flujo completo (14 pruebas ✅)

Estas pruebas simulan a un usuario real usando la aplicación en un navegador, desde que entra hasta que ve el resultado. Toda comunicación con servidores externos (el backend, la IA de Amazon, las listas de cautela) está reemplazada por respuestas simuladas para que las pruebas sean confiables y no dependan de conexiones externas.

---

#### ✅ Verificación de Infraestructura
- El sistema de pruebas puede arrancar la aplicación, interceptar todas las llamadas al servidor y comprobar que el formulario carga correctamente después de hacer login.

#### 👔 Flujo Persona Jurídica (5 pruebas)
- **Paso 1:** Los documentos que ya estaban cargados aparecen correctamente en la lista.
- **Paso 2:** La información básica de la empresa se muestra con los datos pre-llenados (por ejemplo, el nombre de la empresa aparece en el campo correspondiente).
- **Paso 3:** Los datos del representante legal aparecen pre-llenados.
- **Paso 4:** La sección de Junta Directiva, Representantes y Accionistas es visible y accesible (este paso solo existe para Jurídica).
- **Paso 8:** Las Declaraciones y el botón "Radicar Formulario" están visibles en el último paso.

#### 🙍 Flujo Persona Natural (3 pruebas)
- El Paso 3 muestra el formulario de datos personales correctamente.
- Cuando el formulario se abre en el Paso 5 (Información Financiera), **el Paso 4 de Junta Directiva no aparece en ningún momento** — confirmando que el sistema omite ese paso correctamente para Persona Natural.
- El Paso 8 (último paso) está disponible y muestra el botón de radicación.

#### 💾 Persistencia y Recuperación de Borrador (2 pruebas)
- Si el servidor indica que el usuario iba en el Paso 5 cuando cerró sesión, el formulario se abre directamente en ese paso — no desde el principio.
- Si hay un borrador guardado en el navegador, la pantalla de acceso muestra el aviso de "Borrador guardado" con el botón para descartarlo.

#### 🤖 Extracción de Datos por IA (1 prueba)
- Al subir un documento, el sistema llama al servicio de IA, recibe los campos extraídos y muestra el archivo como cargado exitosamente.

#### ⛔ Accesos Bloqueados (2 pruebas)
- Si el usuario entra con un enlace vencido, aparece el mensaje de error de acceso expirado y el formulario no carga.
- Si el usuario ingresa un PIN incorrecto, aparece el mensaje de error y la pantalla de acceso permanece visible.

---

<a id="cobertura"></a>
## Límites de cobertura automática

### Flujos del formulario que aún no tienen prueba automática

| Situación | Por qué es importante |
|---|---|
| **Radicación completa en el navegador** | Confirmar que al hacer clic en "Radicar", el modal de confirmación aparece, el usuario lo acepta y llega a la pantalla de "Formulario Radicado con Éxito" |
| **Formulario devuelto para corrección** | Cuando el área interna devuelve un formulario señalando campos específicos, verificar que esos campos se destacan en naranja, los demás quedan bloqueados y el usuario solo puede editar los marcados |
| **Guardado automático en el navegador** | Verificar que mientras el usuario llena el formulario, el sistema guarda periódicamente un respaldo en el navegador |
| **Autocompletado desde IA con verificación en pantalla** | Confirmar que los datos que la IA extrae del documento (nombre, NIT, dirección) efectivamente aparecen pre-llenados en los campos del formulario en los pasos siguientes |
| **Listas de cautela con coincidencias** | Verificar qué muestra el sistema cuando el nombre de la empresa o representante aparece en una lista de alertas |

### Partes del código sin prueba propia

Estas partes existen en el sistema, pero no tienen una prueba automática propia que verifique su comportamiento de forma aislada; producción aún no está desplegada según el estado documentado.

| Parte del sistema | Qué hace |
|---|
| **Recuperación de sesión** (`useRecuperacionSesion`) | La lógica que decide si usar los datos del servidor o del borrador local cuando son de fechas distintas |
| **Pantalla de confirmación de radicación** (`SubmittedView`) | La pantalla que ve el usuario al terminar de radicar |
| **Barra de progreso** (`NavegacionFormulario`) | El indicador de pasos que muestra en cuál está el usuario y cuáles ha completado |
| **Panel de ayuda contextual** (`HelpPanel`) | El panel que explica cada campo cuando el usuario hace clic en el ícono de ayuda |
| **Modal de confirmación previo a radicar** (`ModalConfirmacion`) | El aviso que aparece antes de enviar definitivamente |
| **Guardado automático en servidor** (`usePersistenciaRemota`) | La lógica que cada cierto tiempo guarda el formulario en el servidor mientras el usuario lo llena |
| **Modo corrección** (`CorreccionContext`) | Todo el sistema de campos bloqueados/desbloqueados cuando el formulario es devuelto |
| **Los 8 pasos individuales del formulario** | Cada sección (Paso 1 al 8) como pantalla completa no tiene prueba propia — solo se prueba su aparición desde la pantalla principal |

### Evidencia de ambientes

Las ejecuciones reales se consultan en [Estado](../docs/estado/ESTADO_DESPLIEGUE_STAGING_PROD.md)
y su [evidencia AWS](../docs/evidencia/e2e-staging/EVIDENCIA_E2E_STAGING_2026-10-01.md).
Este catálogo describe cobertura automática; su ampliación se gestiona en P19.

---

## Resumen en números

| | Cantidad | Estado |
|---|---|---|
| Pruebas de lógica interna | 60 | ✅ Todas pasando |
| Pruebas de flujo completo en navegador | 14 | ✅ Todas pasando |
| **Total de pruebas automáticas** | **74** | **✅** |
| Archivos de producción con prueba | 6 de ~60 | En progreso |
| Flujos E2E cubiertos | 5 de ~10 flujos críticos | En progreso |

---

## Archivos nuevos creados durante este trabajo

```
Pruebas de lógica interna:
  src/components/PantallaIngreso.test.jsx
  src/components/FileUploadField.test.jsx
  src/components/FirmaRepresentanteLegal.test.jsx
  src/components/FormularioSagrilaft.test.jsx
  src/context/DiligenciamientoContext.test.jsx
  src/hooks/formulario/useFormulario.test.jsx

Pruebas de flujo completo en navegador:
  e2e/00-verify.spec.js
  e2e/01-persona-juridica.spec.js
  e2e/02-persona-natural.spec.js
  e2e/03-persistencia.spec.js
  e2e/04-ia-prefill.spec.js
  e2e/05-token-expirado.spec.js
  e2e/utils/networkMocks.js   ← Simulación de servidores externos

Configuración:
  playwright.config.js         ← Configuración del sistema de pruebas en navegador
  src/setupTests.js            ← Configuración de pruebas de lógica interna

Documentación:
  docs/README.md              ← Mapa de fuentes del proyecto
  tests/integration/README.md ← Harness y pruebas backend
```

> Ningún archivo de producción fue modificado durante la construcción de las pruebas —
> solo se corrigió un pequeño detalle en `useFormulario.js` relacionado con el guardado.
