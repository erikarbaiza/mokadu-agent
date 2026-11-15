# El bot de WhatsApp de MOKADU — Guía para Inés

---

## Qué hace

Cuando alguien escribe al WhatsApp del restaurante, el bot responde automáticamente como si fuera alguien del equipo. Sabe todo sobre la carta, los horarios, las reservas y la ubicación.

**Ejemplos de lo que puede responder:**
- "¿Estáis abiertos ahora?" → responde sí/no según el horario real del día
- "¿Qué hay de comer?" → da la carta completa con precios
- "Quiero reservar" → manda el link de Restoo directamente
- "¿Dónde estáis?" → da la dirección y un link a Google Maps
- "¿Tenéis algo sin gluten?" → revisa los alérgenos de cada plato
- Preguntas en euskera → responde en euskera

Mensajes cortos, naturales. No suena a robot.

---

## Cómo probarlo ahora mismo

Escríbele algo al número del restaurante desde tu móvil. Si el bot está conectado, responde en segundos.

Prueba con:
- "¿Estáis abiertos?"
- "¿Cuánto cuesta el Nikita?"
- "Quiero reservar mesa para el viernes"

---

## Qué NO hace

- No gestiona reservas él solo (manda a Restoo para eso)
- No responde fotos ni audios (solo texto)
- Si no sabe algo, da el teléfono del restaurante

---

## Cómo actualizar la información del bot

Todo está en un archivo llamado **`config.json`** dentro de la carpeta `mokadu-agent`.

Ábrelo con cualquier editor de texto (Bloc de notas, Word, lo que sea) y encontrarás:

### Cambiar un precio o plato
Busca el nombre del plato y cambia el precio o la descripción:
```
"nombre": "Nikita",
"precio": "17€",
"descripcion": "Burrito de bonito crudo..."
```

### Añadir un plato nuevo
Dentro de la categoría correspondiente, añade un bloque igual a los demás:
```
{
  "nombre": "Nombre del plato",
  "precio": "12€",
  "descripcion": "Descripción breve"
}
```

### Cambiar los horarios
Busca la sección `"horarios"` y modifica las horas de apertura y cierre de cada día.
Los días cerrados tienen `"franjas": []` (array vacío).

### Añadir información extra (eventos, menú especial, etc.)
Al final del config hay una sección `"reglas_respuesta"`. Puedes añadir una línea como:
```
"El menú de Navidad está disponible del 20 al 31 de diciembre. Consulta por WhatsApp."
```
El bot lo tendrá en cuenta al responder.

---

## Si el bot deja de responder

1. El teléfono del restaurante necesita tener internet (el bot usa WhatsApp Web)
2. Si lleva más de 14 días sin usarse, puede que haya que volver a escanear el QR
3. Para cualquier problema: llama a Erik

---

## Coste

- El bot cuesta menos de **1€ al mes** con el uso normal de un restaurante
- Funciona 24/7 sin que nadie tenga que estar pendiente

---

*Hecho por Erik Arbaiza · arbaiza.erik@gmail.com*
